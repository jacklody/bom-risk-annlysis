"""行情情报 API —— 播种行情事件、查询情报、回扫BOM"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.bom import BomItem, BomProject
from app.models.event import MarketEvent, EventType, Severity
from app.knowledge.market_intel import MARKET_INTEL_ENTRIES
from app.services.market_intel_engine import MarketIntelEngine

router = APIRouter(prefix="/api/market-intel", tags=["market-intel"])


@router.post("/seed")
def seed_market_intel(db: Session = Depends(get_db)):
    """将行情情报知识库中的所有条目播种到 market_events 表，激活并去重"""
    created = 0
    updated = 0
    skipped = 0

    for entry in MARKET_INTEL_ENTRIES:
        existing = db.query(MarketEvent).filter(
            MarketEvent.raw_title == entry.summary[:200],
            MarketEvent.source_name == "market_intel_kb",
        ).first()

        if existing:
            if not existing.cross_validated:
                existing.cross_validated = 1
            else:
                existing.cross_validated += 1
            db.commit()
            updated += 1
            continue

        brand = entry.brand if entry.brand else None
        category = entry.category if entry.category else None

        evt = MarketEvent(
            source_name="market_intel_kb",
            source_url="kb://market_intel",
            raw_title=entry.summary[:200] if entry.summary else "",
            raw_text=f"{entry.summary}\n\n业务建议：{entry.business_advice}",
            brand=brand,
            category=category,
            event_type=EventType(entry.event_type) if entry.event_type in {e.value for e in EventType} else EventType.OTHER,
            severity=Severity(entry.severity) if entry.severity in {s.value for s in Severity} else Severity.HIGH,
            confidence=entry.confidence,
            estimated_lead_time_impact_weeks=entry.lead_time_impact_weeks,
            estimated_price_impact_pct=entry.price_impact_pct,
            cross_validated=max(1, len(entry.sources)),
            is_active=1,
        )
        db.add(evt)
        created += 1

    db.commit()

    # 回扫所有活跃BOM
    scan_result = _rescan_all_active_boms(db)

    return {
        "status": "ok",
        "created": created,
        "updated": updated,
        "total_intel": len(MARKET_INTEL_ENTRIES),
        "active_events_now": db.query(MarketEvent).filter(MarketEvent.is_active == 1).count(),
        "bom_rescan": scan_result,
    }


@router.get("/match/{bom_item_id}")
def match_item_intel(bom_item_id: int, db: Session = Depends(get_db)):
    """查询单个物料的行情情报匹配结果"""
    item = db.query(BomItem).filter(BomItem.id == bom_item_id).first()
    if not item:
        return {"error": "BOM item not found"}

    engine = MarketIntelEngine()
    result = engine.match_item(
        raw_part_number=item.raw_part_number or "",
        raw_brand=item.raw_brand or "",
        raw_category=item.raw_category or "",
        raw_description=item.raw_description or "",
    )
    return {
        "bom_item_id": bom_item_id,
        "raw_part_number": item.raw_part_number,
        "raw_brand": item.raw_brand,
        "raw_category": item.raw_category,
        "matched": result.matched,
        "norm_category": result.category,
        "norm_brand": result.brand,
        "risk_level": result.risk_level,
        "lead_time_weeks": result.lead_time_weeks,
        "price_impact_pct": result.price_impact_pct,
        "summary": result.summary,
        "business_advice": result.business_advice,
        "intel_sources": result.intel_sources,
        "matched_intel_count": result.matched_intel_count,
    }


@router.get("/brand-risk")
def brand_risk_list():
    """返回当前高风险品牌列表"""
    from app.knowledge.market_intel import HIGH_RISK_BRANDS
    return {"high_risk_brands": HIGH_RISK_BRANDS}


@router.get("/category-risk")
def category_risk_list():
    """返回当前品类行情风险"""
    from app.knowledge.market_intel import CATEGORY_MARKET_RISK
    return {"category_market_risk": CATEGORY_MARKET_RISK}


@router.get("/events")
def list_intel_events(db: Session = Depends(get_db)):
    """列出所有由行情知识库生成的市场事件"""
    events = (
        db.query(MarketEvent)
        .filter(MarketEvent.source_name == "market_intel_kb", MarketEvent.is_active == 1)
        .order_by(MarketEvent.severity.desc(), MarketEvent.confidence.desc())
        .all()
    )
    return {
        "total": len(events),
        "events": [e.to_dict() for e in events],
    }


def _rescan_all_active_boms(db: Session) -> dict:
    """回扫所有活跃BOM，更新物料风险"""
    from app.services.bom_matcher import BOMMatcher

    active_events = db.query(MarketEvent).filter(MarketEvent.is_active == 1).all()
    if not active_events:
        return {"projects": 0, "items_updated": 0}

    matcher = BOMMatcher(active_events)
    engine = MarketIntelEngine()
    projects = db.query(BomProject).filter(BomProject.status == "active").all()
    total_updated = 0

    for project in projects:
        items = db.query(BomItem).filter(BomItem.bom_upload_id == project.id).all()
        project_red = project_yellow = project_green = project_gray = 0

        for item in items:
            # 事件匹配
            market_level, market_score, events, market_reason = matcher.match_item(item)

            # 行情情报匹配
            intel_result = engine.match_item(
                raw_part_number=item.raw_part_number or "",
                raw_brand=item.raw_brand or "",
                raw_category=item.raw_category or "",
                raw_description=item.raw_description or "",
            )

            # 合并风险等级：取两者中较高者
            from app.models.bom import RiskLevel
            level_order = {"red": 3, "yellow": 2, "green": 1, "gray": 0}

            final_level = market_level
            if intel_result.risk_level in level_order:
                if level_order.get(intel_result.risk_level, 0) > level_order.get(market_level.value if market_level else "gray", 0):
                    final_level = RiskLevel(intel_result.risk_level)

            # 合并原因
            reason_parts = [market_reason] if market_reason and market_reason != "未发现影响该物料的市场事件" else []
            if intel_result.summary and intel_result.summary not in " ".join(reason_parts):
                reason_parts.append(f"[行情情报] {intel_result.summary}")
            if intel_result.business_advice:
                reason_parts.append(f"[业务建议] {intel_result.business_advice}")

            final_reason = "；".join(reason_parts) if reason_parts else market_reason or ""
            final_score = max(float(market_score or 0), 50.0 if intel_result.matched else 0.0)

            item.risk_level = final_level
            item.risk_score = final_score
            item.risk_reason = final_reason
            item.procurement_suggestion = intel_result.business_advice or item.procurement_suggestion

            if final_level.value == "red": project_red += 1
            elif final_level.value == "yellow": project_yellow += 1
            elif final_level.value == "green": project_green += 1
            else: project_gray += 1

        project.items_analyzed = len(items)
        project.items_red = project_red
        project.items_yellow = project_yellow
        project.items_green = project_green
        project.items_gray = project_gray
        total_updated += len(items)

    db.commit()
    return {"projects": len(projects), "items_updated": total_updated}
