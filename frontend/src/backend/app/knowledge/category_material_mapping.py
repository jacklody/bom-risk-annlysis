"""品类 → 上游原材料映射表服务。

T2-015: 品类-材料映射表
建立BOM物料品类到上游原材料的映射关系，使风险传导链路可以从
"MLCC缺货"追溯到"铜/镍/稀土价格波动"。

覆盖15个BOM品类的上游材料映射:
  被动器件: MLCC、电阻、电感、磁珠
  主动器件: MCU、SoC、电源管理IC、功率器件(MOSFET/IGBT)
  连接器: 板对板、FPC、USB
  PCB/FPC
  结构件: 散热片、外壳(塑料/金属)

Usage:
    service = CategoryMaterialMappingService()
    materials = service.get_materials_for_category("MLCC")
    categories = service.get_categories_for_material("cu_cathode")
    score = service.get_exposure_score("MLCC", {"cu_cathode": PriceChange(pct_change=15.0)})
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from app.knowledge.material_mapping import (
    MATERIAL_REGISTRY,
    RARE_EARTH_AMPLIFIER,
    get_material_entry,
)

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────
# 数据模型
# ────────────────────────────────────────────────────────────

@dataclass
class MaterialMapping:
    """品类 → 上游原材料映射条目。

    Attributes:
        material_key: 内部材料代码(如 cu_cathode)，与 MATERIAL_REGISTRY 一致
        material_name: 中文名(如 "铜")
        weight: 权重(0-1)，表示该材料对该品类成本的重要度
        price_sensitivity: 价格敏感度(0-1)，材料涨价1%对品类成本的影响比例
        lead_time_days: 该材料的前置采购时间(天)
        source: 数据源标识(smm/mysteel/lme/metals_api 等)
        transfer_rate: 转嫁率(0-1)，材料涨价传递到器件价格的比率（如60-80%）
    """
    material_key: str
    material_name: str
    weight: float
    price_sensitivity: float
    lead_time_days: int
    source: str
    transfer_rate: float = 0.7  # 默认转嫁率70%


@dataclass
class PriceChange:
    """材料价格变动数据。

    Attributes:
        pct_change: 价格变动百分比（正数=涨价，负数=降价），如 15.0 表示涨15%
    """
    pct_change: float


# ────────────────────────────────────────────────────────────
# 补充材料定义（不在 MATERIAL_REGISTRY 中的材料）
# ────────────────────────────────────────────────────────────

@dataclass
class _SupplementaryMaterial:
    name_zh: str
    primary_source: str
    is_rare_earth: bool = False

_SUPPLEMENTARY: Dict[str, _SupplementaryMaterial] = {
    "au_bonding_wire": _SupplementaryMaterial("金线(键合丝)", "metals_api"),
    "phosphor_bronze": _SupplementaryMaterial("磷铜(弹片)", "smm"),
    "low_k_dielectric": _SupplementaryMaterial("低k介质材料", "semicon"),
    # ── 新增品类材料 ──
    "al_foil": _SupplementaryMaterial("铝箔(通用)", "smm"),
    "pp_film": _SupplementaryMaterial("聚丙烯薄膜", "mysteel"),
    "pet_film": _SupplementaryMaterial("PET薄膜", "mysteel"),
    "glass_substrate": _SupplementaryMaterial("玻璃基板", "semicon"),
    "indium": _SupplementaryMaterial("铟(ITO靶材)", "smm"),
    "graphite": _SupplementaryMaterial("石墨(负极材料)", "mysteel"),
    "li_carbonate": _SupplementaryMaterial("碳酸锂", "smm"),
    "silicon_steel": _SupplementaryMaterial("硅钢片", "mysteel"),
    "cu_alloy_strip": _SupplementaryMaterial("铜合金带材", "smm"),
    "rare_earth_phosphor": _SupplementaryMaterial("稀土荧光粉", "smm", is_rare_earth=True),
}


def _get_material_name(material_key: str) -> str:
    """获取材料的中文名称，优先从 MATERIAL_REGISTRY 查找。"""
    entry = get_material_entry(material_key)
    if entry:
        return entry.name_zh
    sup = _SUPPLEMENTARY.get(material_key)
    return sup.name_zh if sup else material_key


def _get_material_source(material_key: str) -> str:
    """获取材料的数据源标识。"""
    entry = get_material_entry(material_key)
    if entry:
        return entry.primary_source
    sup = _SUPPLEMENTARY.get(material_key)
    return sup.primary_source if sup else "unknown"


def _is_rare_earth_material(material_key: str) -> bool:
    """判断是否为稀土材料（影响暴露度放大系数）。"""
    entry = get_material_entry(material_key)
    if entry:
        return entry.is_rare_earth
    return False


# ────────────────────────────────────────────────────────────
# 映射数据构建辅助
# ────────────────────────────────────────────────────────────

def _build_mappings(
    entries: list,
) -> List[MaterialMapping]:
    """从 (material_key, weight, price_sensitivity, lead_time_days[, transfer_rate]) 构建映射列表。

    支持4元组（默认转嫁率0.7）和5元组（自定义转嫁率）。
    """
    result = []
    for entry in entries:
        if len(entry) >= 5:
            mk, w, ps, lt, tr = entry[:5]
        else:
            mk, w, ps, lt = entry[:4]
            tr = 0.7  # 默认转嫁率
        result.append(MaterialMapping(
            material_key=mk,
            material_name=_get_material_name(mk),
            weight=w,
            price_sensitivity=ps,
            lead_time_days=lt,
            source=_get_material_source(mk),
            transfer_rate=tr,
        ))
    return result


# ────────────────────────────────────────────────────────────
# 映射数据定义（15品类）
# ────────────────────────────────────────────────────────────

# ── (1) 被动器件: MLCC ──────────────────────────────────────
_MAPPING_MLCC = _build_mappings([
    ("cu_cathode",       0.10, 0.10, 30),  # 铜(外电极)
    ("nickel_powder",    0.20, 0.20, 45),  # 镍(内电极)
    ("barium_carbonate", 0.30, 0.30, 60),  # 碳酸钡→钛酸钡(介质)
    ("prnd_oxide",       0.15, 0.15, 45),  # 稀土(掺杂)
    ("dysprosium_oxide", 0.08, 0.08, 45),  # 氧化镝(掺杂)
    ("yttrium_oxide",    0.07, 0.07, 45),  # 氧化钇(掺杂)
    ("titanium_dioxide", 0.10, 0.10, 30),  # 钛白粉(补充介质)
])

# ── (2) 被动器件: 电阻 ──────────────────────────────────────
_MAPPING_RESISTOR = _build_mappings([
    ("barium_carbonate",  0.25, 0.25, 30),  # 氧化铝基板(碳酸钡为proxy)
    ("manganese_dioxide", 0.15, 0.15, 45),  # 电阻体材料
    ("nickel_powder",     0.20, 0.20, 45),  # 镍铬合金→镍(电阻体)
    ("cu_terminal",       0.10, 0.10, 20),  # 铜端头
    ("ag_paste",          0.08, 0.08, 30),  # 银浆(端电极)
    ("titanium_dioxide",  0.12, 0.12, 30),  # 钛白粉(基板辅料)
    ("tin",               0.10, 0.10, 20),  # 锡(端头镀层)
])

# ── (3) 被动器件: 电感 ──────────────────────────────────────
_MAPPING_INDUCTOR = _build_mappings([
    ("enameled_cu_wire",     0.30, 0.30, 30),  # 漆包铜线(绕组)
    ("ferrite_core",         0.30, 0.30, 45),  # 铁氧体磁芯
    ("prnd_oxide",           0.10, 0.10, 45),   # 稀土(铁氧体掺杂)
    ("engineering_plastics", 0.08, 0.08, 20),   # PA66(骨架)
    ("cu_cathode",           0.12, 0.12, 30),   # 铜(引出端子)
    ("tin",                  0.10, 0.10, 20),   # 锡(端子镀层)
])

# ── (4) 被动器件: 磁珠 ──────────────────────────────────────
_MAPPING_FERRITE_BEAD = _build_mappings([
    ("ferrite_core",         0.35, 0.35, 45),  # 铁氧体(磁芯主体)
    ("enameled_cu_wire",     0.25, 0.25, 30),  # 漆包铜线(穿过)
    ("prnd_oxide",           0.10, 0.10, 45),   # 稀土(铁氧体改性)
    ("ag_paste",             0.10, 0.10, 30),   # 银浆(端电极)
    ("engineering_plastics", 0.10, 0.10, 20),   # 封装材料
    ("tin",                  0.10, 0.10, 20),   # 锡(端头镀层)
])

# ── (5) 主动器件: MCU ───────────────────────────────────────
_MAPPING_MCU = _build_mappings([
    ("cu_cathode",           0.15, 0.15, 30),  # 铜(引线框架)
    ("epoxy_resin",          0.10, 0.10, 30),  # 环氧塑封料
    ("au_bonding_wire",      0.20, 0.20, 60),  # 金(键合丝)
    ("tin",                  0.08, 0.08, 20),  # 锡(引脚镀层)
    ("ag_paste",             0.07, 0.07, 30),  # 银浆(粘片)
    ("engineering_plastics", 0.05, 0.05, 20),  # 托盘/载带
    ("cu_foil",              0.15, 0.15, 30),  # 铜(框架基材)
    ("polyester_film",       0.05, 0.05, 15),  # 载带材料
    ("barium_carbonate",     0.05, 0.05, 30),  # 填料(塑封料)
    ("tantalum_powder",      0.10, 0.10, 45),  # 配套去耦电容(钽)
])

# ── (6) 主动器件: SoC ───────────────────────────────────────
_MAPPING_SOC = _build_mappings([
    ("cu_cathode",           0.12, 0.12, 30),  # 铜(引线框架/BGA基板)
    ("au_bonding_wire",      0.25, 0.25, 60),  # 金(键合丝)
    ("epoxy_resin",          0.10, 0.10, 30),  # 环氧塑封料
    ("tin",                  0.08, 0.08, 20),  # 锡(BGA焊球)
    ("ag_paste",             0.08, 0.08, 30),  # 银浆(粘片)
    ("cu_foil",              0.12, 0.12, 30),  # 铜(基板)
    ("engineering_plastics", 0.05, 0.05, 20),  # 载带
    ("polyester_film",       0.05, 0.05, 15),  # 载带
    ("barium_carbonate",     0.05, 0.05, 30),  # 填料
    ("titanium_dioxide",     0.10, 0.10, 30),  # 低k介质(氧化物)
])

# ── (7) 主动器件: 电源管理IC ─────────────────────────────────
_MAPPING_PMIC = _build_mappings([
    ("cu_cathode",           0.15, 0.15, 30),  # 铜(引线框架)
    ("epoxy_resin",          0.10, 0.10, 30),  # 环氧塑封料
    ("au_bonding_wire",      0.15, 0.15, 60),  # 金(键合丝)
    ("tin",                  0.10, 0.10, 20),  # 锡(引脚)
    ("cu_foil",              0.15, 0.15, 30),  # 铜(散热片/框架)
    ("ag_paste",             0.08, 0.08, 30),  # 银浆
    ("barium_carbonate",     0.07, 0.07, 30),  # 填料
    ("engineering_plastics", 0.05, 0.05, 20),  # 载带
    ("polyester_film",       0.05, 0.05, 15),  # 载带
    ("titanium_dioxide",     0.10, 0.10, 30),  # 氧化物
])

# ── (8) 主动器件: 功率器件(MOSFET/IGBT) ─────────────────────
_MAPPING_POWER_DEVICE = _build_mappings([
    ("cu_cathode",           0.20, 0.20, 30),  # 铜(引线框架/散热底座)
    ("epoxy_resin",          0.10, 0.10, 30),  # 环氧塑封料
    ("au_bonding_wire",      0.10, 0.10, 60),  # 金(键合丝)
    ("tin",                  0.08, 0.08, 20),  # 锡(引脚)
    ("cu_foil",              0.15, 0.15, 30),  # 铜(DBC覆铜)
    ("engineering_plastics", 0.05, 0.05, 20),  # 绝缘件
    ("polyester_film",       0.05, 0.05, 15),  # 绝缘膜
    ("titanium_dioxide",     0.12, 0.12, 30),  # 陶瓷基板(Dielectric)
    ("barium_carbonate",     0.10, 0.10, 30),  # 陶瓷基板(BaTiO₃)
    ("ag_paste",             0.05, 0.05, 30),  # 银浆(烧结)
])

# ── (9) 连接器: 板对板 ──────────────────────────────────────
_MAPPING_BT_CONNECTOR = _build_mappings([
    ("cu_cathode",           0.30, 0.30, 30),  # 铜合金(端子)
    ("ag_ingot",             0.15, 0.15, 45),  # 镀金层(以银为proxy)
    ("engineering_plastics", 0.20, 0.20, 45),  # LCP(外壳)
    ("tin",                  0.10, 0.10, 20),  # 锡(焊接端)
    ("nickel_powder",        0.10, 0.10, 30),  # 镍(底层镀)
    ("phosphor_bronze",      0.15, 0.15, 30),  # 磷铜(弹片)
])

# ── (10) 连接器: FPC ────────────────────────────────────────
_MAPPING_FPC_CONNECTOR = _build_mappings([
    ("cu_cathode",           0.25, 0.25, 30),  # 铜合金(端子)
    ("ag_ingot",             0.10, 0.10, 45),  # 镀层(银/金)
    ("engineering_plastics", 0.25, 0.25, 45),  # LCP/PBT(外壳)
    ("tin",                  0.10, 0.10, 20),  # 锡(焊接端)
    ("nickel_powder",        0.10, 0.10, 30),  # 镍(底层镀)
    ("polyester_film",       0.10, 0.10, 20),  # PET(补强板)
    ("cu_foil",              0.10, 0.10, 30),  # 铜箔(接触片)
])

# ── (11) 连接器: USB ────────────────────────────────────────
_MAPPING_USB_CONNECTOR = _build_mappings([
    ("cu_cathode",           0.30, 0.30, 30),  # 铜合金(端子/壳体)
    ("ag_ingot",             0.10, 0.10, 45),  # 镀层(银/金)
    ("engineering_plastics", 0.20, 0.20, 45),  # PBT/PC(外壳)
    ("tin",                  0.15, 0.15, 20),  # 锡(焊接端)
    ("nickel_powder",        0.10, 0.10, 30),  # 镍(底层镀)
    ("phosphor_bronze",      0.10, 0.10, 30),  # 磷铜(弹片)
    ("zinc",                 0.05, 0.05, 20),  # 锌(屏蔽壳)
])

# ── (12) PCB/FPC ────────────────────────────────────────────
_MAPPING_PCB = _build_mappings([
    ("cu_foil",              0.30, 0.30, 30),  # 覆铜板(铜箔)
    ("cu_cathode",           0.15, 0.15, 30),  # 铜(铜箔原料)
    ("glass_fiber_cloth",    0.15, 0.15, 30),  # 玻纤布
    ("epoxy_resin",          0.15, 0.15, 30),  # 环氧树脂
    ("polyester_film",       0.08, 0.08, 30),  # PI/PET膜(FPC)
    ("tin",                  0.07, 0.07, 20),  # 锡(HASL表面处理)
    ("ag_paste",             0.05, 0.05, 30),  # 银浆(碳浆/银浆)
    ("engineering_plastics", 0.05, 0.05, 20),  # 阻焊油墨(树脂)
])

# ── (13) 结构件: 散热片 ─────────────────────────────────────
_MAPPING_HEATSINK = _build_mappings([
    ("al_ingot",             0.40, 0.40, 20),  # 铝(散热主体)
    ("cu_cathode",           0.25, 0.25, 30),  # 铜(热管/均温板)
    ("al_foil_cathode",      0.15, 0.15, 20),  # 铝(鳍片)
    ("engineering_plastics", 0.05, 0.05, 20),  # 塑料(风扇框)
    ("tin",                  0.05, 0.05, 15),  # 锡(焊接)
    ("ferrite_core",         0.05, 0.05, 30),  # 导热垫片(含铁氧体)
    ("epoxy_resin",          0.05, 0.05, 20),  # 导热胶
])

# ── (14) 结构件: 外壳(塑料) ──────────────────────────────────
_MAPPING_PLASTIC_SHELL = _build_mappings([
    ("engineering_plastics", 0.35, 0.35, 20),  # 工程塑料(ABS/PC/PA66)
    ("polypropylene",        0.15, 0.15, 15),  # PP(填充/铰链)
    ("polyester_film",       0.10, 0.10, 15),  # PET(装饰膜)
    ("epoxy_resin",          0.08, 0.08, 20),  # 环氧(阻燃剂)
    ("tin",                  0.05, 0.05, 15),  # 锡(金属嵌件)
    ("cu_cathode",           0.07, 0.07, 20),  # 铜(导电/EMI)
    ("nickel_powder",        0.05, 0.05, 20),  # 镍(EMI屏蔽涂层)
    ("zinc",                 0.10, 0.10, 20),  # 锌(金属嵌件)
    ("ag_ingot",             0.05, 0.05, 30),  # 银(导电涂层)
])

# ── (15) 结构件: 外壳(金属) ──────────────────────────────────
_MAPPING_METAL_SHELL = _build_mappings([
    ("al_ingot",             0.30, 0.30, 20),  # 铝(CNC/压铸)
    ("cu_cathode",           0.15, 0.15, 30),  # 铜(镶嵌件/导热)
    ("zinc",                 0.20, 0.20, 30),  # 锌(压铸)
    ("nickel_powder",        0.10, 0.10, 30),  # 镍(电镀)
    ("tin",                  0.08, 0.08, 20),  # 锡(表面处理)
    ("ag_ingot",             0.05, 0.05, 30),  # 银(高端导电涂层)
    ("engineering_plastics", 0.07, 0.07, 20),  # 塑料(绝缘件)
    ("epoxy_resin",          0.05, 0.05, 20),  # 环氧(粉末涂料)
])


# ── PRD要求的6个补充品类 ─────────────────────────────────────

# ── (16) 铝电解电容 ──
_MAPPING_AL_ELECTROLYTIC = _build_mappings([
    ("al_foil",          0.30, 0.35, 30, 0.75),  # 铝箔(阳极/阴极)
    ("electrolyte",      0.25, 0.30, 45, 0.65),  # 电解液
    ("al_ingot",         0.15, 0.15, 20, 0.70),  # 铝(外壳/引线)
    ("cu_foil",          0.10, 0.10, 30, 0.60),  # 铜(引线框架)
    ("engineering_plastics", 0.08, 0.08, 20, 0.50),  # 塑料(密封塞)
    ("epoxy_resin",      0.07, 0.07, 20, 0.55),  # 环氧(套管)
    ("tin",              0.05, 0.05, 15, 0.60),  # 锡(端子镀层)
])

# ── (17) 薄膜电容 ──
_MAPPING_FILM_CAP = _build_mappings([
    ("pp_film",          0.25, 0.30, 30, 0.70),  # 聚丙烯薄膜(介质)
    ("pet_film",         0.15, 0.20, 30, 0.65),  # PET薄膜
    ("zinc",             0.15, 0.15, 25, 0.60),  # 锌(蒸镀电极)
    ("cu_cathode",       0.12, 0.12, 30, 0.60),  # 铜(引出端)
    ("tin",              0.08, 0.08, 15, 0.55),  # 锡(焊接端)
    ("epoxy_resin",      0.10, 0.10, 20, 0.50),  # 环氧(包封)
    ("engineering_plastics", 0.10, 0.10, 20, 0.45),  # 塑料(外壳)
])

# ── (18) 线束 ──
_MAPPING_WIRE_HARNESS = _build_mappings([
    ("cu_cathode",       0.35, 0.40, 30, 0.80),  # 铜(导线)
    ("engineering_plastics", 0.20, 0.20, 20, 0.55),  # 塑料(绝缘护套)
    ("tin",              0.12, 0.12, 15, 0.65),  # 锡(端子镀层)
    ("cu_alloy_strip",   0.10, 0.10, 25, 0.60),  # 铜合金(端子)
    ("nickel_powder",    0.05, 0.05, 30, 0.50),  # 镍(端子镀底层)
    ("epoxy_resin",      0.05, 0.05, 20, 0.40),  # 环氧(胶带)
    ("zinc",             0.05, 0.05, 20, 0.45),  # 锌(屏蔽层)
])

# ── (19) 继电器 ──
_MAPPING_RELAY = _build_mappings([
    ("cu_cathode",       0.20, 0.20, 30, 0.70),  # 铜(线圈/触点)
    ("ag_ingot",         0.15, 0.20, 30, 0.80),  # 银(触点材料)
    ("nickel_powder",    0.10, 0.10, 30, 0.55),  # 镍(簧片)
    ("engineering_plastics", 0.20, 0.15, 20, 0.50),  # 塑料(外壳/骨架)
    ("silicon_steel",    0.10, 0.15, 25, 0.60),  # 硅钢(铁芯)
    ("epoxy_resin",      0.08, 0.08, 20, 0.45),  # 环氧(密封)
    ("tin",              0.07, 0.07, 15, 0.60),  # 锡(引脚镀层)
    ("cu_alloy_strip",   0.10, 0.10, 25, 0.55),  # 铜合金(弹簧)
])

# ── (20) 电池 ──
_MAPPING_BATTERY = _build_mappings([
    ("li_carbonate",     0.25, 0.30, 45, 0.80),  # 碳酸锂(正极材料)
    ("nickel_powder",    0.15, 0.20, 30, 0.75),  # 镍(三元正极)
    ("cu_foil",          0.12, 0.12, 30, 0.65),  # 铜箔(负极集流体)
    ("al_foil",          0.10, 0.10, 20, 0.60),  # 铝箔(正极集流体)
    ("graphite",         0.10, 0.15, 30, 0.70),  # 石墨(负极)
    ("electrolyte",      0.12, 0.15, 35, 0.70),  # 电解液
    ("engineering_plastics", 0.08, 0.05, 20, 0.40),  # 塑料(外壳)
    ("tin",              0.05, 0.05, 15, 0.55),  # 锡(极耳焊接)
])

# ── (21) 显示/光电 ──
_MAPPING_DISPLAY_OPTO = _build_mappings([
    ("glass_substrate",  0.20, 0.25, 30, 0.70),  # 玻璃基板
    ("indium",           0.15, 0.20, 45, 0.85),  # 铟(ITO透明电极)
    ("rare_earth_phosphor", 0.10, 0.15, 30, 0.75),  # 稀土荧光粉
    ("cu_cathode",       0.10, 0.10, 30, 0.60),  # 铜(引线/布线)
    ("au_bonding_wire",  0.08, 0.10, 45, 0.50),  # 金线(键合)
    ("epoxy_resin",      0.12, 0.10, 20, 0.55),  # 环氧(封装/透镜)
    ("engineering_plastics", 0.10, 0.08, 20, 0.45),  # 塑料(框架)
    ("tin",              0.05, 0.05, 15, 0.60),  # 锡(引脚)
])

# ────────────────────────────────────────────────────────────
# 品类 → 映射数据 总表
# ────────────────────────────────────────────────────────────

CATEGORY_MAPPING_DATA: Dict[str, List[MaterialMapping]] = {
    "MLCC":           _MAPPING_MLCC,
    "电阻":           _MAPPING_RESISTOR,
    "电感":           _MAPPING_INDUCTOR,
    "磁珠":           _MAPPING_FERRITE_BEAD,
    "MCU":            _MAPPING_MCU,
    "SoC":            _MAPPING_SOC,
    "电源管理IC":     _MAPPING_PMIC,
    "功率器件":       _MAPPING_POWER_DEVICE,
    "板对板连接器":   _MAPPING_BT_CONNECTOR,
    "FPC连接器":      _MAPPING_FPC_CONNECTOR,
    "USB连接器":      _MAPPING_USB_CONNECTOR,
    "PCB/FPC":        _MAPPING_PCB,
    "散热片":         _MAPPING_HEATSINK,
    "外壳(塑料)":     _MAPPING_PLASTIC_SHELL,
    "外壳(金属)":     _MAPPING_METAL_SHELL,
    # ── PRD要求补充品类 ──
    "铝电解电容":     _MAPPING_AL_ELECTROLYTIC,
    "薄膜电容":       _MAPPING_FILM_CAP,
    "线束":           _MAPPING_WIRE_HARNESS,
    "继电器":         _MAPPING_RELAY,
    "电池":           _MAPPING_BATTERY,
    "显示/光电":      _MAPPING_DISPLAY_OPTO,
    # ── PRD合并品类（连接器/电感变压器/结构件 作为聚合入口）──
    "连接器":         _MAPPING_BT_CONNECTOR,   # 聚合入口，实际含3子品类
    "电感/变压器":    _MAPPING_INDUCTOR,
    "结构件":         _MAPPING_METAL_SHELL,
}

# ── 反向索引缓存 ──
_REVERSE_INDEX: Optional[Dict[str, List[str]]] = None

# ── 品类别名（兼容 industry_chain.py 和 material_mapping.py 命名）──
CATEGORY_ALIASES: Dict[str, str] = {
    "mlcc": "MLCC",
    "resistor": "电阻",
    "inductor": "电感",
    "ferrite_bead": "磁珠",
    "mcu": "MCU",
    "soc": "SoC",
    "pmic": "电源管理IC",
    "power_device": "功率器件",
    "mosfet": "功率器件",
    "igbt": "功率器件",
    "bt_connector": "板对板连接器",
    "board_to_board": "板对板连接器",
    "fpc_connector": "FPC连接器",
    "usb_connector": "USB连接器",
    "connector": "板对板连接器",
    "pcb": "PCB/FPC",
    "fpc": "PCB/FPC",
    "heatsink": "散热片",
    "plastic_shell": "外壳(塑料)",
    "metal_shell": "外壳(金属)",
    # industry_chain.py 品类名兼容
    "铝电解电容": "铝电解电容",
    "薄膜电容": "薄膜电容",
    "connector": "连接器",
    "连接器": "连接器",
    "线束": "线束",
    "继电器": "继电器",
    "电感/变压器": "电感/变压器",
    "MOSFET/IGBT": "功率器件",
    "散热器": "散热片",
    "结构件": "结构件",
    "电池": "电池",
    "显示/光电": "显示/光电",
    # material_mapping.py 品类名兼容
    "relay": "继电器",
    "pcb_lower": "PCB/FPC",
    "high_cap_mlcc": "MLCC",
    "aluminum_electrolytic_capacitor": "铝电解电容",
    "tantalum_capacitor": "钽电容",
    "film_capacitor": "薄膜电容",
    "aluminum_heat_sink": "散热片",
    "inductor_transformer": "电感",
}


def _normalize_category(category: str) -> str:
    """标准化品类名称。"""
    if category in CATEGORY_MAPPING_DATA:
        return category
    normalized = CATEGORY_ALIASES.get(category, category)
    if normalized in CATEGORY_MAPPING_DATA:
        return normalized
    lower = category.lower()
    for alias_key, alias_val in CATEGORY_ALIASES.items():
        if alias_key.lower() == lower:
            return alias_val
    for key in CATEGORY_MAPPING_DATA:
        if category in key or key in category:
            return key
    return category


def _build_reverse_index() -> Dict[str, List[str]]:
    """构建 material_key → 品类列表 的反向索引。"""
    index: Dict[str, List[str]] = {}
    for category, mappings in CATEGORY_MAPPING_DATA.items():
        for m in mappings:
            index.setdefault(m.material_key, []).append(category)
    return index


def _get_reverse_index() -> Dict[str, List[str]]:
    """获取反向索引（带缓存）。"""
    global _REVERSE_INDEX
    if _REVERSE_INDEX is None:
        _REVERSE_INDEX = _build_reverse_index()
    return _REVERSE_INDEX


# ────────────────────────────────────────────────────────────
# 服务类
# ────────────────────────────────────────────────────────────

class CategoryMaterialMappingService:
    """品类 → 上游原材料映射表服务。

    映射关系示例:
    - MLCC → 铜(导体)、镍(电极)、钛酸钡(介质)、稀土(掺杂)
    - PCB → 覆铜板(CCL)、铜箔、玻纤布、环氧树脂
    - 被动器件(电阻) → 氧化铝基板、钌酸钌(电阻体)
    - 连接器 → 铜合金(端子)、磷铜(弹片)、LCP(外壳)

    Usage:
        service = CategoryMaterialMappingService()
        materials = service.get_materials_for_category("MLCC")
        categories = service.get_categories_for_material("cu_cathode")
        score = service.get_exposure_score("MLCC", price_changes)
    """

    def get_materials_for_category(self, category: str) -> List[MaterialMapping]:
        """获取某品类对应的上游原材料列表。

        Args:
            category: 品类名称(如 "MLCC"、"PCB/FPC"、"电阻")或别名(如 "mcu")

        Returns:
            该品类的上游原材料映射列表，按权重降序排列。
            若品类不存在，返回空列表。
        """
        normalized = _normalize_category(category)
        mappings = CATEGORY_MAPPING_DATA.get(normalized, [])
        return sorted(mappings, key=lambda m: m.weight, reverse=True)

    def get_categories_for_material(self, material_key: str) -> List[str]:
        """反向查询：某原材料影响哪些品类。

        Args:
            material_key: 材料内部代码(如 "cu_cathode")

        Returns:
            受影响的品类名称列表，按该材料在品类中的权重降序排列。
        """
        reverse_index = _get_reverse_index()
        categories = reverse_index.get(material_key, [])
        if not categories:
            return []

        def _max_weight(cat: str) -> float:
            for m in CATEGORY_MAPPING_DATA.get(cat, []):
                if m.material_key == material_key:
                    return m.weight
            return 0.0

        return sorted(categories, key=_max_weight, reverse=True)

    def get_exposure_score(
        self,
        category: str,
        material_prices: Dict[str, PriceChange],
    ) -> float:
        """根据原材料价格变动计算品类暴露度分数。

        计算公式:
            score = Σ (weight_i × sensitivity_i × pct_change_i × amplifier_i)
        其中:
            - amplifier = RARE_EARTH_AMPLIFIER (1.6) 对稀土材料
            - 分数上限: 100

        Args:
            category: 品类名称
            material_prices: 材料价格变动字典
                key: material_key (如 "cu_cathode")
                value: PriceChange 对象(包含 pct_change 百分比值)

        Returns:
            暴露度分数 (0-100)，越高表示受价格波动影响越大。
            品类不存在时返回 0.0。
        """
        normalized = _normalize_category(category)
        mappings = CATEGORY_MAPPING_DATA.get(normalized, [])
        if not mappings:
            return 0.0

        score = 0.0
        for mapping in mappings:
            if mapping.material_key not in material_prices:
                continue
            price_change = material_prices[mapping.material_key]
            pct = abs(price_change.pct_change)
            amplifier = RARE_EARTH_AMPLIFIER if _is_rare_earth_material(mapping.material_key) else 1.0
            score += mapping.weight * mapping.price_sensitivity * pct * amplifier

        return round(min(score, 100.0), 4)

    def get_all_categories(self) -> List[str]:
        """获取所有已映射的品类名称列表。"""
        return list(CATEGORY_MAPPING_DATA.keys())

    def get_all_material_keys(self) -> List[str]:
        """获取所有涉及的材料代码列表(去重)。"""
        keys: Set[str] = set()
        for mappings in CATEGORY_MAPPING_DATA.values():
            for m in mappings:
                keys.add(m.material_key)
        return sorted(keys)

    def get_mapping_stats(self) -> Dict[str, int]:
        """获取映射统计信息。"""
        total_mappings = sum(len(v) for v in CATEGORY_MAPPING_DATA.values())
        return {
            "total_categories": len(CATEGORY_MAPPING_DATA),
            "total_mappings": total_mappings,
            "unique_materials": len(self.get_all_material_keys()),
        }

    def validate_data_integrity(self) -> Dict:
        """验证映射数据完整性。

        Returns:
            {
                "valid": bool,
                "categories": int,
                "issues": list,
            }
        """
        issues: List[str] = []

        for category, mappings in CATEGORY_MAPPING_DATA.items():
            if not mappings:
                issues.append(f"品类 '{category}' 无映射数据")
                continue

            total_weight = sum(m.weight for m in mappings)
            if total_weight < 0.5:
                issues.append(
                    f"品类 '{category}' 权重总和偏低: {total_weight:.2f}"
                )
            if total_weight > 1.5:
                issues.append(
                    f"品类 '{category}' 权重总和偏高: {total_weight:.2f}"
                )

            for m in mappings:
                if not (0 <= m.weight <= 1):
                    issues.append(
                        f"品类 '{category}' 材料 '{m.material_key}' weight 越界: {m.weight}"
                    )
                if not (0 <= m.price_sensitivity <= 1):
                    issues.append(
                        f"品类 '{category}' 材料 '{m.material_key}' "
                        f"price_sensitivity 越界: {m.price_sensitivity}"
                    )
                if m.lead_time_days < 0:
                    issues.append(
                        f"品类 '{category}' 材料 '{m.material_key}' "
                        f"lead_time_days 为负: {m.lead_time_days}"
                    )

        if len(CATEGORY_MAPPING_DATA) < 15:
            issues.append(
                f"品类数量不足: {len(CATEGORY_MAPPING_DATA)} < 15"
            )

        return {
            "valid": len(issues) == 0,
            "categories": len(CATEGORY_MAPPING_DATA),
            "issues": issues,
        }


# ────────────────────────────────────────────────────────────
# 模块级便捷函数
# ────────────────────────────────────────────────────────────

_default_service: Optional[CategoryMaterialMappingService] = None


def get_category_material_mapping_service() -> CategoryMaterialMappingService:
    """获取品类-材料映射服务单例。"""
    global _default_service
    if _default_service is None:
        _default_service = CategoryMaterialMappingService()
    return _default_service
