"""
自动提级规则引擎 (T2-007)

实现7条自动提级规则，对多因子风险评估结果进行二次评估。
核心原则: 只升不降 — 提级操作永远不会降低风险等级（除非人工干预）。

规则列表:
    R1: S级来源(BIS/USTR/USGS)出现出口管制/实体清单/关税变化 → 直接提升至橙色或红色
    R2: 原厂PCN/EOL/LTB命中BOM型号 → 直接提升至橙色，若无替代料则红色
    R3: 关键材料7日涨幅超过阈值且命中高用量BOM → 提升一级
    R4: 供应商所在地出现GDACS Red级灾害事件 → 提升一级并标记区域风险
    R5: 分销库存低于安全库存且交期拉长>50% → 提升至橙色
    R6: 单一品牌/单一供应商且无替代料 → 至少黄色，叠加事件后橙色
    R7: 数据缺失但BOM关键度高 → 显示灰色待确认

设计要点:
    - 与 MultiFactorRiskResult 完全兼容
    - 每条规则可独立开关
    - 提级结果可追溯（显示由哪条规则触发）
    - 提级不会降级（只升不降）
    - 风险等级有序: gray < green < yellow < orange < red
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.models.risk_assessment import (
    FactorScore,
    MultiFactorRiskResult,
    RiskLevel,
)
from app.services.upstream.propagation_rules import (
    ESCALATION_RULE_ENABLED,
    ESCALATION_RULES_CONFIG,
    INVENTORY_SAFETY_MULTIPLIER,
    LEAD_TIME_INCREASE_THRESHOLD,
    LIFECYCLE_ESCALATION_TRIGGERS,
    PRICE_SURGE_THRESHOLDS,
    S_LEVEL_POLICY_SOURCES,
    EscalationRuleConfig,
    is_rule_enabled,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 风险等级排序 (用于 "只升不降" 判断)
# ═══════════════════════════════════════════════════════════════════════════════

RISK_LEVEL_ORDER: dict[str, int] = {
    "gray": 0,
    "green": 1,
    "yellow": 2,
    "orange": 3,
    "red": 4,
}


def risk_level_ge(level_a: str, level_b: str) -> bool:
    """判断风险等级 level_a 是否 >= level_b。

    Args:
        level_a: 风险等级A
        level_b: 风险等级B

    Returns:
        bool: level_a >= level_b
    """
    return RISK_LEVEL_ORDER.get(level_a, 0) >= RISK_LEVEL_ORDER.get(level_b, 0)


def risk_level_gt(level_a: str, level_b: str) -> bool:
    """判断风险等级 level_a 是否 > level_b。

    Args:
        level_a: 风险等级A
        level_b: 风险等级B

    Returns:
        bool: level_a > level_b
    """
    return RISK_LEVEL_ORDER.get(level_a, 0) > RISK_LEVEL_ORDER.get(level_b, 0)


def escalate_one_level(current_level: str) -> str:
    """将风险等级提升一级。

    等级升序: gray -> green -> yellow -> orange -> red

    Args:
        current_level: 当前风险等级

    Returns:
        提升一级后的风险等级
    """
    level_sequence = ["gray", "green", "yellow", "orange", "red"]
    idx = level_sequence.index(current_level) if current_level in level_sequence else 0
    new_idx = min(idx + 1, len(level_sequence) - 1)
    return level_sequence[new_idx]


# ═══════════════════════════════════════════════════════════════════════════════
# 提级结果数据模型
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class EscalationReason:
    """单条提级原因记录。

    Attributes:
        rule_id: 触发的规则编号 (R1-R7)
        rule_name: 规则中文名称
        description: 具体触发原因描述
        from_level: 提级前的风险等级
        to_level: 提级后的风险等级
        material_id: 关联的物料ID
        metadata: 附加元数据 (如灾害事件ID、价格变化率等)
    """
    rule_id: str
    rule_name: str
    description: str
    from_level: str
    to_level: str
    material_id: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EscalatedRisk:
    """提级后的风险评估结果。

    包装 MultiFactorRiskResult，附加提级信息。

    Attributes:
        final_level: 最终风险等级 (可能被提升)
        base_level: 基础多因子评估的风险等级
        final_score: 最终风险分数 (提级不改变分数，仅改变等级)
        base_score: 基础风险分数
        escalation_reasons: 触发的提级原因列表
        escalated: 是否发生了提级
        base_result: 原始基础评估结果引用
        material_id: 物料ID
        region_risk_tag: 区域风险标记 (R4 触发时)
    """
    final_level: str
    base_level: str
    final_score: float
    base_score: float
    escalation_reasons: list[EscalationReason]
    escalated: bool
    base_result: MultiFactorRiskResult
    material_id: int = 0
    region_risk_tag: str = ""

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典，便于API返回。

        Returns:
            完整的提级结果字典
        """
        return {
            "material_id": self.material_id,
            "final_level": self.final_level,
            "base_level": self.base_level,
            "final_score": round(self.final_score, 1),
            "base_score": round(self.base_score, 1),
            "escalated": self.escalated,
            "region_risk_tag": self.region_risk_tag,
            "escalation_reasons": [
                {
                    "rule_id": r.rule_id,
                    "rule_name": r.rule_name,
                    "description": r.description,
                    "from_level": r.from_level,
                    "to_level": r.to_level,
                    "metadata": r.metadata,
                }
                for r in self.escalation_reasons
            ],
            "base_result": self.base_result.to_dict(),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# 物料上下文 (Material Context) — 提供规则判断所需的物料维度数据
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class MaterialContext:
    """物料上下文数据，用于提级规则判断。

    包含评估某条规则所需的所有外部数据。

    Attributes:
        material_id: 物料ID
        # R1: 政策合规信号
        policy_signals: 政策信号字典 (同 multi_factor_risk_engine 输入)
        # R2: 生命周期事件
        lifecycle_events: 生命周期事件列表 [{"type": "EOL", "source": "Octopart", ...}]
        alternative_count: 可用替代料数量
        # R3: 价格涨幅
        price_changes: 价格变化率 {"7d_change": float, ...}
        material_keys: 材料关键标识列表 (如 ["copper", "aluminum"])
        bom_usage_ratio: BOM中用量占比 (0.0-1.0)
        # R4: 灾害事件
        disaster_signals: 灾害信号字典 (同 multi_factor_risk_engine 输入)
        supplier_region: 供应商所在地区
        affected_regions: 受灾地区列表
        gdacs_events: GDACS事件列表 [{"severity_raw": "Red", "event_type": "earthquake", ...}]
        # R5: 库存与交期
        inventory_level_pct: 当前库存占安全库存百分比 (0-100)
        lead_time_current_weeks: 当前交期(周)
        lead_time_baseline_weeks: 基线交期(周)
        # R6: 来源多样性
        brand_count: 品牌数量
        supplier_count: 供应商数量
        # R7: 数据完整性
        data_completeness_pct: 数据完整度 (0-100)
        is_critical_bom: 是否为BOM关键物料
    """
    material_id: int = 0
    # R1
    policy_signals: dict[str, Any] | None = None
    # R2
    lifecycle_events: list[dict[str, Any]] | None = None
    alternative_count: int | None = None
    # R3
    price_changes: dict[str, float] | None = None
    material_keys: list[str] | None = None
    bom_usage_ratio: float = 0.0
    # R4
    disaster_signals: dict[str, Any] | None = None
    supplier_region: str = ""
    affected_regions: list[str] | None = None
    gdacs_events: list[dict[str, Any]] | None = None
    # R5
    inventory_level_pct: float | None = None
    lead_time_current_weeks: float = 0.0
    lead_time_baseline_weeks: float = 0.0
    # R6
    brand_count: int = 0
    supplier_count: int = 0
    # R7
    data_completeness_pct: float = 100.0
    is_critical_bom: bool = False


# ═══════════════════════════════════════════════════════════════════════════════
# 规则实现: 7条独立的触发条件判定函数
# ═══════════════════════════════════════════════════════════════════════════════

def _check_r1_policy_s_level(
    base_risk: MultiFactorRiskResult,
    ctx: MaterialContext,
) -> tuple[bool, str, str, dict[str, Any]]:
    """R1: S级来源政策事件检测。

    触发条件: BIS/USTR/USGS等S级来源出现出口管制/实体清单/关税变化，
    且政策合规分=100（即已被S级来源标记拉满）。

    动作: 直接提升至红色 (若当前低于红色)。

    Returns:
        (触发, 目标等级, 描述, 元数据)
    """
    policy_signals = ctx.policy_signals or {}
    if not policy_signals:
        return False, "", "", {}

    # 检查是否有S级来源命中
    s_level_hit = False
    hit_sources: list[str] = []

    for signal_key, signal_value in policy_signals.items():
        if not signal_value:
            continue

        # 检查是否是S级来源标识
        if signal_key in S_LEVEL_POLICY_SOURCES:
            s_level_hit = True
            hit_sources.append(signal_key)
            continue

        # 检查signal_value字典中是否有level='S'标记
        if isinstance(signal_value, dict):
            source_level = signal_value.get("level", "")
            source_name = signal_value.get("source", signal_key)
            if str(source_level).upper() == "S":
                s_level_hit = True
                hit_sources.append(str(source_name))

    if not s_level_hit:
        return False, "", "", {}

    # 判定目标等级
    # 如果是实体清单命中 → 红色；否则 → 橙色
    has_entity_list = any(
        k in ("entity_list_hit", "bis_restriction", "ustr_sanction")
        for k in policy_signals
        if policy_signals[k]
    )
    target = "red" if has_entity_list else "orange"

    desc = (
        f"S级来源政策事件触发: {', '.join(hit_sources)}，"
        f"风险提升至{'红色(极高)' if target == 'red' else '橙色(高)'}"
    )
    return True, target, desc, {"hit_sources": hit_sources, "target": target}


def _check_r2_lifecycle_event(
    base_risk: MultiFactorRiskResult,
    ctx: MaterialContext,
) -> tuple[bool, str, str, dict[str, Any]]:
    """R2: 原厂PCN/EOL/LTB事件检测。

    触发条件: Octopart等数据源返回lifecycle_status为PCN/EOL/LTB。

    动作: 有替代料 → 橙色; 无替代料 → 红色。

    Returns:
        (触发, 目标等级, 描述, 元数据)
    """
    lifecycle_events = ctx.lifecycle_events or []
    if not lifecycle_events:
        return False, "", "", {}

    triggered_events: list[str] = []
    for event in lifecycle_events:
        event_type = str(event.get("type", "")).upper()
        if event_type in LIFECYCLE_ESCALATION_TRIGGERS:
            triggered_events.append(event_type)

    if not triggered_events:
        return False, "", "", {}

    # 检查是否有替代料
    alt_count = ctx.alternative_count
    has_alternative = alt_count is not None and alt_count > 0

    if has_alternative:
        target = "orange"
        desc = f"原厂生命周期事件({', '.join(set(triggered_events))})，有{alt_count}个替代料，提升至橙色"
    else:
        target = "red"
        desc = f"原厂生命周期事件({', '.join(set(triggered_events))})，无替代料，提升至红色"

    metadata = {
        "event_types": triggered_events,
        "has_alternative": has_alternative,
        "alternative_count": alt_count or 0,
    }
    return True, target, desc, metadata


def _check_r3_price_surge(
    base_risk: MultiFactorRiskResult,
    ctx: MaterialContext,
    current_level: str | None = None,
) -> tuple[bool, str, str, dict[str, Any]]:
    """R3: 关键材料价格暴涨检测。

    触发条件: 关键材料7日涨幅超过阈值 且 命中高用量BOM (usage_ratio > 0.3)。

    动作: 提升一级。

    Returns:
        (触发, 目标等级, 描述, 元数据)
    """
    price_changes = ctx.price_changes or {}
    material_keys = ctx.material_keys or []
    seven_d_change = price_changes.get("7d_change")

    if seven_d_change is None or not material_keys:
        return False, "", "", {}

    # 检查是否有材料命中涨幅阈值
    surged_materials: list[tuple[str, float, float]] = []  # (材料名, 涨幅, 阈值)
    for key in material_keys:
        threshold = PRICE_SURGE_THRESHOLDS.get(key)
        if threshold is not None and seven_d_change >= threshold:
            surged_materials.append((key, seven_d_change, threshold))

    if not surged_materials:
        return False, "", "", {}

    # 检查是否命中高用量BOM
    high_usage = ctx.bom_usage_ratio > 0.3

    if not high_usage:
        return False, "", "", {}

    # 提升一级 — 基于当前等级（非基础等级），支持多规则叠加
    base_level = current_level or base_risk.risk_level
    target = escalate_one_level(base_level)

    material_desc = "; ".join(
        f"{name}(涨幅{change:+.1f}%>阈值{th:.0f}%)"
        for name, change, th in surged_materials
    )
    desc = f"关键材料{material_desc}暴涨，BOM用量占比{ctx.bom_usage_ratio:.1%}，提升一级至{_level_label(target)}"

    metadata = {
        "surged_materials": [
            {"name": n, "change": c, "threshold": t}
            for n, c, t in surged_materials
        ],
        "bom_usage_ratio": ctx.bom_usage_ratio,
    }
    return True, target, desc, metadata


def _check_r4_gdacs_disaster(
    base_risk: MultiFactorRiskResult,
    ctx: MaterialContext,
    current_level: str | None = None,
) -> tuple[bool, str, str, dict[str, Any]]:
    """R4: GDACS Red级灾害事件检测。

    触发条件: 供应商所在地出现GDACS Red级灾害事件。

    动作: 提升一级并标记区域风险。

    Returns:
        (触发, 目标等级, 描述, 元数据)
    """
    gdacs_events = ctx.gdacs_events or []
    supplier_region = ctx.supplier_region
    affected_regions = ctx.affected_regions or []

    if not gdacs_events or not supplier_region:
        return False, "", "", {}

    # 查找Red级且影响供应商所在地区的事件
    matched_events: list[dict[str, Any]] = []
    for event in gdacs_events:
        severity_raw = str(event.get("severity_raw", "")).lower()
        if severity_raw != "red":
            continue

        # 检查事件影响区域是否包含供应商所在地
        event_country = str(event.get("country", "")).lower()
        event_name = str(event.get("name", "")).lower()

        region_match = False
        if supplier_region.lower() in event_country or event_country in supplier_region.lower():
            region_match = True
        elif any(
            supplier_region.lower() in r.lower() or r.lower() in supplier_region.lower()
            for r in affected_regions
        ):
            region_match = True
        elif supplier_region.lower() in event_name:
            region_match = True

        if region_match:
            matched_events.append(event)

    if not matched_events:
        return False, "", "", {}

    # 提升一级 — 基于当前等级（非基础等级），支持多规则叠加
    base_level = current_level or base_risk.risk_level
    target = escalate_one_level(base_level)

    event_types = set(e.get("event_type", "unknown") for e in matched_events)
    event_names = [e.get("name", "未知") for e in matched_events[:3]]
    desc = (
        f"供应商所在地({supplier_region})出现GDACS Red级"
        f"{','.join(event_types)}事件({'; '.join(event_names)})，"
        f"提升一级至{_level_label(target)}，标记区域风险"
    )

    metadata = {
        "matched_events": [
            {
                "event_id": e.get("event_id", ""),
                "event_type": e.get("event_type", ""),
                "severity": e.get("severity_raw", ""),
                "country": e.get("country", ""),
                "name": e.get("name", ""),
            }
            for e in matched_events
        ],
        "supplier_region": supplier_region,
        "region_risk": True,
    }
    return True, target, desc, metadata


def _check_r5_inventory_crisis(
    base_risk: MultiFactorRiskResult,
    ctx: MaterialContext,
) -> tuple[bool, str, str, dict[str, Any]]:
    """R5: 分销库存危机检测。

    触发条件: 分销库存低于安全库存 且 交期拉长>50%。

    动作: 提升至橙色。

    Returns:
        (触发, 目标等级, 描述, 元数据)
    """
    inventory_pct = ctx.inventory_level_pct
    lead_time_current = ctx.lead_time_current_weeks
    lead_time_baseline = ctx.lead_time_baseline_weeks

    if inventory_pct is None:
        return False, "", "", {}

    # 检查库存是否低于安全库存
    inventory_low = inventory_pct < (INVENTORY_SAFETY_MULTIPLIER * 100)

    if not inventory_low:
        return False, "", "", {}

    # 检查交期拉长是否>50%
    lead_time_increase = 0.0
    if lead_time_baseline > 0:
        lead_time_increase = ((lead_time_current - lead_time_baseline) / lead_time_baseline) * 100

    lead_time_extended = lead_time_increase > LEAD_TIME_INCREASE_THRESHOLD

    if not lead_time_extended:
        return False, "", "", {}

    target = "orange"
    desc = (
        f"分销库存仅{inventory_pct:.0f}%安全库存，"
        f"交期从{lead_time_baseline:.1f}周拉长至{lead_time_current:.1f}周"
        f"(+{lead_time_increase:.0f}%)，提升至橙色"
    )

    metadata = {
        "inventory_pct": inventory_pct,
        "lead_time_current_weeks": lead_time_current,
        "lead_time_baseline_weeks": lead_time_baseline,
        "lead_time_increase_pct": round(lead_time_increase, 1),
    }
    return True, target, desc, metadata


def _check_r6_single_source(
    base_risk: MultiFactorRiskResult,
    ctx: MaterialContext,
) -> tuple[bool, str, str, dict[str, Any]]:
    """R6: 单一来源风险检测。

    触发条件: 单一品牌/单一供应商 且 无替代料。

    动作: 至少黄色；叠加事件后橙色。

    Returns:
        (触发, 目标等级, 描述, 元数据)
    """
    brand_count = ctx.brand_count
    supplier_count = ctx.supplier_count
    alt_count = ctx.alternative_count

    is_single_brand = brand_count == 1
    is_single_supplier = supplier_count == 1
    has_no_alternative = alt_count is None or alt_count == 0

    if not (is_single_brand and is_single_supplier):
        return False, "", "", {}

    if has_no_alternative:
        # 无替代料的单一来源 → 橙色
        target = "orange"
        desc = "单一品牌+单一供应商+无替代料，叠加事件后提升至橙色"
    else:
        # 有替代料但仍是单一来源 → 至少黄色
        target = "yellow"
        desc = f"单一品牌+单一供应商，有{alt_count}个替代料，至少黄色"

    metadata = {
        "brand_count": brand_count,
        "supplier_count": supplier_count,
        "alternative_count": alt_count or 0,
        "has_alternative": not has_no_alternative,
    }
    return True, target, desc, metadata


def _check_r7_data_missing(
    base_risk: MultiFactorRiskResult,
    ctx: MaterialContext,
) -> tuple[bool, str, str, dict[str, Any]]:
    """R7: 数据缺失待确认检测。

    触发条件: 数据缺失(data_completeness < 30%) 但 BOM关键度高。

    动作: 显示灰色待确认。

    Returns:
        (触发, 目标等级, 描述, 元数据)
    """
    completeness = ctx.data_completeness_pct
    is_critical = ctx.is_critical_bom

    # 数据缺失 + BOM关键
    if completeness >= 30.0 or not is_critical:
        return False, "", "", {}

    target = "gray"
    desc = (
        f"数据完整度仅{completeness:.0f}%，"
        f"但该物料为BOM关键物料，标记为灰色待确认"
    )

    metadata = {
        "data_completeness_pct": completeness,
        "is_critical_bom": is_critical,
    }
    return True, target, desc, metadata


# ═══════════════════════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════════════════════

def _level_label(level: str) -> str:
    """获取风险等级的中文标签。

    Args:
        level: 风险等级字符串

    Returns:
        中文标签
    """
    labels = {
        "red": "红色(极高)",
        "orange": "橙色(高)",
        "yellow": "黄色(中)",
        "green": "绿色(低)",
        "gray": "灰色(待确认)",
    }
    return labels.get(level, level)


# ═══════════════════════════════════════════════════════════════════════════════
# 主引擎: AutoEscalationEngine
# ═══════════════════════════════════════════════════════════════════════════════

class AutoEscalationEngine:
    """自动提级规则引擎。

    对多因子风险评估结果进行二次评估，逐条检查7条提级规则。
    核心原则: 只升不降。

    Attributes:
        _rules: 规则列表，按优先级排序
    """

    # 规则检查函数映射
    RULE_CHECKERS: dict[str, Any] = {
        "R1": _check_r1_policy_s_level,
        "R2": _check_r2_lifecycle_event,
        "R3": _check_r3_price_surge,
        "R4": _check_r4_gdacs_disaster,
        "R5": _check_r5_inventory_crisis,
        "R6": _check_r6_single_source,
        "R7": _check_r7_data_missing,
    }

    def __init__(self) -> None:
        """初始化提级规则引擎。

        按优先级从高到低排序规则，确保高优先级规则先执行。
        """
        self._rules = sorted(
            ESCALATION_RULES_CONFIG.values(),
            key=lambda r: r.priority,
            reverse=True,
        )

    @property
    def rule_count(self) -> int:
        """已配置的规则总数。"""
        return len(self._rules)

    @property
    def enabled_rule_count(self) -> int:
        """当前启用的规则数。"""
        return sum(1 for r in self._rules if is_rule_enabled(r.rule_id))

    def evaluate(
        self,
        material_id: int,
        base_risk: MultiFactorRiskResult,
        ctx: MaterialContext | None = None,
    ) -> EscalatedRisk:
        """对基础风险评估结果进行提级评估。

        逐条检查所有启用的提级规则，根据触发情况提升风险等级。
        遵循只升不降原则：提级后等级不会低于原始等级。

        Args:
            material_id: 物料ID
            base_risk: 多因子风险评估结果 (来自 MultiFactorRiskEngine)
            ctx: 物料上下文数据，提供规则判断所需的外部数据

        Returns:
            EscalatedRisk: 提级后的风险评估结果，包含最终等级和提级原因
        """
        if ctx is None:
            ctx = MaterialContext(material_id=material_id)

        final_level = base_risk.risk_level
        escalation_reasons: list[EscalationReason] = []
        region_risk_tag = ""

        for rule_config in self._rules:
            rule_id = rule_config.rule_id

            # 跳过被禁用的规则
            if not is_rule_enabled(rule_id):
                continue

            # 获取对应的检查函数
            checker = self.RULE_CHECKERS.get(rule_id)
            if checker is None:
                logger.warning(f"Unknown escalation rule: {rule_id}")
                continue

            try:
                # 对R3/R4传入当前等级以支持"提升一级"的多规则叠加
                if rule_id in ("R3", "R4"):
                    triggered, target_level, description, metadata = checker(
                        base_risk, ctx, current_level=final_level
                    )
                else:
                    triggered, target_level, description, metadata = checker(
                        base_risk, ctx
                    )
            except Exception as e:
                logger.error(
                    f"Error evaluating rule {rule_id} for material {material_id}: {e}",
                    exc_info=True,
                )
                continue

            if not triggered:
                continue

            # R7特殊处理: gray是数据质量标记(非风险等级)
            # R7表示"数据不足，无法信任当前评分"
            # 仅当没有其他规则触发提级时，才覆盖为gray
            # 如果其他规则(R1-R6)已找到具体证据并提级，则R7仅作注释记录
            if rule_id == "R7":
                if not escalation_reasons:
                    # 无其他提级 → 覆盖为gray (数据不足无法评分)
                    from_level = final_level
                    final_level = target_level
                    escalation_reasons.append(EscalationReason(
                        rule_id=rule_id,
                        rule_name=rule_config.name,
                        description=description,
                        from_level=from_level,
                        to_level=target_level,
                        material_id=material_id,
                        metadata=metadata,
                    ))
                    logger.info(
                        f"Rule {rule_id} overrode material {material_id} "
                        f"to gray (data quality): {from_level} → {target_level}"
                    )
                else:
                    # 已有其他规则提级 → R7仅作注释，不改变等级
                    logger.debug(
                        f"Rule {rule_id} triggered for material {material_id} "
                        f"but other rules already escalated, R7 annotation only"
                    )
                continue

            # 只升不降: 仅当目标等级高于当前等级时才执行提级
            if not risk_level_gt(target_level, final_level):
                # 即使触发了，但目标等级不高于当前等级，跳过
                # 记录为信息但不实际提级
                logger.debug(
                    f"Rule {rule_id} triggered for material {material_id} "
                    f"but target {target_level} <= current {final_level}, skipped"
                )
                continue

            # 执行提级
            from_level = final_level
            final_level = target_level

            # R4特殊处理: 记录区域风险标记
            if rule_id == "R4":
                region_risk_tag = ctx.supplier_region or metadata.get("supplier_region", "")

            escalation_reasons.append(EscalationReason(
                rule_id=rule_id,
                rule_name=rule_config.name,
                description=description,
                from_level=from_level,
                to_level=target_level,
                material_id=material_id,
                metadata=metadata,
            ))

            logger.info(
                f"Rule {rule_id} escalated material {material_id}: "
                f"{from_level} → {target_level}"
            )

        escalated = final_level != base_risk.risk_level

        return EscalatedRisk(
            final_level=final_level,
            base_level=base_risk.risk_level,
            final_score=base_risk.total_score,
            base_score=base_risk.base_score,
            escalation_reasons=escalation_reasons,
            escalated=escalated,
            base_result=base_risk,
            material_id=material_id,
            region_risk_tag=region_risk_tag,
        )

    def evaluate_batch(
        self,
        items: list[tuple[int, MultiFactorRiskResult, MaterialContext]],
    ) -> list[EscalatedRisk]:
        """批量评估多个物料的提级。

        Args:
            items: 物料列表，每项为 (material_id, base_risk, ctx) 元组

        Returns:
            每个物料的提级结果列表
        """
        results: list[EscalatedRisk] = []
        for material_id, base_risk, ctx in items:
            result = self.evaluate(material_id, base_risk, ctx)
            results.append(result)
        return results

    def get_rule_status(self) -> list[dict[str, Any]]:
        """获取所有规则的当前状态。

        Returns:
            规则状态列表，每项包含 rule_id, name, enabled, priority
        """
        return [
            {
                "rule_id": r.rule_id,
                "name": r.name,
                "description": r.description,
                "enabled": is_rule_enabled(r.rule_id),
                "priority": r.priority,
                "target_level": r.target_level,
            }
            for r in self._rules
        ]

    def toggle_rule(self, rule_id: str, enabled: bool) -> bool:
        """动态启用/禁用指定规则。

        Args:
            rule_id: 规则编号 (R1-R7)
            enabled: True=启用, False=禁用

        Returns:
            bool: 操作是否成功
        """
        from app.services.upstream.propagation_rules import set_rule_enabled

        if rule_id not in ESCALATION_RULE_ENABLED:
            logger.warning(f"Unknown rule ID: {rule_id}")
            return False

        set_rule_enabled(rule_id, enabled)
        logger.info(f"Rule {rule_id} {'enabled' if enabled else 'disabled'}")
        return True
