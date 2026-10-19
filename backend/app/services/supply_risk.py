"""供应链交期与EOL风险评估（v3 — 集成实时数据源）。

改进：
- 优先使用 SupplyDataService 从 LCSC/Mouser API 获取的真实交期/库存/生命周期数据
- 降级策略：API 数据不可用时，fallback 到原有的品类启发式规则
- 增加了通用性评分（标准封装+主流品牌+多货源）
- 增加了价格趋势检测（需要至少两次快照对比）
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from app.models.event import EventType, MarketEvent
from app.models.bom import RiskLevel


@dataclass
class SupplyRiskResult:
    production_risk_level: str
    production_risk_score: float
    lead_time_risk_weeks: Optional[int]
    eol_status: str
    supply_risk_tags: str
    supply_risk_reason: str
    procurement_suggestion: str
    # v3 新增字段
    total_stock: int = 0
    supplier_count: int = 0
    lead_time_days: Optional[int] = None
    unit_price: Optional[float] = None
    lifecycle_status: str = "Unknown"
    commonality_score: int = 0       # 通用性评分 0-100


# === 品类长交期启发式（API fallback） ===
_LONG_LEAD_CATEGORY_WEEKS = {
    "MCU": 16, "Power": 12, "MOSFET": 10, "IGBT": 16,
    "Connector": 8, "MLCC": 8, "Tantalum": 10, "Crystal": 8,
    "Optocoupler": 10, "PCB": 4,
}

# === EOL 关键词 ===
_HIGH_RISK_EOL_KEYS = (
    "eol", "end of life", "obsolete", "停产", "停供", "退市",
    "不推荐新设计", "nrnd", "last time buy", "ltb", "终止供货", "生命周期终止",
)

_LEAD_TIME_KEYS = (
    "lead time", "交期", "货期", "排产", "缺货", "shortage",
    "allocation", "产能", "紧缺",
)

_CRITICAL_BRAND_KEYS = (
    "st", "ti", "infineon", "英飞凌", "nxp", "onsemi", "on semiconductor",
    "adi", "analog", "microchip", "renesas", "瑞萨", "murata", "村田", "tdk",
)

# === 标准封装列表（通用性评分依据） ===
_STANDARD_PACKAGES = {
    "0402", "0603", "0805", "1206", "1210", "1812", "2010", "2512",  # 阻容
    "sot-23", "sot-23-5", "sot-23-6", "sot-89", "sot-223",           # SOT
    "soic-8", "soic-14", "soic-16", "tssop-8", "tssop-14",           # SOIC
    "qfn-16", "qfn-20", "qfn-24", "qfn-32",                          # QFN
    "to-220", "to-252", "to-263",                                     # TO
    "sod-123", "sod-323", "sod-523", "sma", "smb", "smc",            # 二极管
    "0805", "ll-34", "mini-melf",                                     # 二极管
}


def evaluate_supply_risk(
    item,
    matched_events: Iterable[MarketEvent],
    realtime_data: dict | None = None,
    commonality_data: dict | None = None,
) -> SupplyRiskResult:
    """综合评估物料供应链风险。

    Args:
        item: BomItem 对象（含 raw_*/normalized_* 字段）
        matched_events: 市场事件匹配结果
        realtime_data: 实时 API 查询结果 dict，包含:
            - total_stock, supplier_count, lead_time_days
            - unit_price, lifecycle_status
        commonality_data: 通用性评估 dict，包含:
            - is_standard_package, is_major_brand, has_multi_source

    Returns:
        SupplyRiskResult 含风险等级、评分、原因、建议
    """
    events = list(matched_events or [])
    text = _item_text(item)
    norm_category = item.normalized_category or item.raw_category or ""
    norm_brand = item.normalized_brand or item.raw_brand or ""
    rd = realtime_data or {}
    cd = commonality_data or {}

    tags: list[str] = []
    reasons: list[str] = []
    suggestions: list[str] = []

    total_stock = rd.get("total_stock", 0)
    supplier_count = rd.get("supplier_count", 0)
    lead_time_days = rd.get("lead_time_days")
    lifecycle_status = rd.get("lifecycle_status", "Unknown")
    unit_price = rd.get("unit_price")

    eol_status = "none"
    score = 0.0

    # ============================================================
    # 1. 生命周期风险（最高优先级）
    # ============================================================
    lifecycle_lower = lifecycle_status.lower()

    if lifecycle_lower in ("obsolete", "eol"):
        eol_status = "confirmed"
        tags.append("EOL/停产")
        reasons.append(f"数据源返回生命周期状态: {lifecycle_status}，该物料已停产")
        suggestions.append("立即启动替代料评估，确认 Last Time Buy 窗口")
        score = max(score, 100)

    elif lifecycle_lower in ("nrnd", "not recommended", "last time buy"):
        eol_status = "confirmed"
        tags.append("EOL/NRND")
        reasons.append(f"数据源返回生命周期状态: {lifecycle_status}，不应用于新设计")
        suggestions.append("即使是现有项目也建议尽快启动替代方案")
        score = max(score, 90)

    elif lifecycle_lower == "active":
        eol_status = "none"

    # 市场事件中的 EOL 信号
    for evt in events:
        evt_type = _enum_value(evt.event_type)
        severity = _enum_value(evt.severity)
        evt_text = " ".join([evt.raw_title or "", evt.raw_text or "", evt_type or ""]).lower()
        evt_score = _severity_score(severity) * float(evt.confidence or 0.5)

        if evt.event_type == EventType.EOL or _contains_any(evt_text, _HIGH_RISK_EOL_KEYS):
            if eol_status != "confirmed":
                eol_status = "suspected"
            tags.append("EOL/停产(事件)")
            reasons.append(f"命中EOL/停产类事件：{evt.brand or ''} {evt.category or ''}".strip())
            suggestions.append("立即确认原厂生命周期状态")
            score = max(score, evt_score + 20)

    # BOM 文本中的 EOL 关键词
    if _contains_any(text.lower(), _HIGH_RISK_EOL_KEYS):
        if eol_status == "none":
            eol_status = "suspected"
        tags.append("疑似EOL")
        reasons.append("BOM描述/备注中出现EOL、NRND、停产或LTB关键词")
        suggestions.append("要求供应商提供原厂PCN/PDN证明")
        score = max(score, 80)

    # ============================================================
    # 2. 交期风险（优先用 API 数据，fallback 品类启发式）
    # ============================================================
    effective_lead_days = lead_time_days

    # Fallback: 品类长交期启发式
    if effective_lead_days is None and norm_category in _LONG_LEAD_CATEGORY_WEEKS:
        effective_lead_days = _LONG_LEAD_CATEGORY_WEEKS[norm_category] * 7
        tags.append("品类长交期(估算)")
        reasons.append(f"{norm_category}属于常见长交期品类，按{_LONG_LEAD_CATEGORY_WEEKS[norm_category]}周评估")
        suggestions.append("关键料建议建立安全库存")

    if effective_lead_days is not None:
        if effective_lead_days > 84:
            tags.append("交期>12周")
            reasons.append(f"交期{effective_lead_days}天(>12周)，严重影响排产")
            suggestions.append("优先询价现货/锁单，评估替代料")
            score = max(score, 95)
        elif effective_lead_days > 56:
            tags.append("交期8-12周")
            reasons.append(f"交期{effective_lead_days}天(8-12周)，需提前备货")
            suggestions.append("确认供应商承诺交期，备安全库存")
            score = max(score, 75)
        elif effective_lead_days > 28:
            tags.append("交期4-8周")
            reasons.append(f"交期{effective_lead_days}天(4-8周)")
            score = max(score, 40)
        else:
            reasons.append(f"交期{effective_lead_days}天，正常范围")

    # 市场事件驱动的交期信号
    for evt in events:
        evt_type = _enum_value(evt.event_type)
        severity = _enum_value(evt.severity)
        evt_text = " ".join([evt.raw_title or "", evt.raw_text or "", evt_type or ""]).lower()
        evt_score = _severity_score(severity) * float(evt.confidence or 0.5)

        if evt_type in ("lead_time", "shortage", "capacity_issue") or _contains_any(evt_text, _LEAD_TIME_KEYS):
            impact = evt.estimated_lead_time_impact_weeks or 0
            if impact and (effective_lead_days is None or impact * 7 > effective_lead_days):
                effective_lead_days = impact * 7
            tags.append("交期/排产(事件)")
            reasons.append(f"命中交期/缺货/产能事件：预计影响约{effective_lead_days // 7 if effective_lead_days else '?'}周")
            suggestions.append("排产前确认供应商承诺交期")
            score = max(score, evt_score + 10)

    # ============================================================
    # 3. 库存风险（仅在确认数据源已命中时生效，避免把"未查到"误判为"零库存"）
    # ============================================================
    _is_available = rd.get("is_available", False)
    if rd and _is_available:
        if total_stock == 0:
            tags.append("零库存")
            reasons.append("所有渠道均无现货库存")
            suggestions.append("确认工厂交期和最小起订量，评估替代型号")
            score = max(score, 80)
        elif supplier_count == 1 and total_stock > 0:
            tags.append("单一货源")
            reasons.append(f"仅1个渠道有现货，共{total_stock}个")
            suggestions.append("开发第二货源，降低断供风险")
            score = max(score, 55)

    # ============================================================
    # 4. 供应商集中度
    # ============================================================
    if supplier_count == 1:
        tags.append("单供应商")
        reasons.append("可用的独立供应商仅1家，供应中断风险高")
        score = max(score, 60)
    elif supplier_count == 2:
        tags.append("双供应商")
        reasons.append("2家供应商，风险可控但建议继续开发备选")
        score = max(score, 30)
    elif supplier_count >= 3:
        reasons.append(f"{supplier_count}家供应商可供应，供货渠道充足")

    # ============================================================
    # 5. 关键品牌+核心品类
    # ============================================================
    if norm_category in ("MCU", "Power", "MOSFET", "IGBT"):
        if _contains_any(norm_brand.lower(), _CRITICAL_BRAND_KEYS):
            tags.append("关键品牌+核心品类")
            reasons.append("关键半导体品牌+核心品类，排产前需单独确认可得性")
            suggestions.append("对关键IC建立AVL替代清单")
            score = max(score, 55)
        elif norm_brand:
            reasons.append(f"{norm_category}品类排产前建议确认可得性")

    # ============================================================
    # 6. 价格风险（事件涨价 + 如有历史快照）
    # ============================================================
    for evt in events:
        evt_type = _enum_value(evt.event_type)
        severity = _enum_value(evt.severity)
        evt_text = " ".join([evt.raw_title or "", evt.raw_text or "", evt_type or ""]).lower()
        if evt_type == "price_increase" or _contains_any(evt_text, ("涨价", "提价", "price increase", "increase price")):
            impact = evt.estimated_price_impact_pct or 0
            tags.append("涨价预警")
            if impact:
                reasons.append(f"命中涨价事件：{evt.brand or ''} {evt.category or ''}预计涨幅约{impact:g}%".strip())
            else:
                reasons.append(f"命中涨价事件：{evt.brand or ''} {evt.category or ''}".strip())
            suggestions.append("排产前锁价/锁单，复核替代品牌和安全库存")
            event_score = _severity_score(severity) * float(evt.confidence or 0.5)
            if impact >= 15:
                score = max(score, event_score + 20)
            elif impact >= 10:
                score = max(score, event_score + 10, 55)
            else:
                score = max(score, event_score, 45)

    if unit_price and unit_price > 0:
        reasons.append(f"参考单价: {unit_price}")

    # ============================================================
    # 7. 通用性评分（物料标准化程度）
    # ============================================================
    commonality_score = _calc_commonality(item, cd)
    if commonality_score < 40:
        tags.append("非标物料")
        reasons.append(f"通用性评分{commonality_score}，该物料标准化程度低")
        suggestions.append("评估是否可用标准物料替代")
        score = max(score, 45)
    elif commonality_score >= 70:
        reasons.append(f"标准化程度高(通用性评分{commonality_score})")
    else:
        reasons.append(f"标准化程度一般(通用性评分{commonality_score})")

    # ============================================================
    # 8. 多品牌处理
    # ============================================================
    if not norm_brand and (item.raw_brand or ""):
        tags.append("多品牌/未锁定")
        reasons.append("品牌字段为多品牌或未锁定真实制造商")
        suggestions.append("下单前锁定最终制造商品牌和MPN")
        score = max(score, 35)

    # ============================================================
    # 综合判定
    # ============================================================
    score = min(round(score, 1), 100.0)
    level = _score_to_level(score, eol_status)

    if not reasons:
        reasons.append("未发现明确风险信号")
        suggestions.append("按常规采购流程确认价格、MOQ、交期和替代料")

    return SupplyRiskResult(
        production_risk_level=level.value,
        production_risk_score=score,
        lead_time_risk_weeks=effective_lead_days // 7 if effective_lead_days else None,
        eol_status=eol_status,
        supply_risk_tags=",".join(dict.fromkeys(tags)),
        supply_risk_reason="；".join(dict.fromkeys(reasons)),
        procurement_suggestion="；".join(dict.fromkeys(suggestions)),
        total_stock=total_stock,
        supplier_count=supplier_count,
        lead_time_days=effective_lead_days,
        unit_price=unit_price,
        lifecycle_status=lifecycle_status,
        commonality_score=commonality_score,
    )


def _calc_commonality(item, cd: dict) -> int:
    """计算物料通用性评分（0-100）。
    维度：标准封装 + 主流品牌 + 多货源 + 基础物料标记
    """
    score = 50  # 基础分

    raw_spec = (item.raw_spec or "").lower()
    if cd.get("is_standard_package", is_standard_package(raw_spec)):
        score += 15
    if cd.get("is_major_brand", False):
        score += 15
    if cd.get("has_multi_source", False):
        score += 15
    if cd.get("is_basic_part", False):
        score += 5

    return min(score, 100)


def is_standard_package(spec: str) -> bool:
    """从规格文本推断是否是标准封装（v3.3: 公开接口）。"""
    if not spec:
        return False
    spec_lower = spec.lower()
    return any(pkg in spec_lower for pkg in _STANDARD_PACKAGES)


# === 工具函数 ===
def _item_text(item) -> str:
    return " ".join(
        str(v or "")
        for v in (
            item.raw_part_number, item.raw_description,
            item.raw_brand, item.raw_category, item.raw_spec,
            item.normalized_brand, item.normalized_category,
        )
    )


def _contains_any(text: str, keys: Iterable[str]) -> bool:
    return any(k.lower() in text for k in keys)


def _enum_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value or "")


def _severity_score(severity: str) -> float:
    return {
        "critical": 95, "high": 78, "medium": 55,
        "low": 30, "unknown": 35,
    }.get(severity, 35)


def _base_lead_time_weeks(category: str) -> Optional[int]:
    return _LONG_LEAD_CATEGORY_WEEKS.get(category)


def _score_to_level(score: float, eol_status: str) -> RiskLevel:
    if eol_status == "confirmed" or score >= 75:
        return RiskLevel.RED
    if eol_status == "suspected" or score >= 40:
        return RiskLevel.YELLOW
    if score > 0:
        return RiskLevel.GREEN
    return RiskLevel.GRAY
