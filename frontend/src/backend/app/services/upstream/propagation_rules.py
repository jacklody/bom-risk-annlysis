from __future__ import annotations


CATEGORY_MODEL_WEIGHTS = {
    # ── 成本驱动型（材料传导为主）──
    "pcb":                  {"material": 0.75, "demand_supply": 0.25, "display": "PCB"},
    "resistor":             {"material": 0.70, "demand_supply": 0.30, "display": "贴片电阻"},
    "relay":                {"material": 0.70, "demand_supply": 0.30, "display": "继电器"},
    "connector":            {"material": 0.70, "demand_supply": 0.30, "display": "连接器"},
    "inductor_transformer": {"material": 0.72, "demand_supply": 0.28, "display": "电感/变压器"},
    "wire_harness":         {"material": 0.78, "demand_supply": 0.22, "display": "线束/电缆"},
    "switch":               {"material": 0.65, "demand_supply": 0.35, "display": "开关/按键"},
    "aluminum_electrolytic_capacitor": {"material": 0.72, "demand_supply": 0.28, "display": "铝电解电容"},
    "film_capacitor":       {"material": 0.68, "demand_supply": 0.32, "display": "薄膜/安规电容"},
    "tantalum_capacitor":   {"material": 0.65, "demand_supply": 0.35, "display": "钽电容"},
    "varistor_thermistor":  {"material": 0.70, "demand_supply": 0.30, "display": "压敏/热敏电阻"},
    # ── 供需驱动型（产能/交期/行业需求为主）──
    "mcu":                  {"material": 0.15, "demand_supply": 0.85, "display": "MCU"},
    "power_ic":             {"material": 0.18, "demand_supply": 0.82, "display": "电源芯片"},
    "mosfet":               {"material": 0.22, "demand_supply": 0.78, "display": "MOSFET/功率器件"},
    "analog_ic":            {"material": 0.15, "demand_supply": 0.85, "display": "模拟芯片/运放"},
    "memory":               {"material": 0.10, "demand_supply": 0.90, "display": "存储芯片"},
    "fpga_cpld":            {"material": 0.10, "demand_supply": 0.90, "display": "FPGA/CPLD"},
    "crystal_oscillator":   {"material": 0.20, "demand_supply": 0.80, "display": "晶振/振荡器"},
    "sensor":               {"material": 0.18, "demand_supply": 0.82, "display": "传感器"},
    # ── 混合驱动型 ──
    "high_cap_mlcc":        {"material": 0.35, "demand_supply": 0.65, "display": "高容MLCC"},
    "mlcc":                 {"material": 0.35, "demand_supply": 0.65, "display": "MLCC"},
    "discrete_diode":       {"material": 0.45, "demand_supply": 0.55, "display": "分立器件/二极管"},
    "power_module":         {"material": 0.40, "demand_supply": 0.60, "display": "功率模块"},
}

MATERIAL_SIGNAL_WEIGHTS = {
    # PCB 相关
    "copper_foil_price_up": 32,
    "fiberglass_price_up": 18,
    "resin_price_up": 12,
    # 金属/贵金属（跨品类影响）
    "copper_price_up": 24,
    "silver_price_up": 18,
    "gold_price_up": 14,
    "tin_price_up": 10,
    "nickel_price_up": 10,
    "palladium_price_up": 8,
    "aluminum_price_up": 20,
    "aluminum_foil_price_up": 26,
    # 电容类
    "ceramic_powder_pressure": 22,
    "electrolyte_price_up": 18,
    "tantalum_price_up": 20,
    "plastic_film_price_up": 14,
    # IC/半导体
    "silicon_wafer_price_up": 20,
    "foundry_tight_capacity": 24,
    "osat_tight_capacity": 22,
    "leadframe_price_up": 12,
    "bonding_wire_price_up": 10,
    # 新材料
    "ruthenium_price_up": 16,
    "iron_ore_price_up": 10,
    "zinc_price_up": 12,
    "magnetic_core_price_up": 14,
    "engineering_plastics_price_up": 10,
}

DEMAND_SUPPLY_SIGNAL_WEIGHTS = {
    "stock_down": 20,
    "price_up_confirmed": 26,
    "shortage_confirmed": 30,
    "lead_time_long": 24,
    "lead_time_medium": 12,
}


def get_category_model(category: str | None) -> dict:
    return CATEGORY_MODEL_WEIGHTS.get(category or "", {"material": 0.4, "demand_supply": 0.6, "display": category or "未知品类"})


# ══════════════════════════════════════════════════════════════════════════════
# T2-001: 多因子风险评分引擎 — 权重配置
# ══════════════════════════════════════════════════════════════════════════════

# ── 七因子全局权重 (PRD 定义，总和 = 1.0) ──
MULTI_FACTOR_WEIGHTS: dict[str, float] = {
    "market_trend":           0.25,   # 行情趋势分
    "supply_tension":         0.20,   # 供应紧张分
    "policy_compliance":      0.15,   # 政策合规分
    "disaster_zone":          0.10,   # 灾害区域分
    "bom_exposure":           0.15,   # BOM暴露度
    "substitution_difficulty": 0.10,  # 替代难度
    "confidence_adjustment":  0.05,   # 数据置信度调整 (分数部分)
}

# ── 七因子显示名称 ──
MULTI_FACTOR_DISPLAY_NAMES: dict[str, str] = {
    "market_trend":           "行情趋势分",
    "supply_tension":         "供应紧张分",
    "policy_compliance":      "政策合规分",
    "disaster_zone":          "灾害区域分",
    "bom_exposure":           "BOM暴露度",
    "substitution_difficulty": "替代难度",
    "confidence_adjustment":  "数据置信度调整",
}

# ── 数据置信度等级 → 调整系数 ──
# 置信度系数作为最终调整乘数作用于 base_score
CONFIDENCE_COEFFICIENTS: dict[str, float] = {
    "S": 1.2,   # 权威来源 + 多源交叉验证
    "A": 1.1,   # 可靠来源 + 部分验证
    "B": 1.0,   # 一般来源
    "C": 0.8,   # 低可信度/单一来源
}

# ── 数据源级别 → 置信度基础分 ──
CONFIDENCE_SOURCE_SCORES: dict[str, float] = {
    "S": 100.0,
    "A": 75.0,
    "B": 50.0,
    "C": 25.0,
}

# ── 政策合规信号权重 (0-100分制) ──
POLICY_COMPLIANCE_SIGNALS: dict[str, float] = {
    "entity_list_hit":        100.0,  # 实体清单命中 → 直接满分
    "bis_restriction":        90.0,   # BIS出口管制
    "ustr_sanction":          90.0,   # USTR制裁
    "export_control":         80.0,   # 出口管制
    "trade_restriction":      75.0,   # 贸易限制
    "tariff_increase":        70.0,   # 关税上调
    "compliance_warning":     50.0,   # 合规预警
    "regulatory_change":      40.0,   # 法规变化
}

# ── 灾害区域信号权重 (0-100分制) ──
DISASTER_ZONE_SIGNALS: dict[str, float] = {
    "earthquake_severe":      100.0,  # 严重地震 (7级+)
    "earthquake_moderate":    70.0,   # 中等地震 (5-7级)
    "typhoon_severe":         90.0,   # 强台风
    "typhoon_moderate":       60.0,   # 中等台风
    "flood_severe":           85.0,   # 严重洪涝
    "flood_moderate":         55.0,   # 中等洪涝
    "fire_event":             80.0,   # 火灾事件
    "pandemic_disruption":    75.0,   # 疫情扰动
    "power_outage":           65.0,   # 停电事件
    "transport_disruption":   50.0,   # 运输中断
}

# ── 替代难度评分参数 ──
SUBSTITUTION_PARAMS: dict[str, float] = {
    "no_alternative":         100.0,  # 无替代料 → 直接满分
    "cert_cycle_long_months": 80.0,   # 认证周期 > 12月
    "cert_cycle_medium_months": 50.0, # 认证周期 6-12月
    "cert_cycle_short_months": 20.0,  # 认证周期 < 6月
    "pin_incompatible":       40.0,   # Pin不兼容
    "pin_compatible_partial": 20.0,   # Pin部分兼容
    "pin_fully_compatible":   0.0,    # Pin完全兼容
    "single_alt_penalty":     30.0,   # 仅1个替代料
    "few_alt_penalty":        15.0,   # 2-3个替代料
}


def get_multi_factor_weights() -> dict[str, float]:
    """获取七因子权重配置的副本"""
    return dict(MULTI_FACTOR_WEIGHTS)


def get_confidence_coefficient(level: str) -> float:
    """
    获取数据置信度调整系数。

    Args:
        level: 数据源级别 ('S', 'A', 'B', 'C')

    Returns:
        调整系数 (0.8-1.2)
    """
    return CONFIDENCE_COEFFICIENTS.get(level.upper(), 1.0)

# ══════════════════════════════════════════════════════════════════
# T2-007: 自动提级规则引擎 — 规则配置
# ══════════════════════════════════════════════════════════════════

from dataclasses import dataclass, field
from typing import Callable


# ── 提级规则开关 ──
# 每条规则可独立启用/禁用，默认全部启用
ESCALATION_RULE_ENABLED: dict[str, bool] = {
    "R1": True,   # S级来源政策事件提级
    "R2": True,   # 原厂PCN/EOL/LTB提级
    "R3": True,   # 关键材料价格暴涨提级
    "R4": True,   # GDACS Red级灾害提级
    "R5": True,   # 分销库存低于安全库存提级
    "R6": True,   # 单一来源提级
    "R7": True,   # 数据缺失待确认
}


# ── 提级规则优先级排序 (值越大优先级越高) ──
ESCALATION_RULE_PRIORITY: dict[str, int] = {
    "R1": 90,   # 政策合规 — 最高优先级
    "R2": 85,   # 生命周期事件
    "R3": 70,   # 价格暴涨
    "R4": 75,   # 自然灾害
    "R5": 65,   # 库存危机
    "R6": 60,   # 单一来源
    "R7": 50,   # 数据缺失
}


# ── R3: 关键材料价格涨幅阈值 ──
# 格式: {材料关键标识: 7日涨幅阈值(%)}
PRICE_SURGE_THRESHOLDS: dict[str, float] = {
    "copper": 10.0,
    "aluminum": 12.0,
    "gold": 8.0,
    "silver": 10.0,
    "tin": 15.0,
    "nickel": 12.0,
    "tantalum": 15.0,
    "silicon": 20.0,
    "rare_earth": 25.0,
    "ceramic": 15.0,
    "resin": 18.0,
    "fiberglass": 15.0,
}


# ── R5: 库存与交期阈值 ──
INVENTORY_SAFETY_MULTIPLIER: float = 0.5       # 库存低于安全库存的50%视为危险
LEAD_TIME_INCREASE_THRESHOLD: float = 50.0     # 交期拉长超过50%


# ── R1: S级来源标识 (权威机构/部门名称) ──
# 仅包含数据源机构标识，不包含通用信号类型
S_LEVEL_POLICY_SOURCES: set[str] = {
    "BIS", "USTR", "USGS",
}


# ── R2: 生命周期状态触发值 ──
LIFECYCLE_ESCALATION_TRIGGERS: set[str] = {
    "PCN",       # Product Change Notification
    "EOL",       # End of Life
    "LTB",       # Last Time Buy
    "NRND",      # Not Recommended for New Designs
    "END_OF_LIFE",
    "LAST_BUY",
}


@dataclass
class EscalationRuleConfig:
    """单条提级规则的配置。

    Attributes:
        rule_id: 规则编号 (R1-R7)
        name: 规则中文名称
        description: 规则详细描述
        enabled: 是否启用
        priority: 优先级 (越大越优先)
        target_level: 触发后目标风险等级
        target_level_if_no_alternative: 无替代料时的目标等级 (仅部分规则使用)
        escalate_one_level: 是否提升一级 (而非直接设定目标等级)
    """
    rule_id: str
    name: str
    description: str
    enabled: bool = True
    priority: int = 50
    target_level: str = "yellow"
    target_level_if_no_alternative: str = ""
    escalate_one_level: bool = False


# ── 七条提级规则配置表 ──
ESCALATION_RULES_CONFIG: dict[str, EscalationRuleConfig] = {
    "R1": EscalationRuleConfig(
        rule_id="R1",
        name="S级来源政策事件",
        description="BIS/USTR/USGS等S级来源出现出口管制/实体清单/关税变化，直接提升至橙色或红色",
        enabled=True,
        priority=90,
        target_level="red",
    ),
    "R2": EscalationRuleConfig(
        rule_id="R2",
        name="原厂PCN/EOL/LTB",
        description="原厂发布PCN/EOL/LTB通知命中BOM型号，有替代料提升至橙色，无替代料提升至红色",
        enabled=True,
        priority=85,
        target_level="orange",
        target_level_if_no_alternative="red",
    ),
    "R3": EscalationRuleConfig(
        rule_id="R3",
        name="关键材料价格暴涨",
        description="关键材料7日涨幅超过阈值且命中高用量BOM，提升一级",
        enabled=True,
        priority=70,
        target_level="",
        escalate_one_level=True,
    ),
    "R4": EscalationRuleConfig(
        rule_id="R4",
        name="GDACS Red级灾害",
        description="供应商所在地出现GDACS Red级灾害事件，提升一级并标记区域风险",
        enabled=True,
        priority=75,
        target_level="",
        escalate_one_level=True,
    ),
    "R5": EscalationRuleConfig(
        rule_id="R5",
        name="分销库存危机",
        description="分销库存低于安全库存且交期拉长超过50%，提升至橙色",
        enabled=True,
        priority=65,
        target_level="orange",
    ),
    "R6": EscalationRuleConfig(
        rule_id="R6",
        name="单一来源风险",
        description="单一品牌/单一供应商且无替代料，至少黄色，叠加事件后橙色",
        enabled=True,
        priority=60,
        target_level="yellow",
        target_level_if_no_alternative="orange",
    ),
    "R7": EscalationRuleConfig(
        rule_id="R7",
        name="数据缺失待确认",
        description="数据缺失但BOM关键度高，显示灰色待确认",
        enabled=True,
        priority=50,
        target_level="gray",
    ),
}


def get_escalation_rule(rule_id: str) -> EscalationRuleConfig | None:
    """获取指定提级规则配置。

    Args:
        rule_id: 规则编号 (R1-R7)

    Returns:
        EscalationRuleConfig 或 None
    """
    return ESCALATION_RULES_CONFIG.get(rule_id)


def is_rule_enabled(rule_id: str) -> bool:
    """检查指定规则是否启用。

    Args:
        rule_id: 规则编号 (R1-R7)

    Returns:
        bool: 规则是否启用
    """
    return ESCALATION_RULE_ENABLED.get(rule_id, False)


def set_rule_enabled(rule_id: str, enabled: bool) -> None:
    """动态启用/禁用指定规则。

    Args:
        rule_id: 规则编号 (R1-R7)
        enabled: 是否启用
    """
    if rule_id in ESCALATION_RULE_ENABLED:
        ESCALATION_RULE_ENABLED[rule_id] = enabled


def get_all_escalation_rules() -> dict[str, EscalationRuleConfig]:
    """获取所有提级规则配置。

    Returns:
        规则编号到配置的映射字典
    """
    return dict(ESCALATION_RULES_CONFIG)
