"""
品类分类器 — v4.0 改造版
规则引擎（21品类） + LLM 兜底 + 偏门物料标识
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from app.services.upstream.mlcc_classifier import classify_mlcc

logger = logging.getLogger(__name__)

# ── LLM 分类缓存（进程内，避免重复调用） ──
_llm_cache: dict[str, dict] = {}
_LLM_CACHE_MAX = 500


@dataclass(frozen=True)
class ComponentCategoryResult:
    raw_text: str
    manufacturer: str = ""
    category: str = "unknown"
    display_name: str = "未知品类"
    driver_type: str = "unknown"  # material_cost / demand_supply / hybrid / unknown
    confidence: float = 0.0
    upstream_materials: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    reason: str = ""
    is_high_risk: bool = False      # v4.0: 偏门物料标识
    risk_reason: str = ""           # v4.0: 偏门原因


# ── 品类元数据表（品类→展示名、驱动类型、上游材料） ──
_CATEGORY_META = {
    "pcb": ("PCB/印制板", "material_cost", ["copper_foil", "fiberglass_cloth", "epoxy_resin", "ccl"]),
    "resistor": ("贴片电阻", "material_cost", ["ceramic_substrate", "ruthenium_paste", "silver_palladium", "nickel", "tin"]),
    "inductor_transformer": ("电感/变压器", "material_cost", ["copper", "ferrite", "magnetic_core", "iron_powder"]),
    "aluminum_electrolytic_capacitor": ("铝电解电容", "material_cost", ["aluminum_foil", "electrolyte", "paper_separator", "rubber_seal"]),
    "film_capacitor": ("薄膜电容", "material_cost", ["plastic_film", "metallized_film", "aluminum_zinc_metal", "resin"]),
    "tantalum_capacitor": ("钽电容", "material_cost", ["tantalum_powder", "tantalum_wire", "silver", "conductive_polymer"]),
    "mcu": ("MCU/微控制器", "demand_supply", ["silicon_wafer", "foundry_capacity", "osat_capacity", "leadframe", "bonding_wire"]),
    "power_ic": ("电源芯片/PMIC", "demand_supply", ["silicon_wafer", "foundry_capacity", "packaging_capacity", "copper_clip"]),
    "mosfet": ("MOSFET/功率器件", "demand_supply", ["silicon_wafer", "silicon_carbide", "copper_clip", "ceramic_substrate", "sinter_silver"]),
    "discrete_diode": ("分立器件/二极管", "hybrid", ["silicon_wafer", "copper", "leadframe", "molding_compound"]),
    "analog_ic": ("模拟芯片/运放", "demand_supply", ["silicon_wafer", "foundry_capacity"]),
    "memory": ("存储芯片", "demand_supply", ["silicon_wafer", "advanced_node_capacity"]),
    "fpga_cpld": ("FPGA/CPLD", "demand_supply", ["silicon_wafer", "advanced_node_capacity", "packaging_substrate"]),
    "relay": ("继电器", "material_cost", ["copper", "silver", "engineering_plastics", "iron_nickel_alloy"]),
    "connector": ("连接器", "material_cost", ["copper", "gold", "engineering_plastics", "tin", "nickel"]),
    "wire_harness": ("线束/电缆", "material_cost", ["copper", "pvc", "tpe", "tin"]),
    "switch": ("开关/按键", "material_cost", ["copper", "silver", "steel", "engineering_plastics"]),
    "power_module": ("功率模块", "hybrid", ["copper", "alumina_ceramic", "aluminum_nitride", "silver_sinter", "silicon_gel"]),
    "crystal_oscillator": ("晶振/振荡器", "demand_supply", ["quartz", "ceramic_package", "leadframe"]),
    "sensor": ("传感器", "demand_supply", ["silicon_wafer", "ceramic_package", "magnetic_material"]),
    "varistor_thermistor": ("压敏/热敏电阻", "material_cost", ["zinc_oxide", "bismuth_oxide", "silver", "copper", "epoxy_resin"]),
}


_CATEGORY_RULES = [
    # ── 被动元件 ──
    {
        "category": "pcb",
        "keywords": ["pcb", "pcba", "fr4", "ccl", "印制板", "线路板", "电路板", "覆铜板"],
    },
    {
        "category": "resistor",
        "keywords": ["resistor", "chip resistor", "贴片电阻", "厚膜电阻", "薄膜电阻", "采样电阻", "shunt"],
    },
    {
        "category": "inductor_transformer",
        "keywords": ["inductor", "transformer", "电感", "变压器", "磁珠", "共模电感", "功率电感", "bead", "choke"],
    },
    # ── 电容器 ──
    {
        "category": "aluminum_electrolytic_capacitor",
        "keywords": ["aluminum electrolytic", "electrolytic capacitor", "铝电解", "电解电容", "贴片铝电解"],
    },
    {
        "category": "film_capacitor",
        "keywords": ["film capacitor", "film cap", "metallized film", "polypropylene capacitor", "薄膜电容", "金属化薄膜", "cbb电容", "film", "安规电容", "x2电容", "y2电容"],
    },
    {
        "category": "tantalum_capacitor",
        "keywords": ["tantalum", "tantalum capacitor", "钽电容", "聚合物钽"],
    },
    # ── 半导体 ──
    {
        "category": "mcu",
        "keywords": ["mcu", "microcontroller", "微控制器", "stm32", "gd32", "n32", "hc32", "mm32", "at32", "单片机", "arm cortex-m", "risc-v mcu"],
        "brand_hints": ["st", "意法", "nxp", "renesas", "兆易", "gigadevice", "gd", "nations", "国民技术", "中微", "雅特力", "极海"],
    },
    {
        "category": "power_ic",
        "keywords": ["pmic", "power ic", "dc-dc", "ldo", "buck", "boost", "电源芯片", "电源管理", "charger", "charger ic", "充电芯片", "ac-dc", "pwm controller", "pfc"],
    },
    {
        "category": "mosfet",
        "keywords": ["mosfet", "igbt", "sic", "gan", "power transistor", "功率管", "场效应管", "氮化镓", "碳化硅", "coolmos", "trench mos", "sj mos", "super junction"],
        "brand_hints": ["infineon", "英飞凌", "onsemi", "安森美", "st", "vishay", "nxp", "华润微", "士兰微", "新洁能", "东微"],
    },
    {
        "category": "discrete_diode",
        "keywords": ["diode", "tvs", "esd", "zener", "schottky", "整流", "稳压管", "肖特基", "快恢复", "整流桥", "二极管", "三极管", "bjt", "transistor npn", "transistor pnp", "晶闸管", "scr", "triac"],
        "brand_hints": ["扬杰", "长晶", "changjing", "yangjie", "vishay", "diodes", "安世", "nexperia"],
    },
    {
        "category": "analog_ic",
        "keywords": ["op amp", "opamp", "comparator", "运算放大器", "比较器", "adc", "dac", "模拟开关", "analog switch", "仪表放大器", "电流检测"],
    },
    {
        "category": "memory",
        "keywords": ["dram", "nand", "nor flash", "eeprom", "flash", "sdram", "ddr", "lpddr", "emmc", "ufs", "存储", "内存"],
    },
    {
        "category": "fpga_cpld",
        "keywords": ["fpga", "cpld", "soc fpga", "可编程逻辑"],
    },
    # ── 机电/连接 ──
    {
        "category": "relay",
        "keywords": ["relay", "继电器", "固态继电器", "ssr", "功率继电器", "信号继电器"],
    },
    {
        "category": "connector",
        "keywords": ["connector", "连接器", "端子", "排针", "排母", "fpc", "ffc", "usb", "type-c", "rj45", "板对板", "线对板", "btb", "w tb"],
    },
    {
        "category": "wire_harness",
        "keywords": ["cable", "wire", "harness", "线束", "电缆", "导线", "排线", "电子线", "ul", "awg"],
    },
    {
        "category": "switch",
        "keywords": ["switch", "button", "开关", "按键", "轻触开关", "拨动开关", "微动开关", "tact"],
    },
    {
        "category": "power_module",
        "keywords": ["power module", "ipm", "igbt module", "sic module", "功率模块", "智能功率模块"],
    },
    # ── 其他 ──
    {
        "category": "crystal_oscillator",
        "keywords": ["crystal", "oscillator", "晶振", "振荡器", "谐振器", "tcxo", "ocxo", "mhz", "khz"],
    },
    {
        "category": "sensor",
        "keywords": ["sensor", "传感器", "温度传感器", "hall", "霍尔", "current sensor", "加速度计", "陀螺仪", "mems"],
    },
    {
        "category": "varistor_thermistor",
        "keywords": ["varistor", "mov", "压敏电阻", "ntc", "ptc", "热敏电阻", "surge protector", "浪涌"],
    },
]


def _make_result(
    raw_text: str,
    manufacturer: str,
    category: str,
    confidence: float,
    reason: str,
    tags: list[str] | None = None,
    is_high_risk: bool = False,
    risk_reason: str = "",
) -> ComponentCategoryResult:
    """根据品类ID构建标准结果"""
    meta = _CATEGORY_META.get(category)
    if meta:
        display_name, driver_type, upstream = meta
    else:
        display_name = "未知品类"
        driver_type = "unknown"
        upstream = []

    return ComponentCategoryResult(
        raw_text=raw_text,
        manufacturer=manufacturer,
        category=category,
        display_name=display_name,
        driver_type=driver_type,
        confidence=confidence,
        upstream_materials=upstream,
        tags=tags or [driver_type],
        reason=reason,
        is_high_risk=is_high_risk,
        risk_reason=risk_reason,
    )


def _try_llm_classify(description: str, manufacturer: str) -> dict:
    """尝试 LLM 分类（带缓存）"""
    cache_key = f"{description}|{manufacturer}".strip().lower()

    if cache_key in _llm_cache:
        return _llm_cache[cache_key]

    try:
        from app.services.llm_client import LLMClient
        client = LLMClient()
        if not client.available:
            return {"category": "unknown", "confidence": 0.0}

        result = client.classify_component(description, manufacturer)

        # 缓存
        if len(_llm_cache) < _LLM_CACHE_MAX:
            _llm_cache[cache_key] = result

        return result
    except Exception as e:
        logger.warning(f"LLM 品类分类异常: {e}")
        return {"category": "unknown", "confidence": 0.0}


def classify_component_category(
    description: str | None,
    manufacturer: str | None = "",
    enable_llm_fallback: bool = True,
) -> ComponentCategoryResult:
    """
    品类分类主入口。
    策略：MLCC专用 → 规则匹配 → LLM兜底（v4.0）
    """
    raw_text = description or ""
    maker = manufacturer or ""
    text_haystack = raw_text.lower()
    maker_haystack = maker.lower()

    # ── Step 1: MLCC 专用分类器（最高优先级） ──
    mlcc = classify_mlcc(raw_text)
    if mlcc.is_mlcc:
        tags = ["mlcc"]
        if mlcc.high_capacitance_flag:
            tags.append("high_capacitance")
        # MLCC 高容检测：判断是否偏门
        is_high_risk = mlcc.high_capacitance_flag
        risk_reason = "高容MLCC（供应商集中，产能易被挤占）" if mlcc.high_capacitance_flag else ""
        return ComponentCategoryResult(
            raw_text=raw_text,
            manufacturer=maker,
            category="high_cap_mlcc" if mlcc.high_capacitance_flag else "mlcc",
            display_name="高容MLCC" if mlcc.high_capacitance_flag else "MLCC",
            driver_type="hybrid",
            confidence=mlcc.confidence,
            upstream_materials=["ceramic_powder", "nickel", "palladium", "silver", "capacity_utilization"],
            tags=tags,
            reason=mlcc.reason,
            is_high_risk=is_high_risk,
            risk_reason=risk_reason,
        )

    # ── Step 2: 规则匹配 ──
    for rule in _CATEGORY_RULES:
        keyword_hit = any(kw.lower() in text_haystack for kw in rule["keywords"])
        brand_hit = any(b.lower() == maker_haystack for b in rule.get("brand_hints", []))
        if keyword_hit or brand_hit:
            confidence = 0.88 if keyword_hit else 0.65
            return _make_result(
                raw_text=raw_text,
                manufacturer=maker,
                category=rule["category"],
                confidence=confidence,
                reason="matched category keyword" if keyword_hit else "matched manufacturer/category hint",
            )

    # ── Step 3: LLM 兜底（v4.0 新增） ──
    if enable_llm_fallback and raw_text.strip():
        llm_result = _try_llm_classify(raw_text, maker)
        llm_category = llm_result.get("category", "unknown")
        llm_conf = llm_result.get("confidence", 0.0)

        if llm_category != "unknown" and llm_conf >= 0.5:
            is_high_risk = llm_result.get("is_high_risk", False)
            risk_reason = llm_result.get("risk_reason", "") or ""
            return _make_result(
                raw_text=raw_text,
                manufacturer=maker,
                category=llm_category,
                confidence=llm_conf,
                reason=f"LLM classified (high_risk={is_high_risk})",
                is_high_risk=is_high_risk,
                risk_reason=risk_reason,
            )

    # ── Step 4: 完全无法分类 ──
    return ComponentCategoryResult(
        raw_text=raw_text,
        manufacturer=maker,
        category="unknown",
        display_name="未知品类",
        driver_type="unknown",
        confidence=0.2,
        tags=["information_insufficient"],
        reason="no reliable category signal matched (rules + LLM both failed)",
    )
