"""风险链路 API — 返回上游材料层级链、行情信号、BOM影响和策略建议。

从数据库实时统计 + 品类模板数据组合，供前端 MaterialChain 页面和仪表盘双轨看板使用。
"""

from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.bom import BomItem, BomProject
from app.models.event import MarketEvent
from app.knowledge.risk_chain_library import (
    ACTION_STRATEGY_TEMPLATES,
    BOM_IMPACT_TEMPLATES,
    CATEGORY_CHAIN_TEMPLATES,
    CATEGORY_FILTERS,
    MARKET_SIGNAL_TEMPLATES,
    source_link,
)
from app.services.upstream.evidence_chain_builder import (
    CATEGORY_UPSTREAM_CHAIN,
    CATEGORY_MODEL_WEIGHTS,
    DEMAND_DRIVEN_NOTE,
)
from sqlalchemy import text

# 数据库实际品类名 → 规范化品类key的映射
_DB_CATEGORY_MAP = {
    "pcb": "pcb", "PCB": "pcb",
    "mlcc": "mlcc", "MLCC": "mlcc",
    "resistor": "resistor", "Resistor": "resistor",
    "diode": "discrete_diode", "Diode": "discrete_diode",
    "electrolytic": "aluminum_electrolytic_capacitor", "Electrolytic": "aluminum_electrolytic_capacitor",
    "connector": "connector", "Connector": "connector",
    "relay": "relay", "Relay": "relay",
    "mcu": "mcu", "MCU": "mcu",
    "mosfet": "mosfet", "MOSFET": "mosfet",
    "igbt": "mosfet", "IGBT": "mosfet",
    "power": "power_ic", "Power": "power_ic",
    "analog": "analog_ic", "Analog": "analog_ic",
    "inductor": "inductor_transformer", "Inductor": "inductor_transformer",
    "transformer": "inductor_transformer", "Transformer": "inductor_transformer",
    "film": "film_capacitor", "Film": "film_capacitor",
    "fuse": "switch", "Fuse": "switch",
    "optocoupler": "discrete_diode", "Optocoupler": "discrete_diode",
    "eeprom": "memory", "EEPROM": "memory",
}


def _normalize_db_category(db_cat: str) -> str:
    """将数据库中的品类名映射到规范化品类key。"""
    if not db_cat:
        return "unknown"
    return _DB_CATEGORY_MAP.get(db_cat, db_cat.lower())


# ── 模板品类名 → DB规范化品类key 的映射 ──
_SIGNAL_CATEGORY_OVERRIDE = {
    "PCB/FPC": ["pcb"],
    "MLCC/被动件": ["mlcc", "high_cap_mlcc", "film_capacitor", "tantalum_capacitor", "resistor", "discrete_diode"],
    "IC/半导体": ["mcu", "power_ic", "mosfet", "analog_ic", "memory", "fpga_cpld", "discrete_diode", "power_module", "crystal_oscillator", "sensor"],
    "连接器/线缆": ["connector", "wire_harness", "relay", "switch"],
    "磁性件/电机": ["inductor_transformer"],
}

def _sev_rank(sev: str) -> int:
    return {"red": 4, "orange": 3, "yellow": 2, "green": 1}.get(sev, 0)

def _build_signal_index():
    idx = {}
    for sig in MARKET_SIGNAL_TEMPLATES:
        sev = sig.get("severity", "green")
        for tpl_cat in sig.get("linkedCategories", []):
            for cat_key in _SIGNAL_CATEGORY_OVERRIDE.get(tpl_cat, [tpl_cat]):
                if cat_key not in idx or _sev_rank(sev) > _sev_rank(idx[cat_key]):
                    idx[cat_key] = sev
    return idx

_SIGNAL_RISK_INDEX = _build_signal_index()

router = APIRouter(prefix="/api/risk-chain", tags=["risk-chain"])

SourceLevel = Literal["S", "A", "B", "C"]
RiskLevel = Literal["red", "orange", "yellow", "green"]
SignalType = Literal["price", "shortage", "tariff", "trade", "ban", "disaster", "strike", "shutdown"]
StrategyType = Literal["price", "lead_time", "alternative", "trade", "watch"]
Priority = Literal["P0", "P1", "P2"]
OwnerRole = Literal["采购", "研发", "项目经理", "供应链"]


class RiskChainSummary(BaseModel):
    highRiskBomCount: int = 0
    affectedItemCount: int = 0
    affectedCategoryCount: int = 0
    highConfidenceSignalCount: int = 0
    pendingActionCount: int = 0
    categoryCoverageCount: int = 0


class CategoryFilter(BaseModel):
    key: str
    label: str


class SourceLink(BaseModel):
    id: str
    sourceName: str
    sourceLevel: SourceLevel
    sourceType: str
    url: str
    summary: str


class MarketSignal(BaseModel):
    id: str
    group: str = "all"
    title: str
    signalType: SignalType
    severity: RiskLevel
    sourceName: str
    sourceLevel: SourceLevel
    sourceType: str
    sourceUrl: str
    confidenceScore: int = Field(ge=0, le=100)
    occurredAt: str
    summary: str
    linkedMaterials: list[str]
    linkedCategories: list[str]


class MaterialNode(BaseModel):
    name: str
    materialType: str
    riskLevel: RiskLevel
    evidence: str
    priceChangeText: str
    confidenceScore: int = Field(ge=0, le=100)


class MaterialChain(BaseModel):
    id: str
    group: str = "all"
    category: str
    title: str
    summary: str
    nodes: list[MaterialNode]
    sourceLinks: list[SourceLink]


class BomImpact(BaseModel):
    id: str
    group: str = "all"
    bomProjectName: str
    itemCode: str
    itemName: str
    category: str
    riskLevel: RiskLevel
    priceImpactText: str
    leadTimeImpactText: str
    reasonSummary: str
    linkedSignalIds: list[str]
    linkedMaterials: list[str]
    suggestedStrategyIds: list[str]
    impactBreakdown: dict[str, str] = Field(default_factory=dict)


class ActionStrategy(BaseModel):
    id: str
    group: str = "all"
    strategyType: StrategyType
    priority: Priority
    title: str
    detail: str
    ownerRole: OwnerRole
    triggerReason: str
    expectedEffect: str


class RiskChainDashboard(BaseModel):
    summary: RiskChainSummary
    categoryFilters: list[CategoryFilter]
    signals: list[MarketSignal]
    materialChains: list[MaterialChain]
    bomImpacts: list[BomImpact]
    strategies: list[ActionStrategy]


def _build_dashboard_signal(template: dict) -> MarketSignal:
    source = source_link(template["sourceId"])
    return MarketSignal(
        id=template["id"],
        group=template.get("group", "all"),
        title=template["title"],
        signalType=template["signalType"],
        severity=template["severity"],
        sourceName=source["sourceName"],
        sourceLevel=source["sourceLevel"],
        sourceType=source["sourceType"],
        sourceUrl=source["url"],
        confidenceScore=template["confidenceScore"],
        occurredAt=template["occurredAt"],
        summary=template["summary"],
        linkedMaterials=template["linkedMaterials"],
        linkedCategories=template["linkedCategories"],
    )


def _build_dashboard_chain(template: dict) -> MaterialChain:
    return MaterialChain(
        id=template["id"],
        group=template.get("group", "all"),
        category=template["category"],
        title=template["title"],
        summary=template["summary"],
        nodes=template["nodes"],
        sourceLinks=[source_link(source_id) for source_id in template.get("sourceIds", [])],
    )


def _dashboard_summary() -> RiskChainSummary:
    high_risk_count = sum(1 for impact in BOM_IMPACT_TEMPLATES if impact["riskLevel"] in {"red", "orange"})
    affected_categories = {impact["category"] for impact in BOM_IMPACT_TEMPLATES}
    high_confidence_signals = sum(1 for signal in MARKET_SIGNAL_TEMPLATES if signal["confidenceScore"] >= 85)
    pending_actions = sum(1 for strategy in ACTION_STRATEGY_TEMPLATES if strategy["priority"] in {"P0", "P1"})
    covered_groups = {chain["group"] for chain in CATEGORY_CHAIN_TEMPLATES}
    return RiskChainSummary(
        highRiskBomCount=high_risk_count,
        affectedItemCount=len(BOM_IMPACT_TEMPLATES),
        affectedCategoryCount=len(affected_categories),
        highConfidenceSignalCount=high_confidence_signals,
        pendingActionCount=pending_actions,
        categoryCoverageCount=len(covered_groups),
    )


@router.get("/dashboard", response_model=RiskChainDashboard)
def get_risk_chain_dashboard() -> RiskChainDashboard:
    """返回多电子物料类别风险链路驾驶舱数据。"""
    return RiskChainDashboard(
        summary=_dashboard_summary(),
        categoryFilters=CATEGORY_FILTERS,
        signals=[_build_dashboard_signal(signal) for signal in MARKET_SIGNAL_TEMPLATES],
        materialChains=[_build_dashboard_chain(chain) for chain in CATEGORY_CHAIN_TEMPLATES],
        bomImpacts=BOM_IMPACT_TEMPLATES,
        strategies=ACTION_STRATEGY_TEMPLATES,
    )


def _category_item_stats(db: Session) -> dict:
    """统计各品类的 BOM 物料数和风险分布。
    将数据库原始品类名通过映射表规范化后聚合。"""
    rows = db.execute(text(
        "SELECT normalized_category, COUNT(*) as cnt, "
        "SUM(CASE WHEN risk_level='red' THEN 1 ELSE 0 END) as red, "
        "SUM(CASE WHEN risk_level='orange' THEN 1 ELSE 0 END) as orange, "
        "SUM(CASE WHEN risk_level='yellow' THEN 1 ELSE 0 END) as yellow, "
        "SUM(CASE WHEN risk_level='green' THEN 1 ELSE 0 END) as green "
        "FROM bom_items WHERE normalized_category IS NOT NULL AND normalized_category != '' "
        "GROUP BY normalized_category"
    )).fetchall()
    stats = {}
    for row in rows:
        cat_key = _normalize_db_category(row[0])
        if cat_key == "unknown":
            continue
        if cat_key not in stats:
            stats[cat_key] = {"total": 0, "red": 0, "orange": 0, "yellow": 0, "green": 0}
        stats[cat_key]["total"] += row[1]
        stats[cat_key]["red"] += row[2] or 0
        stats[cat_key]["orange"] += row[3] or 0
        stats[cat_key]["yellow"] += row[4] or 0
        stats[cat_key]["green"] += row[5] or 0
    return stats


def _category_project_count(db: Session) -> dict:
    """统计各品类影响的 BOM 项目数。"""
    rows = db.execute(text(
        "SELECT normalized_category, COUNT(DISTINCT bom_upload_id) "
        "FROM bom_items WHERE normalized_category IS NOT NULL AND normalized_category != '' "
        "GROUP BY normalized_category"
    )).fetchall()
    result = {}
    for row in rows:
        cat_key = _normalize_db_category(row[0])
        if cat_key == "unknown":
            continue
        result[cat_key] = result.get(cat_key, 0) + (row[1] or 0)
    return result


def _active_events(db: Session, limit: int = 30) -> list:
    """获取活跃市场事件。"""
    events = db.query(MarketEvent).filter(
        MarketEvent.is_active == True
    ).order_by(MarketEvent.created_at.desc()).limit(limit).all()
    return [
        {
            "id": e.id,
            "title": getattr(e, "raw_title", "") or "",
            "brand": getattr(e, "brand", ""),
            "category": getattr(e, "category", ""),
            "event_type": getattr(e, "event_type", ""),
            "severity": getattr(e, "severity", ""),
            "source_name": getattr(e, "source_name", ""),
            "confidence": getattr(e, "confidence", 0),
            "estimated_price_impact_pct": getattr(e, "estimated_price_impact_pct", None),
            "estimated_lead_time_impact_weeks": getattr(e, "estimated_lead_time_impact_weeks", None),
            "created_at": str(getattr(e, "created_at", "")),
        }
        for e in events
    ]


def _build_chain_view(category_key: str, category_stats: dict, proj_counts: dict, events: list) -> dict:
    """构建单个品类的完整链路视图。"""
    template = CATEGORY_UPSTREAM_CHAIN.get(category_key, {})
    model = CATEGORY_MODEL_WEIGHTS.get(category_key, {"material": 0.4, "demand_supply": 0.6, "display": category_key})
    stats = category_stats.get(category_key, {})

    total = stats.get("total", 0)
    high_risk = stats.get("red", 0) + stats.get("orange", 0)

    # 品类级风险等级 — 优先用模板信号（用户确认的真实行情），其次用DB统计
    db_max_sev = "red" if stats.get("red", 0) > 0 else \
                 "orange" if stats.get("orange", 0) > 0 else \
                 "yellow" if stats.get("yellow", 0) > 0 else \
                 "green" if total > 0 else "gray"

    # 从模板信号获取该品类的行情风险等级（已通过_SIGNAL_CATEGORY_OVERRIDE展开）
    template_sev = _SIGNAL_RISK_INDEX.get(category_key, "green")

    # 取模板信号和DB统计中较高的风险等级
    risk_level = template_sev if _sev_rank(template_sev) > _sev_rank(db_max_sev) else db_max_sev

    # 该品类的行情事件（DB实际事件 + 模板信号）
    category_events = [e for e in events if e.get("category") == category_key]
    # 注入模板信号为该品类的行情依据
    template_signals_for_cat = []
    for sig in MARKET_SIGNAL_TEMPLATES:
        linked = sig.get("linkedCategories", [])
        matched_keys = []
        for tpl_cat in linked:
            mapped = _SIGNAL_CATEGORY_OVERRIDE.get(tpl_cat, [tpl_cat])
            matched_keys.extend(mapped)
        if category_key in matched_keys:
            template_signals_for_cat.append({
                "title": sig["title"],
                "source_name": sig.get("sourceId", ""),
                "severity": sig["severity"],
                "event_type": sig.get("signalType", ""),
                "created_at": sig.get("occurredAt", ""),
                "confidence": sig.get("confidenceScore", 0) / 100.0,
                "estimated_price_impact_pct": None,
                "estimated_lead_time_impact_weeks": None,
            })
    # 合并：模板信号优先显示
    seen_titles = {e.get("title", "") for e in category_events}
    for ts in template_signals_for_cat:
        if ts["title"] not in seen_titles:
            category_events.insert(0, ts)

    # 该品类的 BOM 物料样本
    bom_items = []
    if total > 0:
        # 取风险最高的前5个物料
        from app.database import SessionLocal
        db_sample = SessionLocal()
        try:
            # 反向映射：规范化key → 可能的DB品类名列表
            db_cats = [k for k, v in _DB_CATEGORY_MAP.items() if v == category_key]
            if not db_cats:
                db_cats = [category_key]
            placeholders = ", ".join([f":cat{i}" for i in range(len(db_cats))])
            params = {f"cat{i}": c for i, c in enumerate(db_cats)}
            items = db_sample.execute(text(
                f"SELECT raw_part_number, raw_brand, bom_upload_id, risk_level "
                f"FROM bom_items WHERE normalized_category IN ({placeholders}) AND risk_level IN ('red','orange','yellow') "
                f"ORDER BY CASE risk_level WHEN 'red' THEN 1 WHEN 'orange' THEN 2 ELSE 3 END LIMIT 5"
            ), params).fetchall()
            for item in items:
                proj = db_sample.query(BomProject).filter(BomProject.id == item[2]).first()
                bom_items.append({
                    "mpn": item[0] or "未知型号",
                    "brand": item[1] or "",
                    "project_name": proj.project_name if proj else "",
                    "project_id": item[2],
                    "risk_level": item[3],
                })
        finally:
            db_sample.close()

    # AI 判断 — 优先反映模板信号（用户确认的真实行情）
    if risk_level == "red":
        sig_for_cat = [s for s in MARKET_SIGNAL_TEMPLATES if s["severity"] == "red" and category_key in [
            mk for tpl_cat in s.get("linkedCategories", []) for mk in _SIGNAL_CATEGORY_OVERRIDE.get(tpl_cat, [tpl_cat])
        ]]
        if sig_for_cat:
            ai = f"⚠️ 已确认高风险：{sig_for_cat[0]['title']}。{sig_for_cat[0]['summary'][:200]}。建议立即启动应急采购方案。"
        else:
            ai = f"{model['display']}当前为高风险，BOM命中{total}个物料（高{high_risk}个），建议优先处理。"
    elif risk_level == "orange":
        if model["material"] > model["demand_supply"]:
            ai = f"{model['display']}为成本驱动型品类，材料传导可靠性{template.get('reliability','unknown')}，预计滞后{template.get('lag','未知')}。当前{high_risk}个物料中高风险，建议关注。"
        else:
            ai = f"{model['display']}以供需信号为主，建议跟踪交期、库存和供应商动态。"
    elif risk_level == "yellow":
        ai = f"{model['display']}当前为关注级别，建议纳入观察池跟踪。"
    elif total == 0:
        ai = f"{model['display']}暂无BOM命中数据。"
    else:
        ai = f"{model['display']}当前风险较低。"
    if category_key in DEMAND_DRIVEN_NOTE and risk_level not in ("red",):
        ai += " " + DEMAND_DRIVEN_NOTE[category_key]

    return {
        "category_key": category_key,
        "display_name": model["display"],
        "driver_type": "material_cost" if model["material"] > 0.5 else "demand_supply" if model["demand_supply"] > 0.5 else "hybrid",
        "risk_level": risk_level,
        "total_items": total,
        "high_risk_items": high_risk,
        "project_count": proj_counts.get(category_key, 0),
        "material_weight": model["material"],
        "demand_supply_weight": model["demand_supply"],
        "pass_through": template.get("pass_through", ""),
        "lag": template.get("lag", ""),
        "reliability": template.get("reliability", "unknown"),
        "note": template.get("note", ""),
        # 层级节点
        "raw_materials": [
            {
                "name": rm["name"],
                "data_level": rm.get("data_level", "C"),
                "source": rm.get("source", ""),
                "signal_key": rm.get("signal_key", ""),
            }
            for rm in template.get("raw_materials", [])
        ],
        "mid_components": [
            {
                "name": mc["name"],
                "from": mc.get("from", ""),
                "cost_share": mc.get("cost_share", ""),
            }
            for mc in template.get("mid_components", [])
        ],
        # 行情事件
        "market_events": category_events[:5],
        # BOM物料
        "bom_items": bom_items,
        # AI判断
        "ai_judgement": ai,
        # 建议
        "suggestions": _build_suggestions(category_key, risk_level, model["display"]),
    }


def _build_suggestions(category_key: str, risk_level: str, display_name: str) -> list:
    """生成处置建议。"""
    suggestions = []
    if risk_level in ("red", "orange"):
        suggestions.append({"urgency": "urgent", "text": f"立即复核{display_name}的供应商报价、交期和安全库存覆盖周期"})
        suggestions.append({"urgency": "urgent", "text": f"评估{display_name}替代料方案，降低单一品牌/规格依赖"})
    if risk_level in ("red", "orange", "yellow"):
        if category_key not in DEMAND_DRIVEN_NOTE:
            suggestions.append({"urgency": "watch", "text": "跟踪上游材料价格趋势，关注供应商调价窗口"})
        suggestions.append({"urgency": "watch", "text": "将高风险物料纳入定期巡检范围"})
    return suggestions


@router.get("/material-chain")
def get_material_chain(
    category: str | None = Query(None, description="按品类过滤"),
    db: Session = Depends(get_db),
):
    """返回完整的材料链路数据（所有品类或指定品类）。

    前端 MaterialChain.vue 使用此端点替代硬编码模板。
    """
    cat_stats = _category_item_stats(db)
    proj_counts = _category_project_count(db)
    events = _active_events(db)

    # 构建所有品类的链路
    all_chains = []
    categories_to_build = [category] if category else list(CATEGORY_UPSTREAM_CHAIN.keys())

    for cat_key in categories_to_build:
        chain = _build_chain_view(cat_key, cat_stats, proj_counts, events)
        all_chains.append(chain)

    # 按风险等级排序（红→橙→黄→绿→灰）
    risk_order = {"red": 0, "orange": 1, "yellow": 2, "green": 3, "gray": 4}
    all_chains.sort(key=lambda c: (risk_order.get(c["risk_level"], 9), -c["high_risk_items"]))

    return {
        "chains": all_chains,
        "total_categories": len(all_chains),
        "total_items": sum(c["total_items"] for c in all_chains),
        "total_high_risk": sum(c["high_risk_items"] for c in all_chains),
    }


@router.get("/material-chain/by-material")
def get_material_chain_by_material(db: Session = Depends(get_db)):
    """按原材料视角返回传导链路（铜→PCB/连接器/电感，银→继电器 等）。"""
    cat_stats = _category_item_stats(db)
    proj_counts = _category_project_count(db)

    # 原材料 → 受影响品类的聚合
    material_map = {}
    for cat_key, template in CATEGORY_UPSTREAM_CHAIN.items():
        model = CATEGORY_MODEL_WEIGHTS.get(cat_key, {})
        stats = cat_stats.get(cat_key, {})
        for rm in template.get("raw_materials", []):
            mat_name = rm["name"]
            if mat_name not in material_map:
                material_map[mat_name] = {
                    "material_name": mat_name,
                    "data_level": rm.get("data_level", "C"),
                    "source": rm.get("source", ""),
                    "affected_categories": [],
                }
            material_map[mat_name]["affected_categories"].append({
                "category_key": cat_key,
                "display_name": model.get("display", cat_key),
                "total_items": stats.get("total", 0),
                "high_risk_items": stats.get("red", 0) + stats.get("orange", 0),
                "project_count": proj_counts.get(cat_key, 0),
                "reliability": template.get("reliability", "unknown"),
                "pass_through": template.get("pass_through", ""),
                "lag": template.get("lag", ""),
            })

    return {
        "materials": list(material_map.values()),
    }


@router.get("/material-chain/by-project")
def get_material_chain_by_project(db: Session = Depends(get_db)):
    """按BOM项目视角返回材料风险总览。"""
    projects = db.query(BomProject).filter(BomProject.status == "active").all()
    result = []
    for proj in projects:
        items = db.execute(text(
            "SELECT normalized_category, risk_level FROM bom_items "
            "WHERE bom_upload_id = :pid AND normalized_category IS NOT NULL AND normalized_category != ''"
        ), {"pid": proj.id}).fetchall()
        if not items:
            continue

        # 统计项目内品类分布（规范化key后聚合）
        cat_set = {}
        for item in items:
            cat = _normalize_db_category(item[0])
            level = item[1]
            if cat == "unknown":
                continue
            if cat not in cat_set:
                cat_set[cat] = {"red": 0, "orange": 0, "yellow": 0, "green": 0}
            if level in cat_set[cat]:
                cat_set[cat][level] += 1

        if not cat_set:
            continue

        # 总体风险
        has_red = any(c["red"] > 0 for c in cat_set.values())
        has_orange = any(c["orange"] > 0 for c in cat_set.values())
        overall = "red" if has_red else "orange" if has_orange else "green"

        # 材料暴露
        mat_exposures = set()
        supply_exposures = set()
        for cat_key in cat_set:
            model = CATEGORY_MODEL_WEIGHTS.get(cat_key, {})
            if model.get("material", 0.4) > model.get("demand_supply", 0.4):
                mat_exposures.add(model.get("display", cat_key))
            else:
                supply_exposures.add(model.get("display", cat_key))

        result.append({
            "id": proj.id,
            "name": proj.project_name,
            "overall_risk": overall,
            "item_count": len(items),
            "red_count": sum(c["red"] for c in cat_set.values()),
            "orange_count": sum(c["orange"] for c in cat_set.values()),
            "yellow_count": sum(c["yellow"] for c in cat_set.values()),
            "material_exposures": list(mat_exposures),
            "supply_exposures": list(supply_exposures),
        })

    return {"projects": result}
