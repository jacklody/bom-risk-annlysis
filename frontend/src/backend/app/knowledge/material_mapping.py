"""品类 → 原材料 → 数据源 → 传导系数 完整映射字典。

覆盖 9 大元器件品类 × 32 种上游原材料，按三大数据域组织：
- 有色金属域 (metals): Cu/Al/Ag/Sn/Ni/Zn，主源 metals-api.com
- 稀土 & 小金属域 (rare_earth): 氧化镨钕/氧化镝/氧化钇/TiO₂/BaCO₃/钽粉/钽丝/二氧化锰
- 化工 & 非金属域 (chemical): 环氧树脂/玻纤布/电解液/PP/PET/PA66/铁氧体/漆包铜线

使用方式:
    from app.knowledge.material_mapping import (
        CATEGORY_MATERIAL_MAP,
        MATERIAL_REGISTRY,
        get_materials_for_category,
        get_categories_for_material,
        get_sources_for_domain,
        RARE_EARTH_AMPLIFIER,
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ── 稀土传导系数放大因子 ──────────────────────────────────
RARE_EARTH_AMPLIFIER = 1.6


# ── 材料条目定义 ──────────────────────────────────────────

@dataclass
class MaterialEntry:
    key: str                # 唯一标识, 如 "cu_cathode"
    name_zh: str            # 中文名, 如 "电解铜"
    domain: str             # 数据域: "metals" | "rare_earth" | "chemical"
    cost_ratio: float       # 成本占比 (传导系数), 0.0~1.0
    primary_source: str     # 主数据源标识
    backup_source: str      # 备数据源标识
    fetch_frequency: str    # "daily" | "weekly" | "monthly"
    is_rare_earth: bool = False  # 是否触发 1.6× 放大器
    symbol: str = ""        # 金属符号 (有色金属域用)
    price_multiplier: float = 1.0  # 加工溢价系数 (如铜箔 ×1.12)
    unit: str = "元/吨"     # 价格单位


# ── 全部 32 种材料注册表 ──────────────────────────────────

MATERIAL_REGISTRY: Dict[str, MaterialEntry] = {
    # ═══ 有色金属域 (metals) ═══
    "cu_cathode": MaterialEntry(
        key="cu_cathode", name_zh="电解铜", domain="metals",
        cost_ratio=0.12, primary_source="metals_api", backup_source="changjiang",
        fetch_frequency="daily", symbol="Cu", unit="元/吨",
    ),
    "cu_foil": MaterialEntry(
        key="cu_foil", name_zh="铜箔(PCB)", domain="metals",
        cost_ratio=0.15, primary_source="metals_api", backup_source="changjiang",
        fetch_frequency="daily", symbol="Cu", price_multiplier=1.12, unit="元/吨",
    ),
    "cu_ball": MaterialEntry(
        key="cu_ball", name_zh="铜球(填孔)", domain="metals",
        cost_ratio=0.05, primary_source="metals_api", backup_source="changjiang",
        fetch_frequency="daily", symbol="Cu", unit="元/吨",
    ),
    "cu_terminal": MaterialEntry(
        key="cu_terminal", name_zh="铜(端头)", domain="metals",
        cost_ratio=0.08, primary_source="metals_api", backup_source="changjiang",
        fetch_frequency="daily", symbol="Cu", unit="元/吨",
    ),
    "al_ingot": MaterialEntry(
        key="al_ingot", name_zh="铝锭A00", domain="metals",
        cost_ratio=0.40, primary_source="metals_api", backup_source="shialu",
        fetch_frequency="daily", symbol="Al", unit="元/吨",
    ),
    "al_foil_anode": MaterialEntry(
        key="al_foil_anode", name_zh="高纯铝箔(阳极)", domain="metals",
        cost_ratio=0.20, primary_source="metals_api", backup_source="changjiang",
        fetch_frequency="daily", symbol="Al", price_multiplier=1.08, unit="元/吨",
    ),
    "al_foil_cathode": MaterialEntry(
        key="al_foil_cathode", name_zh="铝箔(阴极)", domain="metals",
        cost_ratio=0.10, primary_source="metals_api", backup_source="changjiang",
        fetch_frequency="daily", symbol="Al", unit="元/吨",
    ),
    "al_metallization": MaterialEntry(
        key="al_metallization", name_zh="铝(金属化层)", domain="metals",
        cost_ratio=0.03, primary_source="metals_api", backup_source="changjiang",
        fetch_frequency="daily", symbol="Al", unit="元/吨",
    ),
    "ag_ingot": MaterialEntry(
        key="ag_ingot", name_zh="白银", domain="metals",
        cost_ratio=0.15, primary_source="metals_api", backup_source="cngold",
        fetch_frequency="daily", symbol="Ag", unit="元/克",
    ),
    "ag_paste": MaterialEntry(
        key="ag_paste", name_zh="银浆", domain="metals",
        cost_ratio=0.08, primary_source="metals_api", backup_source="cngold",
        fetch_frequency="daily", symbol="Ag", unit="元/克",
    ),
    "tin": MaterialEntry(
        key="tin", name_zh="锡(焊料)", domain="metals",
        cost_ratio=0.05, primary_source="metals_api", backup_source="lme",
        fetch_frequency="daily", symbol="Sn", unit="元/吨",
    ),
    "nickel_powder": MaterialEntry(
        key="nickel_powder", name_zh="镍粉(电极)", domain="metals",
        cost_ratio=0.15, primary_source="metals_api", backup_source="lme",
        fetch_frequency="daily", symbol="Ni", unit="元/吨",
    ),
    "ni_plating": MaterialEntry(
        key="ni_plating", name_zh="镍(镀层)", domain="metals",
        cost_ratio=0.03, primary_source="metals_api", backup_source="lme",
        fetch_frequency="daily", symbol="Ni", unit="元/吨",
    ),
    "zinc": MaterialEntry(
        key="zinc", name_zh="锌(金属化层)", domain="metals",
        cost_ratio=0.05, primary_source="metals_api", backup_source="lme",
        fetch_frequency="daily", symbol="Zn", unit="元/吨",
    ),

    # ═══ 稀土 & 小金属域 (rare_earth) ═══
    "titanium_dioxide": MaterialEntry(
        key="titanium_dioxide", name_zh="钛白粉TiO₂", domain="rare_earth",
        cost_ratio=0.12, primary_source="chem_100ppi", backup_source="sci99",
        fetch_frequency="weekly", unit="元/吨",
    ),
    "barium_carbonate": MaterialEntry(
        key="barium_carbonate", name_zh="碳酸钡BaCO₃", domain="rare_earth",
        cost_ratio=0.10, primary_source="baiinfo", backup_source="asian_metal",
        fetch_frequency="weekly", unit="元/吨",
    ),
    "dysprosium_oxide": MaterialEntry(
        key="dysprosium_oxide", name_zh="氧化镝Dy₂O₃", domain="rare_earth",
        cost_ratio=0.06, primary_source="re_association", backup_source="asian_metal",
        fetch_frequency="daily", is_rare_earth=True, unit="万元/吨",
    ),
    "yttrium_oxide": MaterialEntry(
        key="yttrium_oxide", name_zh="氧化钇Y₂O₃", domain="rare_earth",
        cost_ratio=0.05, primary_source="re_association", backup_source="asian_metal",
        fetch_frequency="daily", is_rare_earth=True, unit="万元/吨",
    ),
    "prnd_oxide": MaterialEntry(
        key="prnd_oxide", name_zh="氧化镨钕", domain="rare_earth",
        cost_ratio=0.08, primary_source="re_association", backup_source="asian_metal",
        fetch_frequency="daily", is_rare_earth=True, unit="万元/吨",
    ),
    "tantalum_powder": MaterialEntry(
        key="tantalum_powder", name_zh="钽粉", domain="rare_earth",
        cost_ratio=0.45, primary_source="asian_metal", backup_source="cngold",
        fetch_frequency="weekly", unit="元/公斤",
    ),
    "tantalum_wire": MaterialEntry(
        key="tantalum_wire", name_zh="钽丝", domain="rare_earth",
        cost_ratio=0.10, primary_source="asian_metal", backup_source="cngold",
        fetch_frequency="weekly", unit="元/公斤",
    ),
    "manganese_dioxide": MaterialEntry(
        key="manganese_dioxide", name_zh="二氧化锰", domain="rare_earth",
        cost_ratio=0.05, primary_source="chem_100ppi", backup_source="",
        fetch_frequency="weekly", unit="元/吨",
    ),

    # ═══ 化工 & 非金属域 (chemical) ═══
    "ba_resin": MaterialEntry(
        key="ba_resin", name_zh="双酚A树脂", domain="chemical",
        cost_ratio=0.08, primary_source="chem_100ppi", backup_source="sci99",
        fetch_frequency="weekly", unit="元/吨",
    ),
    "polyester_pet": MaterialEntry(
        key="polyester_pet", name_zh="聚酯PET膜", domain="chemical",
        cost_ratio=0.10, primary_source="chem_100ppi", backup_source="sci99",
        fetch_frequency="weekly", unit="元/吨",
    ),
    "epoxy_resin": MaterialEntry(
        key="epoxy_resin", name_zh="环氧树脂E-51", domain="chemical",
        cost_ratio=0.08, primary_source="chem_100ppi", backup_source="sci99",
        fetch_frequency="weekly", unit="元/吨",
    ),
    "glass_fiber_cloth": MaterialEntry(
        key="glass_fiber_cloth", name_zh="玻纤布7628", domain="chemical",
        cost_ratio=0.10, primary_source="sci99", backup_source="chem_100ppi",
        fetch_frequency="weekly", unit="元/米",
    ),
    "electrolyte": MaterialEntry(
        key="electrolyte", name_zh="电解液(铝电容)", domain="chemical",
        cost_ratio=0.10, primary_source="sci99", backup_source="baiinfo",
        fetch_frequency="weekly", unit="元/吨",
    ),
    "electrolytic_paper": MaterialEntry(
        key="electrolytic_paper", name_zh="电解纸", domain="chemical",
        cost_ratio=0.05, primary_source="industry_online", backup_source="",
        fetch_frequency="monthly", unit="元/吨",
    ),
    "polypropylene": MaterialEntry(
        key="polypropylene", name_zh="聚丙烯PP-T30S", domain="chemical",
        cost_ratio=0.25, primary_source="chem_100ppi", backup_source="sci99",
        fetch_frequency="weekly", unit="元/吨",
    ),
    "polyester_film": MaterialEntry(
        key="polyester_film", name_zh="聚酯切片PET", domain="chemical",
        cost_ratio=0.20, primary_source="chem_100ppi", backup_source="sci99",
        fetch_frequency="weekly", unit="元/吨",
    ),
    "engineering_plastics": MaterialEntry(
        key="engineering_plastics", name_zh="工程塑料PA66", domain="chemical",
        cost_ratio=0.10, primary_source="chem_100ppi", backup_source="sci99",
        fetch_frequency="weekly", unit="元/吨",
    ),
    "ferrite_core": MaterialEntry(
        key="ferrite_core", name_zh="铁氧体磁芯", domain="chemical",
        cost_ratio=0.15, primary_source="chem_100ppi", backup_source="mysteel",
        fetch_frequency="weekly", unit="元/吨",
    ),
    "enameled_cu_wire": MaterialEntry(
        key="enameled_cu_wire", name_zh="漆包铜线", domain="metals",
        cost_ratio=0.20, primary_source="metals_api", backup_source="changjiang",
        fetch_frequency="daily", symbol="Cu", price_multiplier=1.05, unit="元/吨",
    ),
}


# ── 品类 → 材料列表映射 ───────────────────────────────────

CATEGORY_MATERIAL_MAP: Dict[str, List[MaterialEntry]] = {
    "relay": [
        MATERIAL_REGISTRY["cu_cathode"],
        MATERIAL_REGISTRY["ag_ingot"],
        MATERIAL_REGISTRY["engineering_plastics"],
    ],
    "pcb": [
        MATERIAL_REGISTRY["cu_foil"],
        MATERIAL_REGISTRY["glass_fiber_cloth"],
        MATERIAL_REGISTRY["epoxy_resin"],
        MATERIAL_REGISTRY["cu_ball"],
    ],
    "mlcc": [
        MATERIAL_REGISTRY["titanium_dioxide"],
        MATERIAL_REGISTRY["barium_carbonate"],
        MATERIAL_REGISTRY["dysprosium_oxide"],
        MATERIAL_REGISTRY["yttrium_oxide"],
        MATERIAL_REGISTRY["nickel_powder"],
        MATERIAL_REGISTRY["cu_terminal"],
    ],
    "high_cap_mlcc": [  # 高容 MLCC 继承 MLCC 材料链
        MATERIAL_REGISTRY["titanium_dioxide"],
        MATERIAL_REGISTRY["barium_carbonate"],
        MATERIAL_REGISTRY["dysprosium_oxide"],
        MATERIAL_REGISTRY["yttrium_oxide"],
        MATERIAL_REGISTRY["nickel_powder"],
        MATERIAL_REGISTRY["cu_terminal"],
    ],
    "aluminum_electrolytic_capacitor": [
        MATERIAL_REGISTRY["al_foil_anode"],
        MATERIAL_REGISTRY["al_foil_cathode"],
        MATERIAL_REGISTRY["electrolyte"],
        MATERIAL_REGISTRY["electrolytic_paper"],
    ],
    "tantalum_capacitor": [
        MATERIAL_REGISTRY["tantalum_powder"],
        MATERIAL_REGISTRY["tantalum_wire"],
        MATERIAL_REGISTRY["ag_paste"],
        MATERIAL_REGISTRY["manganese_dioxide"],
    ],
    "film_capacitor": [
        MATERIAL_REGISTRY["polypropylene"],
        MATERIAL_REGISTRY["polyester_film"],
        MATERIAL_REGISTRY["zinc"],
        MATERIAL_REGISTRY["al_metallization"],
    ],
    "aluminum_heat_sink": [
        MATERIAL_REGISTRY["al_ingot"],
    ],
    "connector": [
        MATERIAL_REGISTRY["cu_cathode"],
        MATERIAL_REGISTRY["tin"],
        MATERIAL_REGISTRY["ni_plating"],
    ],
    "inductor_transformer": [
        MATERIAL_REGISTRY["enameled_cu_wire"],
        MATERIAL_REGISTRY["ferrite_core"],
        MATERIAL_REGISTRY["dysprosium_oxide"],
    ],
    "inductor": [  # 别名
        MATERIAL_REGISTRY["enameled_cu_wire"],
        MATERIAL_REGISTRY["ferrite_core"],
        MATERIAL_REGISTRY["dysprosium_oxide"],
    ],
}


# ── 按数据域的材料分组 ────────────────────────────────────

DOMAIN_MATERIALS: Dict[str, List[str]] = {}
for _key, _entry in MATERIAL_REGISTRY.items():
    DOMAIN_MATERIALS.setdefault(_entry.domain, []).append(_key)


# ── 数据域 → 数据源映射 ───────────────────────────────────

DOMAIN_SOURCES: Dict[str, Dict[str, str]] = {
    "metals": {
        "primary": "metals_api",
        "backup": "changjiang",
    },
    "rare_earth": {
        "primary": "re_association",
        "backup": "asian_metal",
    },
    "chemical": {
        "primary": "chem_100ppi",
        "backup": "sci99",
    },
}


# ── 公开查询函数 ──────────────────────────────────────────

def get_materials_for_category(category: str) -> List[MaterialEntry]:
    """返回品类对应的原材料列表。"""
    return CATEGORY_MATERIAL_MAP.get(category, [])


def get_categories_for_material(material_key: str) -> List[str]:
    """反向查找：该原材料影响哪些品类。"""
    return [
        cat for cat, materials in CATEGORY_MATERIAL_MAP.items()
        if any(m.key == material_key for m in materials)
    ]


def get_material_keys_for_domain(domain: str) -> List[str]:
    """返回指定数据域的全部 material_key。"""
    return DOMAIN_MATERIALS.get(domain, [])


def get_sources_for_domain(domain: str) -> Dict[str, str]:
    """返回指定数据域的主/备数据源标识。"""
    return DOMAIN_SOURCES.get(domain, {"primary": "", "backup": ""})


def get_material_entry(key: str) -> Optional[MaterialEntry]:
    """按 key 获取材料条目。"""
    return MATERIAL_REGISTRY.get(key)


def get_adjusted_cost_ratio(entry: MaterialEntry) -> float:
    """计算调整后的传导系数（含稀土放大器和加工溢价）。"""
    ratio = entry.cost_ratio * entry.price_multiplier
    if entry.is_rare_earth:
        ratio *= RARE_EARTH_AMPLIFIER
    return ratio
