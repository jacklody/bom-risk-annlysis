"""风险分析接口（v3 — 集成实时数据源）。

改动：分析前先调用 SupplyDataService 查询 LCSC/Mouser 实时交期/库存/生命周期，
再将数据传入 supply_risk 引擎做综合评分。
"""

import asyncio
import csv
import io
from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.knowledge.brand_category_map import normalize_brand
from app.models.event import MarketEvent
from app.models.bom import BomItem, BomProject, RiskLevel
from app.models.media_source import MediaSourceRun
from app.knowledge.media_sources import list_media_sources
from app.services.bom_matcher import BOMMatcher
from app.services.supply_risk import evaluate_supply_risk, is_standard_package
from app.services.supply_data import SupplyDataService
from app.services.risk_report_export import XLSX_MIME_TYPE, render_risk_report_html, render_risk_report_xlsx
from app.services.upstream.risk_context_builder import build_v32_context
from app.services.upstream.category_classifier import classify_component_category
from app.services.market_intel_engine import MarketIntelEngine

router = APIRouter()

# 全局 SupplyDataService 实例（lifespan 中初始化）
_supply_data_svc: SupplyDataService | None = None


def get_supply_data_service() -> SupplyDataService:
    """获取或延迟创建 SupplyDataService"""
    global _supply_data_svc
    if _supply_data_svc is None:
        _supply_data_svc = SupplyDataService()
    return _supply_data_svc


async def ensure_supply_data_service_initialized(service: SupplyDataService) -> None:
    """初始化真实供应数据服务，同时兼容测试替身。"""
    initialize = getattr(service, "initialize", None)
    if initialize is not None and not getattr(service, "_initialized", False):
        await initialize()


def _risk_rank(level: str) -> int:
    """风险等级排序：gray=0 < green=1 < yellow=2 < orange=3 < red=4"""
    return {"gray": 0, "green": 1, "yellow": 2, "orange": 3, "red": 4}.get((level or "gray").lower(), 0)


def _combine_risk_level(market_level: RiskLevel, supply_level: str) -> RiskLevel:
    market_value = market_level.value if hasattr(market_level, "value") else str(market_level or "gray")
    combined = supply_level if _risk_rank(supply_level) > _risk_rank(market_value) else market_value
    return RiskLevel(combined)


def _apply_supply_fields(item: BomItem, supply):
    item.production_risk_level = supply.production_risk_level
    item.production_risk_score = supply.production_risk_score
    item.lead_time_risk_weeks = supply.lead_time_risk_weeks
    item.eol_status = supply.eol_status
    item.supply_risk_tags = supply.supply_risk_tags
    item.supply_risk_reason = supply.supply_risk_reason
    item.procurement_suggestion = supply.procurement_suggestion
    # v3 新增实时数据字段
    item.total_stock = supply.total_stock
    item.supplier_count = supply.supplier_count
    item.lead_time_days = supply.lead_time_days
    item.unit_price = supply.unit_price
    item.lifecycle_status = supply.lifecycle_status
    item.commonality_score = supply.commonality_score


def _build_v32_context(item: BomItem, events: list[MarketEvent], realtime_data: dict | None, commonality: dict | None) -> dict:
    return build_v32_context(item=item, events=events, realtime_data=realtime_data, commonality=commonality)


def _csv_event_ids(raw_ids: str | None) -> list[int]:
    ids: list[int] = []
    if not raw_ids:
        return ids
    for raw_id in str(raw_ids).split(","):
        raw_id = raw_id.strip()
        if not raw_id:
            continue
        try:
            ids.append(int(raw_id))
        except ValueError:
            continue
    return ids


def _report_v32_context(item: BomItem, event_by_id: dict[int, MarketEvent]) -> dict:
    events = [event_by_id[event_id] for event_id in _csv_event_ids(item.matched_event_ids) if event_id in event_by_id]
    realtime_data = {
        "total_stock": item.total_stock or 0,
        "supplier_count": item.supplier_count or 0,
        "lead_time_days": item.lead_time_days,
        "unit_price": item.unit_price,
        "lifecycle_status": item.lifecycle_status,
        "is_available": bool((item.total_stock or 0) > 0),
    }
    commonality = {
        "is_standard_package": is_standard_package(item.raw_spec or ""),
        "is_major_brand": bool(item.normalized_brand or item.raw_brand),
        "has_multi_source": (item.supplier_count or 0) >= 2,
        "is_basic_part": False,
    }
    return _build_v32_context(item, events, realtime_data, commonality)


def _risk_report_market_evidence(item: BomItem, event_by_id: dict[int, MarketEvent]) -> list[dict]:
    evidence = []
    for event_id in _csv_event_ids(item.matched_event_ids):
        event = event_by_id.get(event_id)
        if event is None:
            continue
        evidence.append({
            "id": event.id,
            "title": event.raw_title or event.raw_text or f"事件 {event.id}",
            "source_name": event.source_name,
            "event_type": event.event_type.value if event.event_type else None,
            "severity": event.severity.value if event.severity else None,
            "confidence": event.confidence,
            "price_impact_pct": event.estimated_price_impact_pct,
            "lead_time_impact_weeks": event.estimated_lead_time_impact_weeks,
        })
    return evidence


def _risk_report_item_payload(item: BomItem, event_by_id: dict[int, MarketEvent]) -> dict:
    payload = {
        "id": item.id,
        "row_number": item.row_number,
        "part_number": item.raw_part_number,
        "brand": item.raw_brand,
        "category": item.normalized_category or item.raw_category,
        "risk_level": item.risk_level.value if item.risk_level else "gray",
        "risk_score": round(item.risk_score or 0, 1),
        "risk_reason": item.risk_reason,
        "suggestion": item.procurement_suggestion,
        "procurement_suggestion": item.procurement_suggestion,
        "total_stock": item.total_stock,
        "supplier_count": item.supplier_count,
        "lead_time_days": item.lead_time_days,
        "unit_price": item.unit_price,
        "lifecycle_status": item.lifecycle_status,
        "supply_sources_summary": item.supply_sources_summary,
        "supply_risk_tags": item.supply_risk_tags,
        "market_evidence": _risk_report_market_evidence(item, event_by_id),
    }
    payload.update(_report_v32_context(item, event_by_id))
    return payload


def _classify_v32_category_for_match(item: BomItem) -> str:
    description = " ".join(
        str(value or "")
        for value in [item.normalized_category, item.raw_spec, item.raw_category, item.raw_part_number]
    )
    manufacturer = item.normalized_brand or item.raw_brand or ""
    return classify_component_category(description, manufacturer=manufacturer).category


def _event_matches_v32_category(item: BomItem, event: MarketEvent) -> bool:
    event_category = (event.category or "").strip().lower()
    if not event_category:
        return False
    item_v32_category = _classify_v32_category_for_match(item).lower()
    if event_category != item_v32_category:
        return False
    event_brand = (event.brand or "").strip()
    if not event_brand:
        return True
    event_brand_norm = normalize_brand(event_brand) or event_brand
    item_brand_text = " ".join(str(value or "") for value in [item.normalized_brand, item.raw_brand])
    item_brand_norm = normalize_brand(item.normalized_brand or "") or normalize_brand(item.raw_brand or "") or item_brand_text
    return event_brand_norm.lower() in item_brand_text.lower() or item_brand_norm.lower() == str(event_brand_norm).lower() and event_brand.lower() in item_brand_text.lower()


def _merge_v32_events(item: BomItem, events: list[MarketEvent], active_events: list[MarketEvent]) -> list[MarketEvent]:
    merged = list(events or [])
    existing_ids = {event.id for event in merged if event.id is not None}
    for event in active_events:
        if event.id in existing_ids:
            continue
        if _event_matches_v32_category(item, event):
            merged.append(event)
            if event.id is not None:
                existing_ids.add(event.id)
    return merged


def _item_payload(item: BomItem, level: RiskLevel, score: float, reason: str, events: list[MarketEvent], v32_context: dict | None = None):
    payload = {
        "id": item.id,
        "row_number": item.row_number,
        "raw_part_number": item.raw_part_number,
        "raw_brand": item.raw_brand,
        "raw_category": item.raw_category,
        "raw_spec": item.raw_spec,
        "raw_qty": item.raw_qty,
        "normalized_brand": item.normalized_brand,
        "normalized_category": item.normalized_category,
        # 行情事件风险
        "risk_level": level.value,
        "risk_score": round(score, 1),
        "risk_reason": reason,
        # 供应链实时数据风险
        "production_risk_level": item.production_risk_level,
        "production_risk_score": round(item.production_risk_score or 0, 1),
        "lead_time_risk_weeks": item.lead_time_risk_weeks,
        "eol_status": item.eol_status,
        "supply_risk_tags": item.supply_risk_tags,
        "supply_risk_reason": item.supply_risk_reason,
        "procurement_suggestion": item.procurement_suggestion,
        # v3 新增：实时数据字段
        "total_stock": item.total_stock,
        "supplier_count": item.supplier_count,
        "lead_time_days": item.lead_time_days,
        "unit_price": item.unit_price,
        "lifecycle_status": item.lifecycle_status,
        "commonality_score": item.commonality_score,
        "matched_events": [e.to_dict() for e in events],
    }
    if v32_context:
        payload.update(v32_context)
    return payload


@router.post("/analyze/{upload_id}")
async def analyze_bom(upload_id: int, db: Session = Depends(get_db)):
    """对指定BOM执行风险分析（含实时数据源查询）"""
    project = db.query(BomProject).filter(BomProject.id == upload_id).first()
    if not project:
        return {"error": "BOM upload not found"}

    items = (
        db.query(BomItem)
        .filter(BomItem.bom_upload_id == upload_id)
        .all()
    )
    active_events = (
        db.query(MarketEvent).filter(MarketEvent.is_active == 1).all()
    )

    # 市场事件匹配
    matcher = BOMMatcher(active_events)
    # 行情情报引擎
    intel_engine = MarketIntelEngine()

    # 实时数据查询：收集所有物料 MPN → 批量查询
    supply_svc = get_supply_data_service()
    supply_results = {}
    supply_degraded = False

    try:
        await ensure_supply_data_service_initialized(supply_svc)
        mpns = [item.raw_part_number for item in items if item.raw_part_number]
        supply_results = await supply_svc.query_batch(mpns)
    except Exception as supply_error:
        import logging
        logging.getLogger(__name__).warning(
            f"SupplyDataService 不可用，降级为仅事件匹配模式: {supply_error}"
        )
        supply_degraded = True
        supply_results = {}

    results = {"red": 0, "yellow": 0, "green": 0, "gray": 0, "items": []}

    # 记录分析前旧风险等级，用于变更追踪
    old_risk_map = {item.id: item.risk_level.value if item.risk_level else "gray" for item in items}
    new_red = new_orange = new_yellow = 0

    for item in items:
        mpn = item.raw_part_number or ""

        # 市场事件匹配；额外桥接 v3.2 品类事件（如 high_cap_mlcc）
        market_level, market_score, events, market_reason = matcher.match_item(item)
        events = _merge_v32_events(item, events, active_events)

        # 获取实时数据
        realtime = supply_results.get(mpn)
        rd = {
            "total_stock": realtime.total_stock if realtime else 0,
            "supplier_count": realtime.supplier_count if realtime else 0,
            "lead_time_days": realtime.lead_time_days if realtime else None,
            "unit_price": realtime.unit_price if realtime else None,
            "lifecycle_status": realtime.lifecycle_status if realtime else "Unknown",
            "is_available": realtime.is_available if realtime else False,
        } if realtime else {}

        # 通用性评估
        commonality = {
            "is_standard_package": is_standard_package(item.raw_spec or ""),
            "is_major_brand": bool(item.normalized_brand),
            "has_multi_source": (realtime.supplier_count if realtime else 0) >= 2 if realtime else False,
            "is_basic_part": False,  # LCSC basic 标记后续从 API 获取
        }

        # 综合风险评估
        supply = evaluate_supply_risk(item, events, rd, commonality)
        _apply_supply_fields(item, supply)

        # 行情情报匹配：基于品类/品牌的市场风险 + 业务建议
        intel_result = intel_engine.match_item(
            raw_part_number=item.raw_part_number or "",
            raw_brand=item.raw_brand or "",
            raw_category=item.raw_category or "",
            raw_description=item.raw_description or "",
        )

        level = _combine_risk_level(market_level, supply.production_risk_level)
        # 行情情报风险叠加
        intel_rank = _risk_rank(intel_result.risk_level)
        if intel_rank > _risk_rank(level.value if hasattr(level, "value") else str(level or "gray")):
            level = RiskLevel(intel_result.risk_level)

        # v3.2 双轨风险参与最终融合（先构建上下文，再取 v32_risk_level 叠加）
        v32_context = _build_v32_context(item, events, rd, commonality)
        v32_level = v32_context.get("v32_risk_level")
        v32_rank = _risk_rank(v32_level)
        if v32_rank > _risk_rank(level.value if hasattr(level, "value") else str(level or "gray")):
            level = RiskLevel(v32_level)

        score = max(float(market_score or 0), float(supply.production_risk_score or 0))
        if intel_result.matched:
            score = max(score, 60.0 if intel_result.risk_level == "yellow" else 80.0 if intel_result.risk_level == "red" else 40.0)
        v32_score = v32_context.get("v32_risk_score")
        if v32_score is not None:
            score = max(score, float(v32_score) if isinstance(v32_score, (int, float)) else 0)

        reason = market_reason
        if supply.supply_risk_reason and supply.supply_risk_reason not in reason:
            reason = f"{market_reason}；{supply.supply_risk_reason}"
        if intel_result.summary:
            reason = f"{reason} | [行情] {intel_result.summary}"
        if v32_context.get("v32_evidence_summary"):
            reason = f"{reason} | [v3.2] {v32_context['v32_evidence_summary']}"

        item.risk_level = level
        item.risk_score = score
        item.risk_reason = reason
        item.matched_event_ids = ",".join(str(e.id) for e in events)

        # 行情情报业务建议
        if intel_result.business_advice and not item.procurement_suggestion:
            item.procurement_suggestion = intel_result.business_advice
        elif intel_result.business_advice:
            item.procurement_suggestion = f"[行情建议] {intel_result.business_advice}；{item.procurement_suggestion}"

        # 风险变更追踪：记录旧等级并在恶化时标记
        item.last_risk_level = old_risk_map.get(item.id, "gray")
        new_level_val = level.value
        if new_level_val != item.last_risk_level and _risk_rank(new_level_val) > _risk_rank(item.last_risk_level):
            item.risk_changed_at = datetime.now(timezone.utc)
            item.risk_trigger_event_ids = item.matched_event_ids
            if new_level_val == "red": new_red += 1
            elif new_level_val == "orange": new_orange += 1
            elif new_level_val == "yellow": new_yellow += 1

        results["items"].append(_item_payload(item, level, score, reason, events, v32_context))

        level_key = level.value
        results[level_key] = results.get(level_key, 0) + 1

    project.items_analyzed = len(items)
    project.items_red = results.get("red", 0)
    project.items_orange = results.get("orange", 0)
    project.items_yellow = results.get("yellow", 0)
    project.items_green = results.get("green", 0)
    project.items_gray = results.get("gray", 0)
    project.new_red_count = new_red
    project.new_orange_count = new_orange
    project.new_yellow_count = new_yellow
    project.last_analysis_at = datetime.now(timezone.utc)

    db.commit()

    return {
        "upload_id": upload_id,
        "project_name": project.project_name or project.filename,
        "total_items": len(items),
        "supply_degraded": supply_degraded,
        "summary": {
            "red": results.get("red", 0),
            "orange": results.get("orange", 0),
            "yellow": results.get("yellow", 0),
            "green": results.get("green", 0),
            "gray": results.get("gray", 0),
        },
        "items": results["items"],
    }


@router.post("/analyze-all")
async def analyze_all_projects(db: Session = Depends(get_db)):
    """批量分析所有活跃BOM项目（含实时数据源查询）"""
    projects = (
        db.query(BomProject)
        .filter(BomProject.status == "active")
        .order_by(BomProject.id)
        .all()
    )
    active_events = (
        db.query(MarketEvent).filter(MarketEvent.is_active == 1).all()
    )
    matcher = BOMMatcher(active_events)

    # 收集所有项目的所有 MPN
    all_mpns = []
    project_items_map = {}
    for project in projects:
        items = (
            db.query(BomItem)
            .filter(BomItem.bom_upload_id == project.id)
            .all()
        )
        project_items_map[project.id] = items
        for item in items:
            if item.raw_part_number:
                all_mpns.append(item.raw_part_number)

    # 批量查询实时数据
    supply_svc = get_supply_data_service()
    supply_results = {}
    supply_degraded = False
    try:
        await ensure_supply_data_service_initialized(supply_svc)
        supply_results = await supply_svc.query_batch(list(set(all_mpns)))
    except Exception as supply_error:
        import logging
        logging.getLogger(__name__).warning(
            f"SupplyDataService 不可用，降级为仅事件匹配模式: {supply_error}"
        )
        supply_degraded = True
        supply_results = {}

    project_summaries = []
    for project in projects:
        items = project_items_map[project.id]
        red = orange_count = yellow = green = gray = 0
        eol_count = lead_time_risk_count = 0
        new_red = new_orange = new_yellow = 0
        old_risk_map = {item.id: item.risk_level.value if item.risk_level else "gray" for item in items} if items else {}

        for item in items:
            mpn = item.raw_part_number or ""
            market_level, market_score, events, market_reason = matcher.match_item(item)
            events = _merge_v32_events(item, events, active_events)

            realtime = supply_results.get(mpn)
            rd = {
                "total_stock": realtime.total_stock if realtime else 0,
                "supplier_count": realtime.supplier_count if realtime else 0,
                "lead_time_days": realtime.lead_time_days if realtime else None,
                "unit_price": realtime.unit_price if realtime else None,
                "lifecycle_status": realtime.lifecycle_status if realtime else "Unknown",
                "is_available": realtime.is_available if realtime else False,
            } if realtime else {}

            commonality = {
                "is_standard_package": is_standard_package(item.raw_spec or ""),
                "is_major_brand": bool(item.normalized_brand),
                "has_multi_source": (realtime.supplier_count if realtime else 0) >= 2 if realtime else False,
                "is_basic_part": False,
            }

            supply = evaluate_supply_risk(item, events, rd, commonality)
            _apply_supply_fields(item, supply)

            # 行情情报匹配
            intel_result = intel_engine.match_item(
                raw_part_number=item.raw_part_number or "",
                raw_brand=item.raw_brand or "",
                raw_category=item.raw_category or "",
                raw_description=item.raw_description or "",
            )

            level = _combine_risk_level(market_level, supply.production_risk_level)
            intel_rank = _risk_rank(intel_result.risk_level)
            if intel_rank > _risk_rank(level.value if hasattr(level, "value") else str(level or "gray")):
                level = RiskLevel(intel_result.risk_level)

            # v3.2 双轨风险参与最终融合
            v32_ctx = _build_v32_context(item, events, rd, commonality)
            v32_level = v32_ctx.get("v32_risk_level")
            v32_rank = _risk_rank(v32_level)
            if v32_rank > _risk_rank(level.value if hasattr(level, "value") else str(level or "gray")):
                level = RiskLevel(v32_level)

            score = max(float(market_score or 0), float(supply.production_risk_score or 0))
            if intel_result.matched:
                score = max(score, 60.0 if intel_result.risk_level == "yellow" else 80.0 if intel_result.risk_level == "red" else 40.0)
            v32_score = v32_ctx.get("v32_risk_score")
            if v32_score is not None:
                score = max(score, float(v32_score) if isinstance(v32_score, (int, float)) else 0)

            reason = market_reason
            if supply.supply_risk_reason and supply.supply_risk_reason not in reason:
                reason = f"{market_reason}；{supply.supply_risk_reason}"
            if intel_result.summary:
                reason = f"{reason} | [行情] {intel_result.summary}"
            if v32_ctx.get("v32_evidence_summary"):
                reason = f"{reason} | [v3.2] {v32_ctx['v32_evidence_summary']}"

            item.risk_level = level
            item.risk_score = score
            item.risk_reason = reason
            item.matched_event_ids = ",".join(str(e.id) for e in events)

            if intel_result.business_advice and not item.procurement_suggestion:
                item.procurement_suggestion = intel_result.business_advice
            elif intel_result.business_advice:
                item.procurement_suggestion = f"[行情建议] {intel_result.business_advice}；{item.procurement_suggestion}"

            # 风险变更追踪
            item.last_risk_level = old_risk_map.get(item.id, "gray")
            new_level_val = level.value
            if new_level_val != item.last_risk_level and _risk_rank(new_level_val) > _risk_rank(item.last_risk_level):
                item.risk_changed_at = datetime.now(timezone.utc)
                item.risk_trigger_event_ids = item.matched_event_ids
                if new_level_val == "red": new_red += 1
                elif new_level_val == "orange": new_orange += 1
                elif new_level_val == "yellow": new_yellow += 1

            if item.eol_status in ("confirmed", "suspected"):
                eol_count += 1
            if item.production_risk_level in ("red", "yellow") or item.lead_time_risk_weeks:
                lead_time_risk_count += 1

            if level.value == "red": red += 1
            elif level.value == "orange": orange_count += 1
            elif level.value == "yellow": yellow += 1
            elif level.value == "green": green += 1
            else: gray += 1

        project.items_analyzed = len(items)
        project.items_red = red
        project.items_orange = orange_count
        project.items_yellow = yellow
        project.items_green = green
        project.items_gray = gray
        project.new_red_count = new_red
        project.new_orange_count = new_orange
        project.new_yellow_count = new_yellow
        project.last_analysis_at = datetime.now(timezone.utc)

        project_summaries.append({
            "project_id": project.id,
            "project_name": project.project_name or project.filename,
            "total": len(items),
            "red": red, "orange": orange_count, "yellow": yellow, "green": green, "gray": gray,
            "eol_count": eol_count,
            "lead_time_risk_count": lead_time_risk_count,
            "risk_rate": round((red + orange_count + yellow) / len(items) * 100, 1) if items else 0,
        })

    db.commit()
    return {"projects": project_summaries, "total_projects": len(projects), "supply_degraded": supply_degraded}


@router.get("/report/{upload_id}")
def project_risk_report(upload_id: int, db: Session = Depends(get_db)):
    """生成项目级风险行动报告，汇总行情情报、市场事件、业务建议。"""
    project = db.query(BomProject).filter(BomProject.id == upload_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="BOM project not found")

    items = (
        db.query(BomItem)
        .filter(BomItem.bom_upload_id == upload_id)
        .all()
    )

    # 高/中风险物料
    high_risk_items = [item for item in items if item.risk_level and item.risk_level.value in ("red", "orange")]
    yellow_items = [item for item in items if item.risk_level and item.risk_level.value == "yellow"]

    # 汇总品类分布
    category_risk: dict[str, dict] = {}
    for item in items:
        cat = item.normalized_category or item.raw_category or "未分类"
        if cat not in category_risk:
            category_risk[cat] = {"category": cat, "total": 0, "red": 0, "orange": 0, "yellow": 0}
        category_risk[cat]["total"] += 1
        level = item.risk_level.value if item.risk_level else "gray"
        if level in ("red", "orange", "yellow"):
            category_risk[cat][level] += 1

    # 汇总当前项目实际关联的行情来源。
    # 注意：这里不能用全局 active_events，否则所有 BOM 项目的“行情来源/活跃事件”都会显示一样。
    matched_event_ids: set[int] = set()
    for item in items:
        if not item.matched_event_ids:
            continue
        for raw_id in str(item.matched_event_ids).split(","):
            raw_id = raw_id.strip()
            if not raw_id:
                continue
            try:
                matched_event_ids.add(int(raw_id))
            except ValueError:
                continue

    active_events = (
        db.query(MarketEvent)
        .filter(MarketEvent.id.in_(matched_event_ids), MarketEvent.is_active == 1)
        .all()
        if matched_event_ids
        else []
    )
    event_by_id = {event.id: event for event in active_events if event.id is not None}
    event_sources = set()
    for event in active_events:
        event_sources.add(event.source_name or "")
    # 去掉 kb 源
    event_sources.discard("market_intel_kb")
    event_sources.discard("")

    # 近期采集运行记录
    recent_runs = (
        db.query(MediaSourceRun)
        .order_by(MediaSourceRun.started_at.desc())
        .limit(10)
        .all()
    )

    # 汇总业务建议
    suggestions: list[str] = []
    for item in items:
        if item.procurement_suggestion and item.procurement_suggestion not in suggestions:
            suggestions.append(item.procurement_suggestion)
    # 按风险分类整理建议
    urgent_actions: list[str] = []
    watch_actions: list[str] = []
    for item in high_risk_items:
        if item.procurement_suggestion:
            sugg = item.procurement_suggestion
            desc = f"{item.raw_part_number or '未知型号'}（{item.raw_brand or '未知品牌'}）：{sugg}"
            urgent_actions.append(desc)
    for item in yellow_items:
        if item.procurement_suggestion:
            sugg = item.procurement_suggestion
            desc = f"{item.raw_part_number or '未知型号'}（{item.raw_brand or '未知品牌'}）：{sugg}"
            watch_actions.append(desc)

    # 媒体源状态
    media_sources = list_media_sources(enabled_only=True)

    return {
        "project": project.to_summary(),
        "risk_summary": {
            "total_items": len(items),
            "red": project.items_red or 0,
            "yellow": project.items_yellow or 0,
            "green": project.items_green or 0,
            "gray": project.items_gray or 0,
            "risk_rate": round(
                ((project.items_red or 0) + (project.items_yellow or 0)) / max(1, len(items)) * 100, 1
            ),
            "has_urgent": len(high_risk_items) > 0,
        },
        "category_risk": sorted(category_risk.values(), key=lambda x: x["red"] + x["yellow"], reverse=True),
        "intel_sources": {
            "active_event_count": len(active_events),
            "source_count": len(event_sources),
            "sources": sorted(event_sources),
            "registered_media_sources": len(media_sources),
            "recent_runs": [run.to_dict() for run in recent_runs],
        },
        "actions": {
            "urgent": urgent_actions[:10],
            "watch": watch_actions[:15],
            "all_suggestions_count": len(suggestions),
        },
        "high_risk_items": [
            _risk_report_item_payload(item, event_by_id)
            for item in high_risk_items
        ][:20],
        "items": [
            _risk_report_item_payload(item, event_by_id)
            for item in items
        ],
        "last_analysis_at": project.last_analysis_at.isoformat() if project.last_analysis_at else None,
    }


@router.get("/report/{upload_id}/export.html", response_class=HTMLResponse)
def export_project_risk_report_html(upload_id: int, db: Session = Depends(get_db)):
    report = project_risk_report(upload_id, db)
    html = render_risk_report_html(report)
    return HTMLResponse(content=html)


@router.get("/report/{upload_id}/export.xlsx")
def export_project_risk_report_xlsx(upload_id: int, db: Session = Depends(get_db)):
    report = project_risk_report(upload_id, db)
    content = render_risk_report_xlsx(report)
    project = report.get("project") or {}
    name = project.get("project_name") or project.get("filename") or f"project-{upload_id}"
    filename = quote(f"{name}-BOM风险报告.xlsx")
    return Response(
        content=content,
        media_type=XLSX_MIME_TYPE,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


CSV_MIME_TYPE = "text/csv; charset=utf-8-sig"

_CSV_HEADERS = [
    "行号", "物料编号", "品牌", "品类", "风险等级", "风险评分",
    "风险原因", "采购建议", "库存总量", "供应商数", "交期(天)",
    "单价", "生命周期", "供应源摘要", "供应风险标签",
    "v3.2风险等级", "v3.2风险评分", "v3.2需求/供应压力",
    "关联事件标题", "关联事件来源", "关联事件严重性",
]


def _render_risk_report_csv(report: dict) -> str:
    """将风险报告渲染为 CSV 字符串 (UTF-8 BOM)。"""
    output = io.StringIO()
    writer = csv.writer(output)

    # 表头
    writer.writerow(_CSV_HEADERS)

    # 数据行
    items: list[dict] = report.get("items") or []
    for item in items:
        row_num = item.get("row_number", "")
        part_number = item.get("part_number") or ""
        brand = item.get("brand") or ""
        category = item.get("category") or ""
        risk_level = item.get("risk_level") or ""
        risk_score = item.get("risk_score") or ""
        risk_reason = item.get("risk_reason") or ""
        suggestion = item.get("procurement_suggestion") or item.get("suggestion") or ""
        total_stock = item.get("total_stock") or ""
        supplier_count = item.get("supplier_count") or ""
        lead_time = item.get("lead_time_days") or ""
        unit_price = item.get("unit_price") or ""
        lifecycle = item.get("lifecycle_status") or ""
        supply_sources = item.get("supply_sources_summary") or ""
        supply_tags = item.get("supply_risk_tags") or ""
        v32_level = item.get("v32_risk_level") or ""
        v32_score = item.get("v32_risk_score") or ""
        v32_pressure = item.get("v32_pressure_summary") or ""

        # 关联事件
        evidence: list[dict] = item.get("market_evidence") or []
        event_titles = "；".join(e.get("title", "") for e in evidence)
        event_sources = "；".join(e.get("source_name", "") for e in evidence)
        event_severities = "；".join(e.get("severity", "") or "" for e in evidence)

        writer.writerow([
            row_num, part_number, brand, category, risk_level, risk_score,
            risk_reason, suggestion, total_stock, supplier_count, lead_time,
            unit_price, lifecycle, supply_sources, supply_tags,
            v32_level, v32_score, v32_pressure,
            event_titles, event_sources, event_severities,
        ])

    return output.getvalue()


@router.get("/report/{upload_id}/export.csv")
def export_project_risk_report_csv(upload_id: int, db: Session = Depends(get_db)):
    """导出项目风险报告为 CSV 文件。"""
    report = project_risk_report(upload_id, db)
    content = _render_risk_report_csv(report)
    project = report.get("project") or {}
    name = project.get("project_name") or project.get("filename") or f"project-{upload_id}"
    filename = quote(f"{name}-BOM风险报告.csv")
    return Response(
        content=content.encode("utf-8-sig"),
        media_type=CSV_MIME_TYPE,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )
