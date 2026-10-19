"""产业链知识图谱数据定义。

T2-005: 产业链知识图谱数据模型
本模块替代 risk_chain_library.py，用 SQLite 关系表 + Python 实现图遍历。
包含 14 个 BOM 品类的完整上游材料链路、转嫁率和滞后时间。

结构说明
--------
图谱数据由三张表组成:
- industry_node: 节点 (材料/半成品/品类/工厂/地区)
- industry_edge: 边 (供应传导/共享材料/替代)
- category_material_mapping: 品类-材料直接映射

本模块提供静态数据定义 ``GRAPH_DATA`` 供初始化脚本写入数据库。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ────────────────────────────────────────────────────────────
# 1. 节点定义 (node_id, node_type, name, category, geo_location, metadata_json)
# ────────────────────────────────────────────────────────────

@dataclass
class NodeDef:
    """节点定义。"""
    node_id: str            # 逻辑 ID, 如 "mat_copper"
    node_type: str          # material / sub_assembly / component_category / factory / region
    name: str               # 显示名称
    category: str = ""      # 所属 BOM 大类
    geo_location: str = ""  # 地理位置/产业集群
    metadata: str = ""      # JSON 扩展


# ─── 基础材料层 (material) ──────────────────────────────────

_BASE_MATERIALS: List[NodeDef] = [
    # 金属
    NodeDef("mat_copper",        "material", "铜",       "有色金属", "LME/SHFE/长江有色"),
    NodeDef("mat_aluminum",      "material", "铝",       "有色金属", "LME/SHFE"),
    NodeDef("mat_nickel",        "material", "镍",       "有色金属", "LME"),
    NodeDef("mat_tin",           "material", "锡",       "有色金属", "LME"),
    NodeDef("mat_silver",        "material", "银",       "贵金属",   "LME/上海黄金交易所"),
    NodeDef("mat_gold",          "material", "金",       "贵金属",   "LME/上海黄金交易所"),
    NodeDef("mat_cobalt",        "material", "钴",       "小金属",   "LME/USGS"),
    NodeDef("mat_manganese",     "material", "锰",       "小金属",   "Mysteel/USGS"),
    NodeDef("mat_zinc",          "material", "锌",       "有色金属", "LME/SHFE"),
    NodeDef("mat_lithium_carb",  "material", "碳酸锂",   "锂电材料", "SMM/USGS"),
    # 稀土
    NodeDef("mat_ba_titanate",   "material", "钛酸钡",   "稀土功能材料", "SMM稀土"),
    NodeDef("mat_nickel_powder", "material", "镍粉",     "有色金属", "SMM镍"),
    NodeDef("mat_ceramic_powder","material", "陶瓷粉体", "电子陶瓷", "SMM稀土"),
    NodeDef("mat_rare_earth_fluor","material","稀土荧光粉","稀土功能材料","SMM稀土/USGS"),
    # 非金属 / 化工
    NodeDef("mat_petroleum",     "material", "石油",     "化工",     "化工行业"),
    NodeDef("mat_epoxy_resin",   "material", "环氧树脂", "化工",     "SMM树脂行业"),
    NodeDef("mat_glass_fiber",   "material", "玻纤",     "非金属矿", "中国巨石/泰山玻纤"),
    NodeDef("mat_pp",            "material", "聚丙烯PP", "化工",     "化工行业/SMM塑料"),
    NodeDef("mat_pet_film",      "material", "聚酯PET",  "化工",     "化工行业"),
    NodeDef("mat_pi_film",       "material", "聚酰亚胺PI","化工",    "化工行业"),
    NodeDef("mat_pvc",           "material", "聚氯乙烯PVC","化工",    "化工行业"),
    NodeDef("mat_xlpe",          "material", "交联聚乙烯XLPE","化工", "化工行业"),
    NodeDef("mat_tpe",           "material", "热塑性弹性体TPE","化工", "化工行业"),
    NodeDef("mat_lcp",           "material", "液晶聚合物LCP","化工", "化工行业"),
    NodeDef("mat_pbt",           "material", "聚对苯二甲酸丁酯PBT","化工","化工行业"),
    NodeDef("mat_pa66",          "material", "尼龙PA66", "化工",     "化工行业"),
    NodeDef("mat_abs",           "material", "ABS塑料",  "化工",     "化工行业/SMM塑料"),
    NodeDef("mat_pc",            "material", "聚碳酸酯PC","化工",     "化工行业"),
    NodeDef("mat_graphite",      "material", "石墨/天然石墨","非金属矿","USGS/SMM锂电"),
    NodeDef("mat_silicon_steel", "material", "硅钢片",   "钢铁",     "Mysteel/宝钢"),
    NodeDef("mat_cold_rolled",   "material", "冷轧钢板", "钢铁",     "Mysteel/宝钢"),
    NodeDef("mat_stainless",     "material", "不锈钢",   "钢铁",     "Mysteel/太钢"),
    NodeDef("mat_al_alloy_plate","material", "铝板/铝合金","有色金属", "SMM铝"),
    NodeDef("mat_zinc_alloy",    "material", "锌合金",   "有色金属", "SMM/压铸行业"),
    NodeDef("mat_ferrite",       "material", "铁氧体",   "电子陶瓷", "SMM/陶瓷行业"),
    NodeDef("mat_silicon_wafer", "material", "硅片/晶圆", "半导体材料","SEMI"),
    NodeDef("mat_dielectric_ceramic","material","介电陶瓷","电子陶瓷","SMM稀土"),
    NodeDef("mat_ruthenium",     "material", "钌",       "贵金属",   "SMM贵金属"),
    NodeDef("mat_nickel_chromium","material","镍铬合金",  "有色金属", "SMM镍"),
    NodeDef("mat_iron_nickel",   "material", "铁镍合金", "有色金属", "SMM镍/钢材"),
    NodeDef("mat_silicone_thermal","material","导热硅胶", "化工",     "化工行业"),
    NodeDef("mat_copper_alloy",  "material", "铜合金",   "有色金属", "SMM铜"),
    NodeDef("mat_rubber",        "material", "橡胶",     "化工",     "化工行业"),
    NodeDef("mat_paper",         "material", "电子纸",   "非金属",   "造纸行业"),
    NodeDef("mat_silver_paste",  "material", "银浆",     "贵金属",   "SMM银/杜邦"),
    NodeDef("mat_copper_end_cap","material", "铜端头",   "有色金属", "SMM铜"),
    NodeDef("mat_ceramic_substrate","material","陶瓷基板","电子陶瓷", "SMM/半导体材料"),
    NodeDef("mat_dielectric_film","material","介电薄膜",  "化工",     "化工行业"),
    NodeDef("mat_ito",           "material", "ITO氧化铟锡","稀有金属","SMM稀有金属"),
    NodeDef("mat_glass_substrate","material","玻璃基板",  "非金属矿", "面板行业"),
    NodeDef("mat_polarizer",     "material", "偏光片",   "光电材料", "面板行业"),
    NodeDef("mat_led_chip",      "material", "LED芯片",  "半导体材料","SEMI"),
    NodeDef("mat_epoxy_molding", "material", "环氧塑封料","化工",     "化工行业/封装材料"),
    NodeDef("mat_copper_frame",  "material", "铜框架/引线框架","有色金属","SMM铜/封装材料"),
    NodeDef("mat_electrolyte",   "material", "电解液",   "化工",     "化工行业/SMM化工"),
]

# ─── 中间制品层 (sub_assembly) ──────────────────────────────

_SUB_ASSEMBLIES: List[NodeDef] = [
    # PCB/FPC 链
    NodeDef("sub_copper_foil",   "sub_assembly", "铜箔",     "PCB/FPC", "SMM铜/诺德/铜陵有色"),
    NodeDef("sub_ccl",           "sub_assembly", "覆铜板CCL","PCB/FPC", "生益科技/建滔"),
    NodeDef("sub_glass_cloth",   "sub_assembly", "玻纤布",   "PCB/FPC", "中国巨石/宏和电子"),
    NodeDef("sub_epoxy_ccl",     "sub_assembly", "环氧树脂/玻纤布","PCB/FPC","SMM树脂行业"),
    NodeDef("sub_pi_film",       "sub_assembly", "PI膜",     "PCB/FPC", "鼎龙股份/SKPI"),
    NodeDef("sub_ink",           "sub_assembly", "油墨",     "PCB/FPC", "太阳油墨/容大感光"),
    # MLCC 链
    NodeDef("sub_batio3",        "sub_assembly", "钛酸钡陶瓷粉","MLCC","SMM稀土/国瓷材料"),
    NodeDef("sub_nickel_electrode","sub_assembly","镍内电极", "MLCC",   "SMM镍"),
    NodeDef("sub_copper_terminal","sub_assembly","铜端头镀层","MLCC",   "SMM铜"),
    NodeDef("sub_silver_paste_m","sub_assembly", "银浆(MLCC)","MLCC",   "SMM银/杜邦"),
    NodeDef("sub_ceramic_body",  "sub_assembly", "陶瓷粉体(MLCC)","MLCC","SMM稀土"),
    # 铝电解电容
    NodeDef("sub_al_foil",       "sub_assembly", "铝箔(腐蚀箔/化成箔)","铝电解电容","SMM铝/东阳光"),
    NodeDef("sub_electrolyte",   "sub_assembly", "电解液(铝电容)","铝电解电容","化工行业"),
    NodeDef("sub_electro_paper", "sub_assembly", "电解纸",   "铝电解电容","造纸行业"),
    NodeDef("sub_rubber_plug",   "sub_assembly", "橡胶塞",   "铝电解电容","化工行业"),
    # 薄膜电容
    NodeDef("sub_pp_film",       "sub_assembly", "PP薄膜(金属化)","薄膜电容","化工/SMM塑料"),
    NodeDef("sub_pet_film",      "sub_assembly", "PET薄膜",  "薄膜电容","化工"),
    NodeDef("sub_al_zn_spray",   "sub_assembly", "铝锌喷金层","薄膜电容","SMM铝锌"),
    # 电阻
    NodeDef("sub_ceramic_sub",   "sub_assembly", "陶瓷基板(电阻)","电阻","SMM/陶瓷行业"),
    NodeDef("sub_nichrome_film", "sub_assembly", "镍铬膜",   "电阻",   "SMM镍"),
    NodeDef("sub_ruthenium_paste","sub_assembly","钌浆(厚膜电阻)","电阻","SMM贵金属"),
    NodeDef("sub_cu_terminal_r", "sub_assembly", "铜端头(电阻)","电阻", "SMM铜"),
    # 连接器
    NodeDef("sub_cu_alloy",      "sub_assembly", "铜合金(端子)","连接器","SMM铜"),
    NodeDef("sub_au_sn_ni_plate","sub_assembly", "镀金锡镍层","连接器","SMM铜锡镍金"),
    NodeDef("sub_lcp_housing",   "sub_assembly", "LCP外壳",  "连接器", "化工行业"),
    NodeDef("sub_pbt_housing",   "sub_assembly", "PBT外壳",  "连接器", "化工行业"),
    NodeDef("sub_pa66_housing",  "sub_assembly", "PA66外壳", "连接器", "化工行业"),
    # 线束
    NodeDef("sub_cu_wire",       "sub_assembly", "铜线(导体)","线束",  "SMM铜"),
    NodeDef("sub_pvc_jacket",    "sub_assembly", "PVC/XLPE/TPE护套","线束","化工"),
    NodeDef("sub_terminal",      "sub_assembly", "端子(压接)","线束",  "SMM铜"),
    # 继电器
    NodeDef("sub_ag_contact",    "sub_assembly", "银触点",   "继电器", "SMM银"),
    NodeDef("sub_cu_coil",       "sub_assembly", "铜线圈",   "继电器", "SMM铜"),
    NodeDef("sub_fe_ni_core",    "sub_assembly", "铁镍合金(磁芯)","继电器","SMM镍/钢材"),
    NodeDef("sub_plastic_shell_r","sub_assembly","塑胶壳(继电器)","继电器","化工"),
    # 电感/变压器
    NodeDef("sub_cu_wire_i",     "sub_assembly", "铜线(绕组)","电感/变压器","SMM铜"),
    NodeDef("sub_ferrite_core",  "sub_assembly", "铁氧体磁芯","电感/变压器","SMM/陶瓷行业"),
    NodeDef("sub_si_steel",      "sub_assembly", "硅钢片(变压器铁芯)","电感/变压器","Mysteel/宝钢"),
    NodeDef("sub_bone_i",        "sub_assembly", "骨架(电感)","电感/变压器","化工/塑料"),
    # MOSFET/IGBT
    NodeDef("sub_wafer",         "sub_assembly", "晶圆",     "MOSFET/IGBT","SEMI"),
    NodeDef("sub_cu_leadframe",  "sub_assembly", "铜框架/引线框架","MOSFET/IGBT","SMM铜/封装材料"),
    NodeDef("sub_epoxy_mold_m",  "sub_assembly", "环氧塑封料","MOSFET/IGBT","化工/封装材料"),
    NodeDef("sub_ceramic_dbc",   "sub_assembly", "陶瓷DBC基板","MOSFET/IGBT","半导体材料"),
    # 散热器
    NodeDef("sub_al_extrusion",  "sub_assembly", "铝型材",   "散热器", "SMM铝/兴发铝业"),
    NodeDef("sub_al_diecast",    "sub_assembly", "压铸铝",   "散热器", "SMM铝/压铸行业"),
    NodeDef("sub_cu_heatpipe",   "sub_assembly", "铜热管",   "散热器", "SMM铜"),
    NodeDef("sub_silicone_pad",  "sub_assembly", "导热硅胶垫","散热器", "化工行业"),
    # 结构件
    NodeDef("sub_cold_rolled_s", "sub_assembly", "冷轧板(结构)","结构件","Mysteel/宝钢"),
    NodeDef("sub_stainless_s",   "sub_assembly", "不锈钢板",  "结构件", "Mysteel/太钢"),
    NodeDef("sub_al_plate_s",    "sub_assembly", "铝板(结构)","结构件","SMM铝"),
    NodeDef("sub_zinc_alloy_s",  "sub_assembly", "锌合金(压铸件)","结构件","SMM/压铸行业"),
    NodeDef("sub_abs_pc_shell",  "sub_assembly", "ABS/PC外壳","结构件","化工/SMM塑料"),
    # 电池
    NodeDef("sub_li_carbonate",  "sub_assembly", "碳酸锂(电池)","电池", "SMM锂电/USGS"),
    NodeDef("sub_cobalt_salt",   "sub_assembly", "钴盐(电池)","电池",  "SMM锂电"),
    NodeDef("sub_nickel_salt",   "sub_assembly", "镍盐(电池)","电池",  "SMM锂电"),
    NodeDef("sub_manganese_salt","sub_assembly", "锰盐(电池)","电池",  "SMM锂电"),
    NodeDef("sub_graphite_anode","sub_assembly", "石墨负极",  "电池",   "USGS/SMM锂电"),
    NodeDef("sub_cu_foil_bat",   "sub_assembly", "铜箔(负极集流体)","电池","SMM铜"),
    NodeDef("sub_al_foil_bat",   "sub_assembly", "铝箔(正极集流体)","电池","SMM铝"),
    # 显示/光电
    NodeDef("sub_glass_panel",   "sub_assembly", "玻璃基板(面板)","显示/光电","面板行业/康宁"),
    NodeDef("sub_polarizer_f",   "sub_assembly", "偏光片(显示)","显示/光电","面板行业/杉杉"),
    NodeDef("sub_led_die",       "sub_assembly", "LED芯片",  "显示/光电","SEMI/三安光电"),
    NodeDef("sub_re_fluor",      "sub_assembly", "稀土荧光粉(显示)","显示/光电","SMM稀土/USGS"),
]

# ─── BOM 品类层 (component_category) ────────────────────────

_BOM_CATEGORIES: List[NodeDef] = [
    NodeDef("cat_pcb",          "component_category", "PCB/FPC",        "PCB/FPC"),
    NodeDef("cat_mlcc",         "component_category", "MLCC",            "被动件"),
    NodeDef("cat_al_cap",       "component_category", "铝电解电容",       "被动件"),
    NodeDef("cat_film_cap",     "component_category", "薄膜电容",         "被动件"),
    NodeDef("cat_resistor",     "component_category", "电阻",             "被动件"),
    NodeDef("cat_connector",    "component_category", "连接器",           "连接器线缆"),
    NodeDef("cat_wire_harness", "component_category", "线束",             "连接器线缆"),
    NodeDef("cat_relay",        "component_category", "继电器",           "连接器线缆"),
    NodeDef("cat_inductor",     "component_category", "电感/变压器",      "磁性件"),
    NodeDef("cat_mosfet_igbt",  "component_category", "MOSFET/IGBT",     "半导体"),
    NodeDef("cat_heatsink",     "component_category", "散热器",           "结构散热"),
    NodeDef("cat_structural",   "component_category", "结构件",           "结构散热"),
    NodeDef("cat_battery",      "component_category", "电池",             "电池电源"),
    NodeDef("cat_display",      "component_category", "显示/光电",        "显示光电"),
]

# ─── 地区/工厂 (region / factory) ──────────────────────────

_REGIONS: List[NodeDef] = [
    NodeDef("reg_china",       "region", "中国大陆(制造)", "全品类"),
    NodeDef("reg_japan",       "region", "日本(材料/被动件)", "MLCC/半导体"),
    NodeDef("reg_korea",       "region", "韩国(半导体/面板)", "MLCC/面板"),
    NodeDef("reg_taiwan",      "region", "中国台湾(代工/被动件)", "半导体"),
    NodeDef("reg_sea",         "region", "东南亚(组装)", "全品类"),
    NodeDef("reg_europe",      "region", "欧洲(汽车/工控)", "功率器件"),
    NodeDef("reg_us",          "region", "北美(半导体/军工)", "IC/半导体"),
]

# ─── 汇总所有节点 ──────────────────────────────────────────

ALL_NODES: List[NodeDef] = _BASE_MATERIALS + _SUB_ASSEMBLIES + _BOM_CATEGORIES + _REGIONS


# ────────────────────────────────────────────────────────────
# 2. 边定义 (from_id, to_id, edge_type, transfer_rate, lag_months, confidence, description)
#    约定: from = 上游 → to = 下游 (supply_chain 方向)
# ────────────────────────────────────────────────────────────

@dataclass
class EdgeDef:
    from_id: str
    to_id: str
    edge_type: str = "supply_chain"
    transfer_rate: Optional[float] = None
    lag_months: Optional[float] = None
    confidence: float = 0.8
    description: str = ""


# ────────────────────────────────────────────────────────────
# 3. 完整品类-边数据（14 品类 × 至少 2 层上游追溯）
# ────────────────────────────────────────────────────────────

# (1) PCB/FPC
_EDGES_PCB: List[EdgeDef] = [
    # 第 1 层: 品类 -> 中间制品
    EdgeDef("sub_copper_foil",  "cat_pcb", "supply_chain", 0.20, 2.0, 0.90, "铜箔占PCB成本~20-30%"),
    EdgeDef("sub_ccl",          "cat_pcb", "supply_chain", 0.30, 1.5, 0.90, "CCL(覆铜板)是PCB核心基材"),
    EdgeDef("sub_glass_cloth",  "cat_pcb", "supply_chain", 0.10, 2.0, 0.85, "玻纤布是CCL增强材料"),
    EdgeDef("sub_epoxy_ccl",    "cat_pcb", "supply_chain", 0.10, 2.0, 0.80, "环氧树脂用于CCL基材"),
    EdgeDef("sub_pi_film",      "cat_pcb", "supply_chain", 0.08, 2.5, 0.80, "PI膜用于FPC柔性基材"),
    EdgeDef("sub_ink",          "cat_pcb", "supply_chain", 0.05, 1.0, 0.75, "油墨用于PCB阻焊/字符"),
    # 第 2 层: 中间制品 -> 基础材料
    EdgeDef("mat_copper",       "sub_copper_foil", "supply_chain", 0.80, 1.0, 0.95, "铜是铜箔的核心原料"),
    EdgeDef("mat_copper",       "sub_ccl",       "supply_chain", 0.35, 1.5, 0.90, "铜箔占CCL成本~35-50%"),
    EdgeDef("mat_epoxy_resin",  "sub_ccl",       "supply_chain", 0.25, 1.5, 0.85, "环氧树脂占CCL成本~25-30%"),
    EdgeDef("mat_glass_fiber",  "sub_glass_cloth","supply_chain", 0.85, 1.0, 0.90, "玻纤是玻纤布原料"),
    EdgeDef("mat_epoxy_resin",  "sub_epoxy_ccl", "supply_chain", 0.70, 1.0, 0.85, "环氧树脂"),
    EdgeDef("mat_glass_fiber",  "sub_epoxy_ccl", "supply_chain", 0.30, 1.0, 0.85, "玻纤布增强"),
    EdgeDef("mat_petroleum",    "mat_epoxy_resin", "supply_chain", 0.60, 1.0, 0.80, "石油→双酚A→环氧树脂"),
    EdgeDef("mat_petroleum",    "mat_pi_film",   "supply_chain", 0.50, 1.5, 0.75, "石油→PI单体"),
    EdgeDef("mat_petroleum",    "sub_pi_film",   "supply_chain", 0.50, 1.5, 0.75, "石油化学→PI膜"),
]

# (2) MLCC
_EDGES_MLCC: List[EdgeDef] = [
    EdgeDef("sub_batio3",        "cat_mlcc", "supply_chain", 0.25, 3.0, 0.90, "钛酸钡是MLCC陶瓷介质"),
    EdgeDef("sub_nickel_electrode","cat_mlcc", "supply_chain", 0.15, 2.5, 0.85, "镍内电极(贱金属电极)"),
    EdgeDef("sub_copper_terminal", "cat_mlcc", "supply_chain", 0.10, 2.0, 0.85, "铜端头外电极"),
    EdgeDef("sub_silver_paste_m", "cat_mlcc", "supply_chain", 0.08, 2.5, 0.80, "银浆(部分规格)"),
    EdgeDef("sub_ceramic_body",  "cat_mlcc", "supply_chain", 0.10, 3.0, 0.75, "陶瓷粉体"),
    # 第 2 层
    EdgeDef("mat_ba_titanate",   "sub_batio3", "supply_chain", 0.80, 1.0, 0.90, "钛酸钡→陶瓷粉"),
    EdgeDef("mat_nickel_powder", "sub_nickel_electrode","supply_chain", 0.85, 1.0, 0.90, "镍粉→镍内电极"),
    EdgeDef("mat_nickel",        "mat_nickel_powder","supply_chain", 0.70, 1.0, 0.90, "镍→镍粉"),
    EdgeDef("mat_copper",        "sub_copper_terminal","supply_chain", 0.80, 0.5, 0.90, "铜→铜端头"),
    EdgeDef("mat_silver",        "sub_silver_paste_m","supply_chain", 0.75, 1.0, 0.85, "银→银浆"),
    EdgeDef("mat_ceramic_powder","sub_ceramic_body","supply_chain", 0.80, 1.5, 0.80, "陶瓷粉体"),
    EdgeDef("mat_ba_titanate",   "sub_ceramic_body","supply_chain", 0.40, 1.5, 0.80, "钛酸钡→陶瓷粉体"),
]

# (3) 铝电解电容
_EDGES_AL_CAP: List[EdgeDef] = [
    EdgeDef("sub_al_foil",       "cat_al_cap", "supply_chain", 0.35, 1.5, 0.90, "铝箔(阳极/阴极)是核心材料"),
    EdgeDef("sub_electrolyte",   "cat_al_cap", "supply_chain", 0.15, 1.5, 0.85, "电解液"),
    EdgeDef("sub_electro_paper", "cat_al_cap", "supply_chain", 0.08, 1.0, 0.80, "电解纸(隔离)"),
    EdgeDef("sub_rubber_plug",   "cat_al_cap", "supply_chain", 0.05, 1.0, 0.75, "橡胶塞(密封)"),
    # 第 2 层
    EdgeDef("mat_aluminum",      "sub_al_foil", "supply_chain", 0.70, 1.0, 0.90, "铝→铝箔"),
    EdgeDef("mat_petroleum",     "sub_electrolyte","supply_chain", 0.40, 1.0, 0.80, "石油→电解液溶剂"),
    EdgeDef("mat_rubber",        "sub_rubber_plug","supply_chain", 0.80, 0.5, 0.85, "橡胶→橡胶塞"),
    EdgeDef("mat_paper",         "sub_electro_paper","supply_chain", 0.70, 0.5, 0.80, "纸→电解纸"),
]

# (4) 薄膜电容
_EDGES_FILM_CAP: List[EdgeDef] = [
    EdgeDef("sub_pp_film",       "cat_film_cap", "supply_chain", 0.30, 2.0, 0.85, "PP薄膜(金属化)"),
    EdgeDef("sub_pet_film",      "cat_film_cap", "supply_chain", 0.15, 2.0, 0.80, "PET薄膜(部分规格)"),
    EdgeDef("sub_al_zn_spray",   "cat_film_cap", "supply_chain", 0.10, 1.5, 0.85, "铝锌喷金层(端面电极)"),
    EdgeDef("mat_epoxy_resin",   "cat_film_cap", "supply_chain", 0.05, 1.5, 0.75, "环氧树脂(封装)"),
    # 第 2 层
    EdgeDef("mat_pp",            "sub_pp_film",  "supply_chain", 0.75, 1.0, 0.85, "聚丙烯→PP薄膜"),
    EdgeDef("mat_petroleum",     "mat_pp",       "supply_chain", 0.60, 0.5, 0.85, "石油→丙烯→PP"),
    EdgeDef("mat_pet_film",      "sub_pet_film", "supply_chain", 0.80, 0.5, 0.85, "PET切片→PET薄膜"),
    EdgeDef("mat_aluminum",      "sub_al_zn_spray","supply_chain", 0.40, 0.5, 0.85, "铝→铝锌喷金"),
    EdgeDef("mat_zinc",          "sub_al_zn_spray","supply_chain", 0.30, 0.5, 0.85, "锌→铝锌喷金"),
]

# (5) 电阻
_EDGES_RESISTOR: List[EdgeDef] = [
    EdgeDef("sub_ceramic_sub",   "cat_resistor", "supply_chain", 0.20, 1.5, 0.85, "陶瓷基板"),
    EdgeDef("sub_nichrome_film", "cat_resistor", "supply_chain", 0.15, 1.5, 0.80, "镍铬膜(精密电阻)"),
    EdgeDef("sub_ruthenium_paste","cat_resistor","supply_chain", 0.12, 2.0, 0.80, "钌浆(厚膜电阻)"),
    EdgeDef("sub_cu_terminal_r", "cat_resistor", "supply_chain", 0.10, 1.0, 0.85, "铜端头"),
    # 第 2 层
    EdgeDef("mat_dielectric_ceramic","sub_ceramic_sub","supply_chain", 0.70, 1.0, 0.85, "陶瓷→陶瓷基板"),
    EdgeDef("mat_nickel_chromium","sub_nichrome_film","supply_chain", 0.80, 0.5, 0.85, "镍铬→镍铬膜"),
    EdgeDef("mat_nickel",        "mat_nickel_chromium","supply_chain", 0.60, 0.5, 0.85, "镍→镍铬合金"),
    EdgeDef("mat_ruthenium",     "sub_ruthenium_paste","supply_chain", 0.75, 1.0, 0.80, "钌→钌浆"),
    EdgeDef("mat_copper",        "sub_cu_terminal_r","supply_chain", 0.80, 0.5, 0.90, "铜→铜端头"),
]

# (6) 连接器
_EDGES_CONNECTOR: List[EdgeDef] = [
    EdgeDef("sub_cu_alloy",      "cat_connector", "supply_chain", 0.25, 2.0, 0.90, "铜合金端子"),
    EdgeDef("sub_au_sn_ni_plate","cat_connector", "supply_chain", 0.15, 1.5, 0.85, "镀金/锡/镍层"),
    EdgeDef("sub_lcp_housing",   "cat_connector", "supply_chain", 0.10, 2.0, 0.80, "LCP外壳(高频连接器)"),
    EdgeDef("sub_pbt_housing",   "cat_connector", "supply_chain", 0.08, 1.5, 0.80, "PBT外壳"),
    EdgeDef("sub_pa66_housing",  "cat_connector", "supply_chain", 0.08, 1.5, 0.75, "PA66外壳"),
    # 第 2 层
    EdgeDef("mat_copper",        "sub_cu_alloy",  "supply_chain", 0.70, 1.0, 0.90, "铜→铜合金"),
    EdgeDef("mat_copper_alloy",  "sub_cu_alloy",  "supply_chain", 0.60, 1.0, 0.90, "铜合金→铜合金端子"),
    EdgeDef("mat_gold",          "sub_au_sn_ni_plate","supply_chain", 0.30, 0.5, 0.85, "金→镀金层"),
    EdgeDef("mat_tin",           "sub_au_sn_ni_plate","supply_chain", 0.25, 0.5, 0.85, "锡→镀锡层"),
    EdgeDef("mat_nickel",        "sub_au_sn_ni_plate","supply_chain", 0.20, 0.5, 0.85, "镍→镀镍层"),
    EdgeDef("mat_lcp",           "sub_lcp_housing","supply_chain", 0.80, 1.0, 0.80, "LCP→连接器外壳"),
    EdgeDef("mat_pbt",           "sub_pbt_housing","supply_chain", 0.80, 1.0, 0.80, "PBT→连接器外壳"),
    EdgeDef("mat_pa66",          "sub_pa66_housing","supply_chain", 0.80, 1.0, 0.80, "PA66→连接器外壳"),
    EdgeDef("mat_petroleum",     "mat_lcp",       "supply_chain", 0.50, 1.0, 0.75, "石油→LCP单体"),
    EdgeDef("mat_petroleum",     "mat_pbt",       "supply_chain", 0.50, 1.0, 0.75, "石油→PBT"),
    EdgeDef("mat_petroleum",     "mat_pa66",      "supply_chain", 0.50, 1.0, 0.75, "石油→PA66(己内酰胺)"),
]

# (7) 线束
_EDGES_WIRE: List[EdgeDef] = [
    EdgeDef("sub_cu_wire",       "cat_wire_harness", "supply_chain", 0.45, 0.8, 0.95, "铜线(导体)"),
    EdgeDef("sub_pvc_jacket",    "cat_wire_harness", "supply_chain", 0.15, 0.8, 0.85, "PVC/XLPE/TPE护套"),
    EdgeDef("sub_terminal",      "cat_wire_harness", "supply_chain", 0.12, 0.5, 0.90, "端子(压接)"),
    # 第 2 层
    EdgeDef("mat_copper",        "sub_cu_wire",  "supply_chain", 0.85, 0.5, 0.95, "铜→铜线"),
    EdgeDef("mat_pvc",           "sub_pvc_jacket","supply_chain", 0.40, 0.5, 0.85, "PVC→护套"),
    EdgeDef("mat_xlpe",          "sub_pvc_jacket","supply_chain", 0.30, 0.5, 0.85, "XLPE→护套"),
    EdgeDef("mat_tpe",           "sub_pvc_jacket","supply_chain", 0.20, 0.5, 0.80, "TPE→护套"),
    EdgeDef("mat_petroleum",     "mat_pvc",      "supply_chain", 0.50, 0.5, 0.85, "石油→PVC"),
    EdgeDef("mat_petroleum",     "mat_xlpe",     "supply_chain", 0.50, 0.5, 0.80, "石油→XLPE"),
    EdgeDef("mat_petroleum",     "mat_tpe",      "supply_chain", 0.50, 0.5, 0.80, "石油→TPE"),
    EdgeDef("mat_copper",        "sub_terminal", "supply_chain", 0.75, 0.5, 0.90, "铜→端子"),
]

# (8) 继电器
_EDGES_RELAY: List[EdgeDef] = [
    EdgeDef("sub_ag_contact",    "cat_relay", "supply_chain", 0.20, 3.0, 0.90, "银触点(核心)"),
    EdgeDef("sub_cu_coil",       "cat_relay", "supply_chain", 0.15, 2.5, 0.85, "铜线圈"),
    EdgeDef("sub_fe_ni_core",    "cat_relay", "supply_chain", 0.10, 2.5, 0.80, "铁镍合金磁芯"),
    EdgeDef("sub_plastic_shell_r","cat_relay","supply_chain", 0.08, 2.0, 0.75, "塑胶壳"),
    # 第 2 层
    EdgeDef("mat_silver",        "sub_ag_contact","supply_chain", 0.80, 1.0, 0.90, "银→银触点"),
    EdgeDef("mat_copper",        "sub_cu_coil","supply_chain", 0.85, 1.0, 0.90, "铜→铜线圈"),
    EdgeDef("mat_iron_nickel",   "sub_fe_ni_core","supply_chain", 0.70, 1.0, 0.85, "铁镍合金→磁芯"),
    EdgeDef("mat_nickel",        "mat_iron_nickel","supply_chain", 0.40, 0.5, 0.85, "镍→铁镍合金"),
    EdgeDef("mat_pa66",          "sub_plastic_shell_r","supply_chain", 0.70, 1.0, 0.80, "PA66→继电器外壳"),
    EdgeDef("mat_pbt",           "sub_plastic_shell_r","supply_chain", 0.60, 1.0, 0.75, "PBT→继电器外壳"),
]

# (9) 电感/变压器
_EDGES_INDUCTOR: List[EdgeDef] = [
    EdgeDef("sub_cu_wire_i",     "cat_inductor", "supply_chain", 0.25, 1.5, 0.90, "铜线(绕组)"),
    EdgeDef("sub_ferrite_core",  "cat_inductor", "supply_chain", 0.20, 2.0, 0.85, "铁氧体磁芯"),
    EdgeDef("sub_si_steel",      "cat_inductor", "supply_chain", 0.15, 2.0, 0.85, "硅钢片(变压器)"),
    EdgeDef("sub_bone_i",        "cat_inductor", "supply_chain", 0.08, 1.5, 0.75, "骨架"),
    # 第 2 层
    EdgeDef("mat_copper",        "sub_cu_wire_i","supply_chain", 0.85, 0.5, 0.95, "铜→铜线绕组"),
    EdgeDef("mat_ferrite",       "sub_ferrite_core","supply_chain", 0.80, 1.0, 0.85, "铁氧体→磁芯"),
    EdgeDef("mat_silicon_steel", "sub_si_steel", "supply_chain", 0.85, 1.0, 0.90, "硅钢→硅钢片"),
    EdgeDef("mat_pbt",           "sub_bone_i",   "supply_chain", 0.60, 0.5, 0.75, "PBT→骨架"),
    EdgeDef("mat_pa66",          "sub_bone_i",   "supply_chain", 0.50, 0.5, 0.75, "PA66→骨架"),
]

# (10) MOSFET/IGBT
_EDGES_MOSFET: List[EdgeDef] = [
    EdgeDef("sub_wafer",         "cat_mosfet_igbt", "supply_chain", None, None, 0.85, "晶圆(以供需为主)"),
    EdgeDef("sub_cu_leadframe",  "cat_mosfet_igbt", "supply_chain", 0.12, 2.0, 0.80, "铜框架/引线框架"),
    EdgeDef("sub_epoxy_mold_m",  "cat_mosfet_igbt", "supply_chain", 0.08, 2.0, 0.75, "环氧塑封料"),
    EdgeDef("sub_ceramic_dbc",   "cat_mosfet_igbt", "supply_chain", 0.10, 2.5, 0.80, "陶瓷DBC基板(SiC/IGBT)"),
    # 第 2 层
    EdgeDef("mat_silicon_wafer", "sub_wafer",    "supply_chain", None, None, 0.85, "硅片→晶圆"),
    EdgeDef("mat_copper",        "sub_cu_leadframe","supply_chain", 0.70, 1.0, 0.85, "铜→铜框架"),
    EdgeDef("mat_epoxy_molding", "sub_epoxy_mold_m","supply_chain", 0.80, 1.0, 0.80, "环氧塑封料"),
    EdgeDef("mat_ceramic_substrate","sub_ceramic_dbc","supply_chain", 0.70, 1.5, 0.80, "陶瓷→DBC基板"),
]

# (11) 散热器
_EDGES_HEATSINK: List[EdgeDef] = [
    EdgeDef("sub_al_extrusion",  "cat_heatsink", "supply_chain", 0.35, 1.5, 0.90, "铝型材(主要)"),
    EdgeDef("sub_al_diecast",    "cat_heatsink", "supply_chain", 0.15, 1.5, 0.85, "压铸铝"),
    EdgeDef("sub_cu_heatpipe",   "cat_heatsink", "supply_chain", 0.20, 1.5, 0.85, "铜热管(高端)"),
    EdgeDef("sub_silicone_pad",  "cat_heatsink", "supply_chain", 0.05, 1.0, 0.80, "导热硅胶垫"),
    # 第 2 层
    EdgeDef("mat_aluminum",      "sub_al_extrusion","supply_chain", 0.80, 0.5, 0.90, "铝→铝型材"),
    EdgeDef("mat_al_alloy_plate","sub_al_extrusion","supply_chain", 0.70, 0.5, 0.90, "铝合金→铝型材"),
    EdgeDef("mat_aluminum",      "sub_al_diecast","supply_chain", 0.80, 0.5, 0.90, "铝→压铸铝"),
    EdgeDef("mat_copper",        "sub_cu_heatpipe","supply_chain", 0.85, 0.5, 0.90, "铜→铜热管"),
    EdgeDef("mat_silicone_thermal","sub_silicone_pad","supply_chain", 0.70, 0.5, 0.80, "导热硅胶→硅胶垫"),
]

# (12) 结构件
_EDGES_STRUCTURAL: List[EdgeDef] = [
    EdgeDef("sub_cold_rolled_s", "cat_structural", "supply_chain", 0.25, 2.0, 0.90, "冷轧板"),
    EdgeDef("sub_stainless_s",   "cat_structural", "supply_chain", 0.20, 2.0, 0.85, "不锈钢板"),
    EdgeDef("sub_al_plate_s",    "cat_structural", "supply_chain", 0.15, 1.5, 0.85, "铝板"),
    EdgeDef("sub_zinc_alloy_s",  "cat_structural", "supply_chain", 0.12, 2.0, 0.80, "锌合金(压铸)"),
    EdgeDef("sub_abs_pc_shell",  "cat_structural", "supply_chain", 0.10, 1.5, 0.80, "ABS/PC外壳"),
    # 第 2 层
    EdgeDef("mat_cold_rolled",   "sub_cold_rolled_s","supply_chain", 0.85, 1.0, 0.90, "冷轧板→结构件"),
    EdgeDef("mat_stainless",     "sub_stainless_s","supply_chain", 0.85, 1.0, 0.90, "不锈钢→结构件"),
    EdgeDef("mat_al_alloy_plate","sub_al_plate_s","supply_chain", 0.80, 0.5, 0.85, "铝板→结构件"),
    EdgeDef("mat_aluminum",      "sub_al_plate_s","supply_chain", 0.70, 0.5, 0.85, "铝→铝板"),
    EdgeDef("mat_zinc_alloy",    "sub_zinc_alloy_s","supply_chain", 0.80, 1.0, 0.85, "锌合金→压铸件"),
    EdgeDef("mat_zinc",          "mat_zinc_alloy", "supply_chain", 0.60, 0.5, 0.80, "锌→锌合金"),
    EdgeDef("mat_abs",           "sub_abs_pc_shell","supply_chain", 0.50, 0.5, 0.80, "ABS→外壳"),
    EdgeDef("mat_pc",            "sub_abs_pc_shell","supply_chain", 0.40, 0.5, 0.80, "PC→外壳"),
    EdgeDef("mat_petroleum",     "mat_abs",        "supply_chain", 0.50, 1.0, 0.75, "石油→ABS"),
    EdgeDef("mat_petroleum",     "mat_pc",         "supply_chain", 0.50, 1.0, 0.75, "石油→PC"),
]

# (13) 电池
_EDGES_BATTERY: List[EdgeDef] = [
    EdgeDef("sub_li_carbonate",  "cat_battery", "supply_chain", 0.25, 2.0, 0.90, "碳酸锂(正极材料)"),
    EdgeDef("sub_cobalt_salt",   "cat_battery", "supply_chain", 0.15, 2.5, 0.85, "钴盐(三元正极)"),
    EdgeDef("sub_nickel_salt",   "cat_battery", "supply_chain", 0.15, 2.5, 0.85, "镍盐(三元正极)"),
    EdgeDef("sub_manganese_salt","cat_battery", "supply_chain", 0.08, 2.0, 0.80, "锰盐"),
    EdgeDef("sub_graphite_anode","cat_battery", "supply_chain", 0.12, 1.5, 0.85, "石墨负极"),
    EdgeDef("sub_cu_foil_bat",   "cat_battery", "supply_chain", 0.08, 1.0, 0.85, "铜箔(负极集流体)"),
    EdgeDef("sub_al_foil_bat",   "cat_battery", "supply_chain", 0.05, 1.0, 0.85, "铝箔(正极集流体)"),
    # 第 2 层
    EdgeDef("mat_lithium_carb",  "sub_li_carbonate","supply_chain", 0.85, 1.0, 0.90, "碳酸锂"),
    EdgeDef("mat_cobalt",        "sub_cobalt_salt","supply_chain", 0.80, 1.0, 0.85, "钴→钴盐"),
    EdgeDef("mat_nickel",        "sub_nickel_salt","supply_chain", 0.80, 1.0, 0.85, "镍→镍盐"),
    EdgeDef("mat_manganese",     "sub_manganese_salt","supply_chain", 0.80, 1.0, 0.85, "锰→锰盐"),
    EdgeDef("mat_graphite",      "sub_graphite_anode","supply_chain", 0.85, 1.0, 0.90, "石墨→负极"),
    EdgeDef("mat_copper",        "sub_cu_foil_bat","supply_chain", 0.85, 0.5, 0.90, "铜→铜箔"),
    EdgeDef("mat_aluminum",      "sub_al_foil_bat","supply_chain", 0.85, 0.5, 0.90, "铝→铝箔"),
]

# (14) 显示/光电
_EDGES_DISPLAY: List[EdgeDef] = [
    EdgeDef("sub_glass_panel",   "cat_display", "supply_chain", None, None, 0.80, "玻璃基板(面板)"),
    EdgeDef("sub_polarizer_f",   "cat_display", "supply_chain", None, None, 0.80, "偏光片"),
    EdgeDef("sub_led_die",       "cat_display", "supply_chain", None, None, 0.80, "LED芯片"),
    EdgeDef("sub_re_fluor",      "cat_display", "supply_chain", None, None, 0.75, "稀土荧光粉"),
    # 第 2 层
    EdgeDef("mat_glass_substrate","sub_glass_panel","supply_chain", 0.80, 1.5, 0.80, "玻璃基板"),
    EdgeDef("mat_polarizer",     "sub_polarizer_f","supply_chain", 0.80, 2.0, 0.80, "偏光片"),
    EdgeDef("mat_led_chip",      "sub_led_die",  "supply_chain", 0.80, 2.0, 0.80, "LED芯片"),
    EdgeDef("mat_rare_earth_fluor","sub_re_fluor","supply_chain", 0.75, 2.0, 0.75, "稀土荧光粉"),
    EdgeDef("mat_ito",           "sub_glass_panel","supply_chain", 0.15, 2.0, 0.75, "ITO→玻璃基板(电极)"),
]


# ─── 汇总所有边 ──────────────────────────────────────────────

ALL_EDGES: List[EdgeDef] = (
    _EDGES_PCB + _EDGES_MLCC + _EDGES_AL_CAP + _EDGES_FILM_CAP
    + _EDGES_RESISTOR + _EDGES_CONNECTOR + _EDGES_WIRE + _EDGES_RELAY
    + _EDGES_INDUCTOR + _EDGES_MOSFET + _EDGES_HEATSINK
    + _EDGES_STRUCTURAL + _EDGES_BATTERY + _EDGES_DISPLAY
)


# ────────────────────────────────────────────────────────────
# 4. 品类-材料直接映射 (category_material_mapping)
#    用于 get_bom_exposure 快速匹配
# ────────────────────────────────────────────────────────────

@dataclass
class CategoryMaterialDef:
    component_category: str
    material_name: str
    cost_weight: Optional[float] = None
    data_source: str = ""


CATEGORY_MATERIAL_MAPPINGS: List[CategoryMaterialDef] = [
    # (1) PCB/FPC
    CategoryMaterialDef("PCB/FPC", "铜箔",       0.25, "SMM铜"),
    CategoryMaterialDef("PCB/FPC", "覆铜板CCL",  0.30, "SMM铜"),
    CategoryMaterialDef("PCB/FPC", "玻纤布",     0.10, "SMM树脂行业"),
    CategoryMaterialDef("PCB/FPC", "环氧树脂",   0.10, "SMM树脂行业"),
    CategoryMaterialDef("PCB/FPC", "PI膜",       0.08, "化工行业"),
    CategoryMaterialDef("PCB/FPC", "油墨",       0.05, "化工行业"),
    # (2) MLCC
    CategoryMaterialDef("MLCC", "钛酸钡",       0.25, "SMM稀土"),
    CategoryMaterialDef("MLCC", "镍粉",         0.15, "SMM镍"),
    CategoryMaterialDef("MLCC", "铜端头",       0.10, "SMM铜"),
    CategoryMaterialDef("MLCC", "银浆",         0.08, "SMM银"),
    CategoryMaterialDef("MLCC", "陶瓷粉体",     0.10, "SMM稀土"),
    # (3) 铝电解电容
    CategoryMaterialDef("铝电解电容", "铝箔",    0.35, "SMM铝"),
    CategoryMaterialDef("铝电解电容", "电解液",  0.15, "SMM化工"),
    CategoryMaterialDef("铝电解电容", "电子纸",  0.08, "造纸行业"),
    CategoryMaterialDef("铝电解电容", "橡胶塞",  0.05, "化工行业"),
    # (4) 薄膜电容
    CategoryMaterialDef("薄膜电容", "PP薄膜",    0.30, "SMM塑料"),
    CategoryMaterialDef("薄膜电容", "PET薄膜",   0.15, "SMM塑料"),
    CategoryMaterialDef("薄膜电容", "铝锌喷金",  0.10, "SMM铝锌"),
    CategoryMaterialDef("薄膜电容", "环氧树脂",  0.05, "SMM树脂行业"),
    # (5) 电阻
    CategoryMaterialDef("电阻", "陶瓷基板",      0.20, "SMM/陶瓷"),
    CategoryMaterialDef("电阻", "镍铬膜",        0.15, "SMM镍"),
    CategoryMaterialDef("电阻", "钌浆",          0.12, "SMM贵金属"),
    CategoryMaterialDef("电阻", "铜端头",        0.10, "SMM铜"),
    # (6) 连接器
    CategoryMaterialDef("连接器", "铜合金",      0.25, "SMM铜"),
    CategoryMaterialDef("连接器", "镀金锡镍",    0.15, "SMM铜锡镍金"),
    CategoryMaterialDef("连接器", "LCP",         0.10, "化工行业"),
    CategoryMaterialDef("连接器", "PBT",         0.08, "化工行业"),
    CategoryMaterialDef("连接器", "PA66",        0.08, "化工行业"),
    # (7) 线束
    CategoryMaterialDef("线束", "铜线",          0.45, "SMM铜"),
    CategoryMaterialDef("线束", "PVC/XLPE/TPE", 0.15, "SMM塑料"),
    CategoryMaterialDef("线束", "端子",          0.12, "SMM铜"),
    # (8) 继电器
    CategoryMaterialDef("继电器", "银触点",      0.20, "SMM银"),
    CategoryMaterialDef("继电器", "铜线圈",      0.15, "SMM铜"),
    CategoryMaterialDef("继电器", "铁镍合金",    0.10, "SMM镍/钢材"),
    CategoryMaterialDef("继电器", "塑胶壳",      0.08, "化工行业"),
    # (9) 电感/变压器
    CategoryMaterialDef("电感/变压器", "铜线",   0.25, "SMM铜"),
    CategoryMaterialDef("电感/变压器", "铁氧体磁芯", 0.20, "SMM/陶瓷"),
    CategoryMaterialDef("电感/变压器", "硅钢片", 0.15, "Mysteel"),
    CategoryMaterialDef("电感/变压器", "骨架",   0.08, "化工/塑料"),
    # (10) MOSFET/IGBT
    CategoryMaterialDef("MOSFET/IGBT", "晶圆",  None, "SEMI"),
    CategoryMaterialDef("MOSFET/IGBT", "铜框架", 0.12, "SMM铜"),
    CategoryMaterialDef("MOSFET/IGBT", "环氧塑封料", 0.08, "封装材料"),
    CategoryMaterialDef("MOSFET/IGBT", "陶瓷DBC", 0.10, "半导体材料"),
    # (11) 散热器
    CategoryMaterialDef("散热器", "铝型材",      0.35, "SMM铝"),
    CategoryMaterialDef("散热器", "压铸铝",      0.15, "SMM铝"),
    CategoryMaterialDef("散热器", "铜热管",      0.20, "SMM铜"),
    CategoryMaterialDef("散热器", "导热硅胶",    0.05, "化工行业"),
    # (12) 结构件
    CategoryMaterialDef("结构件", "冷轧钢板",    0.25, "Mysteel"),
    CategoryMaterialDef("结构件", "不锈钢",      0.20, "Mysteel"),
    CategoryMaterialDef("结构件", "铝板",        0.15, "SMM铝"),
    CategoryMaterialDef("结构件", "锌合金",      0.12, "SMM/压铸"),
    CategoryMaterialDef("结构件", "ABS/PC",      0.10, "SMM塑料"),
    # (13) 电池
    CategoryMaterialDef("电池", "碳酸锂",        0.25, "SMM锂电/USGS"),
    CategoryMaterialDef("电池", "钴",            0.15, "SMM锂电"),
    CategoryMaterialDef("电池", "镍",            0.15, "SMM锂电"),
    CategoryMaterialDef("电池", "锰",            0.08, "SMM锂电"),
    CategoryMaterialDef("电池", "石墨",          0.12, "USGS"),
    CategoryMaterialDef("电池", "铜箔",          0.08, "SMM铜"),
    CategoryMaterialDef("电池", "铝箔",          0.05, "SMM铝"),
    # (14) 显示/光电
    CategoryMaterialDef("显示/光电", "玻璃基板", None, "面板行业"),
    CategoryMaterialDef("显示/光电", "偏光片",   None, "面板行业"),
    CategoryMaterialDef("显示/光电", "LED芯片",  None, "SEMI"),
    CategoryMaterialDef("显示/光电", "稀土荧光粉", None, "SMM稀土/USGS"),
]


# ────────────────────────────────────────────────────────────
# 5. 工具函数: 通过 node_id 快速查找
# ────────────────────────────────────────────────────────────

_NODE_INDEX: Dict[str, NodeDef] = {n.node_id: n for n in ALL_NODES}


def get_node(node_id: str) -> Optional[NodeDef]:
    """通过 node_id 获取节点定义。"""
    return _NODE_INDEX.get(node_id)


def get_all_bom_category_ids() -> List[str]:
    """返回所有 BOM 品类的 node_id 列表。"""
    return [n.node_id for n in _BOM_CATEGORIES]


def get_bom_category_name(node_id: str) -> str:
    """获取品类节点的显示名称。"""
    node = _NODE_INDEX.get(node_id)
    return node.name if node else ""


# ────────────────────────────────────────────────────────────
# 6. 验证: 确保 14 品类全覆盖
# ────────────────────────────────────────────────────────────

def validate_coverage() -> Dict[str, bool]:
    """验证 14 个品类是否全部有边数据。"""
    covered_cats = set()
    for e in ALL_EDGES:
        if e.to_id.startswith("cat_"):
            covered_cats.add(e.to_id)

    all_cats = set(get_all_bom_category_ids())
    return {
        "total_categories": len(all_cats),
        "covered_categories": len(covered_cats),
        "all_covered": covered_cats == all_cats,
        "missing": list(all_cats - covered_cats),
    }
