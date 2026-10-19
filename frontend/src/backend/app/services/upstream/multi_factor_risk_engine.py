"""
多因子风险评分引擎 (T2-001)

将 Phase 1 双轨模型(材料轨+供需轨)升级为七因子加权模型:

    总风险分 = 行情趋势分 × 25%
             + 供应紧张分 × 20%
             + 政策合规分 × 15%
             + 灾害区域分 × 10%
             + BOM暴露度   × 15%
             + 替代难度   × 10%
             + 数据置信度调整 × 5%
    最终分 = 基础分 × 置信度系数 (0.8-1.2)

各因子定义 (0-100分):
- 行情趋势分: 材料价格7/30/90天变化率 (保留Phase 1材料轨逻辑)
- 供应紧张分: 分销商库存变化、交期变化 (保留Phase 1供需轨逻辑)
- 政策合规分: BIS/USTR/实体清单/关税, S级来源命中时直接拉高
- 灾害区域分: GDACS/USGS灾害事件, 供应商所在地灾害
- BOM暴露度: BOM中该物料用量占比 × 项目数
- 替代难度: 替代料数量 × 认证周期 × Pin兼容度, 无替代料=100分
- 数据置信度: 数据源级别 × 交叉验证数, 作为调整系数 S级×1.2 / C级×0.8

风险等级5级映射:
- >=80分 → red    (已影响交付/成本)
- >=60分 → orange (高概率影响)
- >=35分 → yellow (早期信号)
- >0分   → green  (风险可控)
- 数据不足 → gray (不允许显示为正常)

兼容性:
- 保留 Phase 1 材料轨和供需轨的计算逻辑, 输出 legacy_track_scores
- evaluate_dual_track_risk 仍可独立调用 (dual_track_risk_engine.py)
"""
from __future__ import annotations

import logging
from typing import Any

from app.models.risk_assessment import (
    FactorScore,
    MultiFactorRiskResult,
    RiskLevel,
    score_to_risk_level,
)
from app.services.upstream.propagation_rules import (
    CONFIDENCE_COEFFICIENTS,
    CONFIDENCE_SOURCE_SCORES,
    DEMAND_SUPPLY_SIGNAL_WEIGHTS,
    DISASTER_ZONE_SIGNALS,
    MATERIAL_SIGNAL_WEIGHTS,
    MULTI_FACTOR_DISPLAY_NAMES,
    MULTI_FACTOR_WEIGHTS,
    POLICY_COMPLIANCE_SIGNALS,
    SUBSTITUTION_PARAMS,
    get_category_model,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 因子1: 行情趋势分 (market_trend) — 保留 Phase 1 材料轨逻辑
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_market_trend_score(
    material_signals: dict[str, Any],
    price_changes: dict[str, float] | None = None,
) -> tuple[float, list[str]]:
    """
    计算行情趋势分: 基于材料价格信号和价格变化率。

    保留 Phase 1 材料轨的信号加权逻辑, 并增强支持7/30/90天价格变化率。

    Args:
        material_signals: 材料信号字典 (Phase 1 格式, key 为信号名, value 为 bool)
        price_changes: 价格变化率字典, 格式:
            {"7d_change": float, "30d_change": float, "90d_change": float}
            值为百分比, 如 200.0 表示 +200%

    Returns:
        (score, evidence): 0-100分数 和 证据列表
    """
    score = 0.0
    evidence: list[str] = []

    # ── Phase 1 材料信号加权 (保留原始逻辑) ──
    for signal_key, weight in MATERIAL_SIGNAL_WEIGHTS.items():
        if material_signals.get(signal_key):
            score += weight
            evidence.append(f"material:{signal_key}")

    # ── 增强: 价格变化率加成 ──
    if price_changes:
        change_7d = price_changes.get("7d_change", 0.0) or 0.0
        change_30d = price_changes.get("30d_change", 0.0) or 0.0
        change_90d = price_changes.get("90d_change", 0.0) or 0.0

        # 短期剧烈变化 (>30% in 7天) 额外加成
        if change_7d > 30:
            score += min(change_7d * 0.3, 40)
            evidence.append(f"7d_change:{change_7d:+.1f}%")
        # 中期趋势 (>50% in 30天)
        if change_30d > 50:
            score += min(change_30d * 0.2, 30)
            evidence.append(f"30d_change:{change_30d:+.1f}%")
        # 长期趋势 (>80% in 90天)
        if change_90d > 80:
            score += min(change_90d * 0.15, 25)
            evidence.append(f"90d_change:{change_90d:+.1f}%")

    return min(score, 100.0), evidence


# ═══════════════════════════════════════════════════════════════════════════════
# 因子2: 供应紧张分 (supply_tension) — 保留 Phase 1 供需轨逻辑
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_supply_tension_score(
    body_signals: dict[str, Any],
    market_facts: dict[str, Any],
) -> tuple[float, list[str]]:
    """
    计算供应紧张分: 基于分销商库存变化、交期变化。

    保留 Phase 1 供需轨的核心逻辑, 并增强库存/交期量化评估。

    Args:
        body_signals: 主体信号 (stock_down, lead_time_weeks 等)
        market_facts: 市场事实 (price_up_confirmed, shortage_confirmed 等)

    Returns:
        (score, evidence): 0-100分数 和 证据列表
    """
    score = 0.0
    evidence: list[str] = []

    # ── Phase 1 供需信号加权 (保留原始逻辑) ──
    if body_signals.get("stock_down"):
        score += DEMAND_SUPPLY_SIGNAL_WEIGHTS["stock_down"]
        evidence.append("stock_down")

    if market_facts.get("price_up_confirmed"):
        score += DEMAND_SUPPLY_SIGNAL_WEIGHTS["price_up_confirmed"]
        evidence.append("price_up_confirmed")

    if market_facts.get("shortage_confirmed"):
        score += DEMAND_SUPPLY_SIGNAL_WEIGHTS["shortage_confirmed"]
        evidence.append("shortage_confirmed")

    lead_time_weeks = body_signals.get("lead_time_weeks")
    if isinstance(lead_time_weeks, (int, float)):
        if lead_time_weeks >= 12:
            score += DEMAND_SUPPLY_SIGNAL_WEIGHTS["lead_time_long"]
            evidence.append(f"lead_time_long:{lead_time_weeks}w")
        elif lead_time_weeks >= 8:
            score += DEMAND_SUPPLY_SIGNAL_WEIGHTS["lead_time_medium"]
            evidence.append(f"lead_time_medium:{lead_time_weeks}w")

    # ── 增强: 库存天数量化 ──
    inventory_days = body_signals.get("inventory_days")
    if isinstance(inventory_days, (int, float)):
        if inventory_days <= 0:
            score += 20
            evidence.append(f"inventory_depleted:{inventory_days}d")
        elif inventory_days <= 7:
            score += 15
            evidence.append(f"inventory_critical:{inventory_days}d")
        elif inventory_days <= 14:
            score += 8
            evidence.append(f"inventory_low:{inventory_days}d")

    # ── 增强: 交期变化率 ──
    lead_time_change_pct = body_signals.get("lead_time_change_pct")
    if isinstance(lead_time_change_pct, (int, float)) and lead_time_change_pct > 50:
        score += min(lead_time_change_pct * 0.2, 20)
        evidence.append(f"lead_time_change:{lead_time_change_pct:+.1f}%")

    return min(score, 100.0), evidence


# ═══════════════════════════════════════════════════════════════════════════════
# 因子3: 政策合规分 (policy_compliance)
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_policy_compliance_score(
    policy_signals: dict[str, Any] | None = None,
) -> tuple[float, list[str]]:
    """
    计算政策合规分: 基于BIS/USTR/实体清单/关税等政策信号。

    S级来源命中时直接拉高到满分。多个信号取最高分(非累加),
    因为单一政策事件即可造成最大影响。

    Args:
        policy_signals: 政策信号字典, key 为信号类型, value 为 bool 或 dict
            示例: {"entity_list_hit": True, "tariff_increase": {"rate": 25}}
            或: {"bis_restriction": {"level": "S", "detail": "..."}}

    Returns:
        (score, evidence): 0-100分数 和 证据列表
    """
    policy_signals = policy_signals or {}
    if not policy_signals:
        return 0.0, []

    score = 0.0
    evidence: list[str] = []
    has_s_level = False

    for signal_key, signal_value in policy_signals.items():
        if not signal_value:
            continue

        base_weight = POLICY_COMPLIANCE_SIGNALS.get(signal_key, 0.0)
        if base_weight == 0.0:
            continue

        # 检查是否有 S 级来源标记
        is_s_level = False
        if isinstance(signal_value, dict):
            source_level = signal_value.get("level", "").upper()
            if source_level == "S":
                is_s_level = True
                has_s_level = True

        # S级来源 → 直接满分
        if is_s_level:
            score = 100.0
            evidence.append(f"S_level:{signal_key}")
        else:
            score = max(score, base_weight)
            evidence.append(signal_key)

    return min(score, 100.0), evidence


# ═══════════════════════════════════════════════════════════════════════════════
# 因子4: 灾害区域分 (disaster_zone)
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_disaster_zone_score(
    disaster_signals: dict[str, Any] | None = None,
    supplier_region: str | None = None,
    affected_regions: list[str] | None = None,
) -> tuple[float, list[str]]:
    """
    计算灾害区域分: 基于GDACS/USGS灾害事件与供应商所在地的关联。

    Args:
        disaster_signals: 灾害信号字典, key 为灾害类型, value 为 bool 或 dict
            示例: {"earthquake_severe": {"magnitude": 7.2, "region": "日本"}}
        supplier_region: 供应商所在地区 (如 "日本", "台湾", "广东")
        affected_regions: 受灾害影响的地区列表

    Returns:
        (score, evidence): 0-100分数 和 证据列表
    """
    disaster_signals = disaster_signals or {}
    affected_regions = affected_regions or []

    if not disaster_signals:
        return 0.0, []

    score = 0.0
    evidence: list[str] = []

    # 检查供应商所在区域是否受灾
    region_affected = False
    if supplier_region:
        for region in affected_regions:
            if supplier_region in region or region in supplier_region:
                region_affected = True
                break

    for signal_key, signal_value in disaster_signals.items():
        if not signal_value:
            continue

        base_weight = DISASTER_ZONE_SIGNALS.get(signal_key, 0.0)
        if base_weight == 0.0:
            continue

        # 供应商所在地受灾 → 分数提升
        if region_affected:
            adjusted = min(base_weight * 1.2, 100.0)
            score = max(score, adjusted)
            evidence.append(f"{signal_key}:region_match({supplier_region})")
        else:
            score = max(score, base_weight)
            evidence.append(signal_key)

        # 额外灾害信息
        if isinstance(signal_value, dict):
            detail = signal_value.get("magnitude") or signal_value.get("detail", "")
            if detail:
                evidence[-1] += f":{detail}"

    return min(score, 100.0), evidence


# ═══════════════════════════════════════════════════════════════════════════════
# 因子5: BOM暴露度 (bom_exposure)
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_bom_exposure_score(
    bom_data: dict[str, Any] | None = None,
) -> tuple[float, list[str]]:
    """
    计算BOM暴露度: 该物料在BOM中的用量占比 × 涉及项目数。

    Args:
        bom_data: BOM相关数据
            - usage_ratio: 该物料用量占总用量比例 (0.0-1.0)
            - project_count: 涉及的项目数量
            - total_qty: 总需求量
            - is_critical: 是否为关键物料

    Returns:
        (score, evidence): 0-100分数 和 证据列表
    """
    bom_data = bom_data or {}
    if not bom_data:
        return 0.0, []

    score = 0.0
    evidence: list[str] = []

    usage_ratio = bom_data.get("usage_ratio", 0.0) or 0.0
    project_count = bom_data.get("project_count", 1) or 1
    is_critical = bom_data.get("is_critical", False)

    # 用量占比评分 (0-60分)
    usage_score = min(usage_ratio * 100 * 1.5, 60.0)
    score += usage_score
    if usage_ratio > 0:
        evidence.append(f"usage_ratio:{usage_ratio:.1%}")

    # 项目数评分 (0-30分) — 涉及越多项目风险越高
    project_score = min(project_count * 10, 30.0)
    score += project_score
    if project_count > 1:
        evidence.append(f"project_count:{project_count}")

    # 关键物料加成 (0-10分)
    if is_critical:
        score += 10.0
        evidence.append("critical_component")

    return min(score, 100.0), evidence


# ═══════════════════════════════════════════════════════════════════════════════
# 因子6: 替代难度 (substitution_difficulty)
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_substitution_difficulty_score(
    substitution_data: dict[str, Any] | None = None,
) -> tuple[float, list[str]]:
    """
    计算替代难度: 基于替代料数量、认证周期、Pin兼容度。

    无替代料时直接满分(100分)。

    Args:
        substitution_data: 替代料相关数据
            - alternative_count: 可用替代料数量
            - cert_cycle_months: 认证周期(月)
            - pin_compatibility: Pin兼容度 ("full", "partial", "incompatible")
            - is_pin_to_pin: 是否Pin-to-Pin兼容 (bool, 兼容旧字段)

    Returns:
        (score, evidence): 0-100分数 和 证据列表
    """
    substitution_data = substitution_data or {}
    if not substitution_data:
        return 0.0, []  # 无数据时不贡献风险分

    alt_count = substitution_data.get("alternative_count")
    cert_months = substitution_data.get("cert_cycle_months")
    pin_compat = substitution_data.get("pin_compatibility", "")
    is_p2p = substitution_data.get("is_pin_to_pin", None)

    # ── 无替代料 → 直接满分 ──
    if alt_count is None or alt_count == 0:
        return 100.0, ["no_alternative"]

    score = 0.0
    evidence: list[str] = []

    # ── 替代料数量评分 (0-40分): 越少越难 ──
    if alt_count == 1:
        score += SUBSTITUTION_PARAMS["single_alt_penalty"]
        evidence.append(f"single_alternative")
    elif alt_count <= 3:
        score += SUBSTITUTION_PARAMS["few_alt_penalty"]
        evidence.append(f"few_alternatives:{alt_count}")
    else:
        evidence.append(f"alternatives:{alt_count}")

    # ── 认证周期评分 (0-35分): 越长越难 ──
    if isinstance(cert_months, (int, float)):
        if cert_months > 12:
            score += SUBSTITUTION_PARAMS["cert_cycle_long_months"]
            evidence.append(f"cert_cycle:{cert_months}mo(长)")
        elif cert_months >= 6:
            score += SUBSTITUTION_PARAMS["cert_cycle_medium_months"]
            evidence.append(f"cert_cycle:{cert_months}mo(中)")
        else:
            score += SUBSTITUTION_PARAMS["cert_cycle_short_months"]
            evidence.append(f"cert_cycle:{cert_months}mo(短)")

    # ── Pin兼容度评分 (0-25分): 越不兼容越难 ──
    if pin_compat == "incompatible" or is_p2p is False:
        score += SUBSTITUTION_PARAMS["pin_incompatible"]
        evidence.append("pin_incompatible")
    elif pin_compat == "partial":
        score += SUBSTITUTION_PARAMS["pin_compatible_partial"]
        evidence.append("pin_partial_compatible")
    elif pin_compat == "full" or is_p2p is True:
        score += SUBSTITUTION_PARAMS["pin_fully_compatible"]
        # 完全兼容不加分

    return min(score, 100.0), evidence


# ═══════════════════════════════════════════════════════════════════════════════
# 因子7: 数据置信度调整 (confidence_adjustment)
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_confidence_score(
    data_sources: dict[str, Any] | None = None,
) -> tuple[float, str, float]:
    """
    计算数据置信度分数和调整系数。

    评分基于数据源级别和交叉验证数量。
    调整系数作为最终乘数: S级×1.2, A级×1.1, B级×1.0, C级×0.8

    Args:
        data_sources: 数据源信息
            - source_level: 最高数据源级别 ('S', 'A', 'B', 'C')
            - cross_validation_count: 交叉验证的数据源数量
            - sources: 数据源详情列表

    Returns:
        (confidence_score, source_level, confidence_coefficient)
        - confidence_score: 0-100的置信度分数
        - source_level: 综合判定的数据源级别
        - confidence_coefficient: 调整系数 (0.8-1.2)
    """
    data_sources = data_sources or {}

    # 无数据源信息时返回0分
    if not data_sources or not data_sources.get("source_level"):
        return 0.0, "B", 1.0

    source_level = data_sources.get("source_level", "B") or "B"
    cross_validation_count = data_sources.get("cross_validation_count", 0) or 0

    # ── 基础分: 基于数据源级别 ──
    base_score = CONFIDENCE_SOURCE_SCORES.get(source_level.upper(), 50.0)

    # ── 交叉验证加成 ──
    if cross_validation_count >= 3:
        bonus = 25.0
    elif cross_validation_count == 2:
        bonus = 15.0
    elif cross_validation_count == 1:
        bonus = 5.0
    else:
        bonus = 0.0

    confidence_score = min(base_score + bonus, 100.0)

    # ── 调整系数 ──
    confidence_coefficient = CONFIDENCE_COEFFICIENTS.get(source_level.upper(), 1.0)

    return confidence_score, source_level.upper(), confidence_coefficient


# ═══════════════════════════════════════════════════════════════════════════════
# 主评估函数: 七因子加权评分引擎
# ═══════════════════════════════════════════════════════════════════════════════

def evaluate_multi_factor_risk(
    category: str,
    *,
    # Phase 1 兼容输入
    material_signals: dict[str, Any] | None = None,
    body_signals: dict[str, Any] | None = None,
    market_facts: dict[str, Any] | None = None,
    buffers: dict[str, Any] | None = None,
    # 新增七因子输入
    price_changes: dict[str, float] | None = None,
    policy_signals: dict[str, Any] | None = None,
    disaster_signals: dict[str, Any] | None = None,
    supplier_region: str | None = None,
    affected_regions: list[str] | None = None,
    bom_data: dict[str, Any] | None = None,
    substitution_data: dict[str, Any] | None = None,
    data_sources: dict[str, Any] | None = None,
) -> MultiFactorRiskResult:
    """
    七因子加权风险评估主入口。

    同时兼容 Phase 1 输入格式, 输出中保留 legacy_track_scores 供下游平滑迁移。

    Args:
        category: 物料品类标识
        material_signals: 材料信号 (Phase 1 格式)
        body_signals: 主体信号 (Phase 1 格式)
        market_facts: 市场事实 (Phase 1 格式)
        buffers: 缓冲因子 (Phase 1 格式)
        price_changes: 价格变化率 {"7d_change": float, "30d_change": float, "90d_change": float}
        policy_signals: 政策合规信号
        disaster_signals: 灾害区域信号
        supplier_region: 供应商所在地区
        affected_regions: 受灾地区列表
        bom_data: BOM暴露度数据
        substitution_data: 替代难度数据
        data_sources: 数据源信息

    Returns:
        MultiFactorRiskResult: 完整的七因子风险评估结果
    """
    material_signals = material_signals or {}
    body_signals = body_signals or {}
    market_facts = market_facts or {}
    buffers = buffers or {}

    # ── Step 0: 检查生命周期状态 (保留Phase 1的EOL/NRND直接升级逻辑) ──
    lifecycle = body_signals.get("lifecycle_status", "Unknown")
    if lifecycle and str(lifecycle).upper() in ("EOL", "END_OF_LIFE"):
        return _build_lifecycle_result(category, lifecycle, "red", 95.0)
    if lifecycle and str(lifecycle).upper() in ("NRND", "NOT_RECOMMENDED", "OBSOLETE"):
        return _build_lifecycle_result(category, lifecycle, "orange", 80.0)

    # ── Step 1: 计算7个因子分数 ──
    factors: dict[str, FactorScore] = {}
    weights = MULTI_FACTOR_WEIGHTS
    display_names = MULTI_FACTOR_DISPLAY_NAMES

    # 因子1: 行情趋势分
    mt_raw, mt_evidence = calculate_market_trend_score(material_signals, price_changes)
    factors["market_trend"] = FactorScore(
        name="market_trend",
        display_name=display_names["market_trend"],
        raw_score=mt_raw,
        weight=weights["market_trend"],
        weighted_score=mt_raw * weights["market_trend"],
        evidence=mt_evidence,
    )

    # 因子2: 供应紧张分
    st_raw, st_evidence = calculate_supply_tension_score(body_signals, market_facts)
    factors["supply_tension"] = FactorScore(
        name="supply_tension",
        display_name=display_names["supply_tension"],
        raw_score=st_raw,
        weight=weights["supply_tension"],
        weighted_score=st_raw * weights["supply_tension"],
        evidence=st_evidence,
    )

    # 因子3: 政策合规分
    pc_raw, pc_evidence = calculate_policy_compliance_score(policy_signals)
    factors["policy_compliance"] = FactorScore(
        name="policy_compliance",
        display_name=display_names["policy_compliance"],
        raw_score=pc_raw,
        weight=weights["policy_compliance"],
        weighted_score=pc_raw * weights["policy_compliance"],
        evidence=pc_evidence,
    )

    # 因子4: 灾害区域分
    dz_raw, dz_evidence = calculate_disaster_zone_score(
        disaster_signals, supplier_region, affected_regions
    )
    factors["disaster_zone"] = FactorScore(
        name="disaster_zone",
        display_name=display_names["disaster_zone"],
        raw_score=dz_raw,
        weight=weights["disaster_zone"],
        weighted_score=dz_raw * weights["disaster_zone"],
        evidence=dz_evidence,
    )

    # 因子5: BOM暴露度
    be_raw, be_evidence = calculate_bom_exposure_score(bom_data)
    factors["bom_exposure"] = FactorScore(
        name="bom_exposure",
        display_name=display_names["bom_exposure"],
        raw_score=be_raw,
        weight=weights["bom_exposure"],
        weighted_score=be_raw * weights["bom_exposure"],
        evidence=be_evidence,
    )

    # 因子6: 替代难度
    sd_raw, sd_evidence = calculate_substitution_difficulty_score(substitution_data)
    factors["substitution_difficulty"] = FactorScore(
        name="substitution_difficulty",
        display_name=display_names["substitution_difficulty"],
        raw_score=sd_raw,
        weight=weights["substitution_difficulty"],
        weighted_score=sd_raw * weights["substitution_difficulty"],
        evidence=sd_evidence,
    )

    # 因子7: 数据置信度调整
    conf_score, source_level, conf_coefficient = calculate_confidence_score(data_sources)
    factors["confidence_adjustment"] = FactorScore(
        name="confidence_adjustment",
        display_name=display_names["confidence_adjustment"],
        raw_score=conf_score,
        weight=weights["confidence_adjustment"],
        weighted_score=conf_score * weights["confidence_adjustment"],
        evidence=[f"source_level:{source_level}"],
        confidence=conf_coefficient,
    )

    # ── Step 2: 加权求和 ──
    base_score = sum(f.weighted_score for f in factors.values())

    # ── Step 3: 数据置信度系数调整 (0.8-1.2) ──
    adjusted_score = base_score * conf_coefficient

    # ── Step 3.5: 关键因子地板机制 ──
    # 当任一关键因子(行情/供应/政策/灾害)的原始分极高时，
    # 总风险分不应被其他零分因子过度稀释。
    # 这确保单一维度的极端风险(如实体的清单命中、工厂火灾)能正确反映到总评分。
    CRITICAL_FACTORS = ("market_trend", "supply_tension", "policy_compliance", "disaster_zone")
    max_critical_raw = max(
        (factors[cf].raw_score for cf in CRITICAL_FACTORS if cf in factors),
        default=0.0,
    )
    # 关键因子>=90 → 总分地板80(red级)
    # 关键因子>=70 → 总分地板60(orange级)
    if max_critical_raw >= 90:
        adjusted_score = max(adjusted_score, 80.0)
    elif max_critical_raw >= 70:
        adjusted_score = max(adjusted_score, 60.0)

    total_score = max(0.0, min(100.0, adjusted_score))

    # ── Step 4: 判断是否有足够数据 ──
    has_sufficient_data = _check_data_sufficiency(
        material_signals, body_signals, market_facts,
        policy_signals, disaster_signals, bom_data,
    )

    # ── Step 5: 风险等级映射 ──
    risk_level = score_to_risk_level(total_score, has_sufficient_data)

    # ── Step 6: 确定主风险因子 ──
    primary_factor = max(
        factors.keys(),
        key=lambda k: factors[k].weighted_score
    ) if factors else "unknown"

    # ── Step 7: 生成理由和证据 ──
    reason = _build_reason(category, factors, primary_factor, total_score, source_level)
    all_evidence: list[str] = []
    for f in factors.values():
        all_evidence.extend(f.evidence)

    # ── Step 8: 兼容Phase 1双轨分数 ──
    legacy_scores = _compute_legacy_track_scores(
        category, material_signals, body_signals, market_facts, buffers
    )

    return MultiFactorRiskResult(
        category=category,
        risk_level=risk_level.value,
        total_score=round(total_score, 1),
        base_score=round(base_score, 1),
        confidence_coefficient=conf_coefficient,
        factors=factors,
        primary_factor=primary_factor,
        reason=reason,
        evidence=all_evidence,
        legacy_track_scores=legacy_scores,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 内部辅助函数
# ═══════════════════════════════════════════════════════════════════════════════

def _check_data_sufficiency(
    material_signals: dict[str, Any],
    body_signals: dict[str, Any],
    market_facts: dict[str, Any],
    policy_signals: dict[str, Any] | None,
    disaster_signals: dict[str, Any] | None,
    bom_data: dict[str, Any] | None,
) -> bool:
    """
    检查是否有足够的数据支撑评分。

    至少需要以下条件之一:
    1. 有材料信号
    2. 有供需信号
    3. 有政策信号
    4. 有灾害信号
    5. 有BOM数据
    """
    if any(material_signals.values()):
        return True
    if body_signals.get("stock_down") or body_signals.get("lead_time_weeks"):
        return True
    if market_facts.get("price_up_confirmed") or market_facts.get("shortage_confirmed"):
        return True
    if policy_signals and any(
        v for v in policy_signals.values()
    ):
        return True
    if disaster_signals and any(
        v for v in disaster_signals.values()
    ):
        return True
    if bom_data:
        return True
    return False


def _build_lifecycle_result(
    category: str,
    lifecycle: str,
    risk_level: str,
    score: float,
) -> MultiFactorRiskResult:
    """构建生命周期直接升级的结果 (兼容Phase 1)"""
    default_factor = FactorScore(
        name="lifecycle",
        display_name="生命周期",
        raw_score=score,
        weight=1.0,
        weighted_score=score,
        evidence=[f"lifecycle={lifecycle}"],
    )
    return MultiFactorRiskResult(
        category=category,
        risk_level=risk_level,
        total_score=score,
        base_score=score,
        confidence_coefficient=1.0,
        factors={"lifecycle": default_factor},
        primary_factor="lifecycle",
        reason=f"物料生命周期状态为 {lifecycle}，直接判定{'极高' if risk_level == 'red' else '高'}风险",
        evidence=[f"lifecycle={lifecycle}"],
        legacy_track_scores={},
    )


def _build_reason(
    category: str,
    factors: dict[str, FactorScore],
    primary_factor: str,
    total_score: float,
    source_level: str,
) -> str:
    """构建风险判定原因说明"""
    parts: list[str] = []

    # 主因子说明
    pf = factors.get(primary_factor)
    if pf and pf.raw_score > 0:
        parts.append(f"{pf.display_name}({pf.raw_score:.0f}分)为主要风险驱动")

    # 高分因子汇总
    high_factors = [
        f for f in factors.values()
        if f.raw_score >= 60 and f.name != primary_factor
    ]
    if high_factors:
        names = "、".join(f.display_name for f in high_factors)
        parts.append(f"同时{names}也处于高位")

    # 置信度说明
    if source_level == "S":
        parts.append("数据源可信度高(S级)，评分置信度×1.2")
    elif source_level == "C":
        parts.append("数据源可信度低(C级)，评分置信度×0.8")

    # 风险等级说明
    if total_score >= 80:
        parts.append("已影响交付或成本，需立即应对")
    elif total_score >= 60:
        parts.append("高概率影响交付，建议启动预案")
    elif total_score >= 35:
        parts.append("早期预警信号，建议持续监控")

    return "；".join(parts) if parts else "多因子信号已形成风险评分"


def _compute_legacy_track_scores(
    category: str,
    material_signals: dict[str, Any],
    body_signals: dict[str, Any],
    market_facts: dict[str, Any],
    buffers: dict[str, Any],
) -> dict[str, float]:
    """
    计算兼容Phase 1的双轨分数。

    复用 Phase 1 的材料轨和供需轨逻辑, 使下游可对比验证。
    """
    model = get_category_model(category)

    # 材料轨分数 (Phase 1 逻辑)
    material_raw = 0.0
    for key, weight in MATERIAL_SIGNAL_WEIGHTS.items():
        if material_signals.get(key):
            material_raw += weight
    material_raw = min(material_raw, 100.0)
    material_weighted = round(material_raw * model["material"])

    # 供需轨分数 (Phase 1 逻辑)
    demand_raw = 0.0
    if body_signals.get("stock_down"):
        demand_raw += DEMAND_SUPPLY_SIGNAL_WEIGHTS["stock_down"]
    if market_facts.get("price_up_confirmed"):
        demand_raw += DEMAND_SUPPLY_SIGNAL_WEIGHTS["price_up_confirmed"]
    if market_facts.get("shortage_confirmed"):
        demand_raw += DEMAND_SUPPLY_SIGNAL_WEIGHTS["shortage_confirmed"]
    lead_time_weeks = body_signals.get("lead_time_weeks")
    if isinstance(lead_time_weeks, (int, float)):
        if lead_time_weeks >= 12:
            demand_raw += DEMAND_SUPPLY_SIGNAL_WEIGHTS["lead_time_long"]
        elif lead_time_weeks >= 8:
            demand_raw += DEMAND_SUPPLY_SIGNAL_WEIGHTS["lead_time_medium"]
    demand_raw = min(demand_raw, 100.0)
    demand_weighted = round(demand_raw * model["demand_supply"])

    return {
        "material": material_weighted,
        "demand_supply": demand_weighted,
    }
