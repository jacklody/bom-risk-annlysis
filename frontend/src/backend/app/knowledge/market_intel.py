"""市场行情情报知识库 —— 编码行业公认的市场供需状况。
每条情报来自行业媒体、原厂公告、代理商邮件等多元渠道交叉验证。
格式：[品牌, 品类, 事件类型, 严重度, 置信度, 预计交期影响(周), 预计价格影响(%)，摘要，对BOM业务的建议]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class MarketIntelEntry:
    brand: str = ""
    category: str = ""
    event_type: str = "shortage"
    severity: str = "high"
    confidence: float = 0.90
    lead_time_impact_weeks: Optional[int] = None
    price_impact_pct: Optional[float] = None
    summary: str = ""
    business_advice: str = ""
    sources: list[str] = field(default_factory=list)
    effective_date: Optional[str] = None   # 情报生效日期 ISO 格式（如 "2026-04-01"）
    expiry_date: Optional[str] = None       # 情报失效日期 ISO 格式（如 "2026-07-01"）


# ================================================================
# 2026年Q2 半导体/电子元器件市场行情情报
# 数据来源：代理商通知、行业媒体（国际电子商情/芯师爷/满天芯）、原厂公告、供应链反馈
# ================================================================

MARKET_INTEL_ENTRIES: list[MarketIntelEntry] = [
    # ── 1. 高容MLCC缺货 ──
    MarketIntelEntry(
        brand="",
        category="high_cap_mlcc",
        event_type="shortage",
        severity="critical",
        confidence=0.95,
        lead_time_impact_weeks=16,
        price_impact_pct=15.0,
        summary="高容MLCC（≥10μF）全球产能紧张，村田/三星电机/太阳诱电交期延长至16周以上，部分料号现货价格翻倍",
        business_advice="①优先级最高的排查品类。②确认BOM中所有高容MLCC的当前库存水位≥8周。③尽快锁定现货/期货订单。④评估替代料（如用钽电容或聚合物电容替代部分高容MLCC）。",
        sources=["村田代理商通知", "三星电机涨价函", "芯师爷2026Q2MLCC专题", "国际电子商情"],
        effective_date="2026-04-01",
        expiry_date="2026-09-01",
    ),
    MarketIntelEntry(
        brand="Murata",
        category="high_cap_mlcc",
        event_type="shortage",
        severity="critical",
        confidence=0.95,
        lead_time_impact_weeks=16,
        price_impact_pct=15.0,
        summary="村田高容MLCC交期延长至16-20周，部分车规级料号已暂停接单",
        business_advice="村田品牌高容MLCC应优先排查库存，必要时寻求三星电机或国巨替代。",
        sources=["村田代理商通知"],
        effective_date="2026-04-01",
        expiry_date="2026-09-01",
    ),
    MarketIntelEntry(
        brand="Samsung",
        category="high_cap_mlcc",
        event_type="price_increase",
        severity="high",
        confidence=0.90,
        price_impact_pct=12.0,
        summary="三星电机MLCC全系列价格上调10-15%，高容规格缺货尤为严重",
        business_advice="三星电机MLCC属通用料，建议提前锁单，避免排产断档。",
        sources=["三星电机涨价函", "代理商通知"],
        effective_date="2026-04-01",
        expiry_date="2026-09-01",
    ),
    MarketIntelEntry(
        brand="Yageo",
        category="MLCC",
        event_type="price_increase",
        severity="medium",
        confidence=0.85,
        price_impact_pct=8.0,
        summary="国巨MLCC价格上调5-10%，跟随日系原厂涨价趋势",
        business_advice="国巨MLCC涨幅相对温和，可优先选用国巨/风华作为日系高容MLCC的替代渠道。",
        sources=["国巨经销商通知"],
        effective_date="2026-04-01",
        expiry_date="2026-09-01",
    ),

    # ── 2. 被动分立器件涨价（长晶/杨杰等） ──
    MarketIntelEntry(
        brand="长晶",
        category="discrete_passive",
        event_type="price_increase",
        severity="high",
        confidence=0.90,
        lead_time_impact_weeks=10,
        price_impact_pct=18.0,
        summary="长晶科技（Changjing）二极管/三极管/MOSFET全系列涨价15-20%，SOD-123FL/SMA封装交期延长",
        business_advice="①BOM中长晶品牌的分立器件需逐项复核库存。②SOT-23/SOD-123等通用封装可评估其他国产品牌（如乐山无线电LRC）。③如有用量大的物料，建议锁3个月期货。",
        sources=["长晶科技涨价通知", "代理商邮件", "华强北现货行情"],
        effective_date="2026-04-01",
        expiry_date="2026-09-01",
    ),
    MarketIntelEntry(
        brand="杨杰",
        category="discrete_passive",
        event_type="price_increase",
        severity="high",
        confidence=0.88,
        lead_time_impact_weeks=10,
        price_impact_pct=15.0,
        summary="杨杰电子分立器件全线涨价12-18%，整流桥/快恢复二极管缺货严重",
        business_advice="杨杰品牌物料建议尽快确认二级市场现货可得性，必要时启动替代料验证流程。",
        sources=["杨杰电子涨价函", "代理商通知"],
        effective_date="2026-04-01",
        expiry_date="2026-09-01",
    ),
    MarketIntelEntry(
        brand="",
        category="discrete_passive",
        event_type="price_increase",
        severity="high",
        confidence=0.88,
        lead_time_impact_weeks=8,
        price_impact_pct=12.0,
        summary="国产被动分立器件（二三极管/MOSFET/整流桥）整体进入涨价周期，中小品牌跟涨明显",
        business_advice="通用分立器件建议：①锁定主力品牌渠道。②G/A类物料按季度锁价。③B/C类物料评估现货市场可得性。",
        sources=["华强北指数", "国际电子商情", "满天芯"],
        effective_date="2026-04-01",
        expiry_date="2026-09-01",
    ),

    # ── 3. 存储类芯片（SDRAM尤其紧张） ──
    MarketIntelEntry(
        brand="",
        category="dram",
        event_type="shortage",
        severity="critical",
        confidence=0.95,
        lead_time_impact_weeks=20,
        price_impact_pct=25.0,
        summary="全球DRAM（含SDRAM/DDR3/DDR4）产能紧张，三星/美光/SK海力士交期普遍12-20周，DDR3因停产加速缺货",
        business_advice="①所有含DRAM/SDRAM的BOM物料标记为战略管控。②DDR3型号需立即确认生命周期状态（原厂是否已EOL）。③DDR4建议按季度锁单锁价。④评估国产替代（长鑫存储CXMT DDR4）。",
        sources=["美光财报", "三星半导体业务更新", "TrendForce DRAM报告", "国际电子商情"],
        effective_date="2026-04-01",
        expiry_date="2026-09-01",
    ),
    MarketIntelEntry(
        brand="",
        category="nand",
        event_type="price_increase",
        severity="high",
        confidence=0.90,
        price_impact_pct=15.0,
        summary="NAND Flash价格Q2环比上涨10-15%，大容量颗粒（≥8Gb）供给偏紧",
        business_advice="NAND Flash物料建议按型号逐项评估替代方案（如eMMC与UFS间的Pin-to-Pin兼容性）。",
        sources=["TrendForce NAND报告", "国际电子商情"],
        effective_date="2026-04-01",
        expiry_date="2026-09-01",
    ),

    # ── 4. MCU（尤其含存储的MCU） ──
    MarketIntelEntry(
        brand="",
        category="mcu",
        event_type="shortage",
        severity="critical",
        confidence=0.93,
        lead_time_impact_weeks=16,
        price_impact_pct=20.0,
        summary="MCU（微控制器）市场持续紧缺，尤其是内置Flash/SRAM的型号（如STM32/GD32系列），ST/NXP/Microchip交期12-18周",
        business_advice="①BOM中每个MCU型号需逐项确认现货/期货可得性。②STM32系列建议启动GD32/AT32等国产Pin-to-Pin替代评估。③含大容量Flash（≥256KB）的MCU标记为最高优先级。④任何含MCU的PCBA，提前12周以上备安全库存。",
        sources=["ST官方PCN", "NXP代理商通知", "Microchip涨价函", "芯师爷MCU专题", "国际电子商情"],
        effective_date="2026-04-01",
        expiry_date="2026-09-01",
    ),
    MarketIntelEntry(
        brand="ST",
        category="mcu",
        event_type="shortage",
        severity="critical",
        confidence=0.93,
        lead_time_impact_weeks=18,
        price_impact_pct=25.0,
        summary="意法半导体STM32系列MCU全线交期延长至16-20周，STM32F1/F4系列现货价格较目录价溢价50-300%",
        business_advice="STM32系列应作为最高优先级排查。启动国产化替代评估（GD32/AT32/MM32），优先验证Pin-to-Pin兼容型号。",
        sources=["ST官方交期更新", "代理商通知", "华强北现货报价"],
        effective_date="2026-04-01",
        expiry_date="2026-09-01",
    ),
    MarketIntelEntry(
        brand="",
        category="mcu_with_storage",
        event_type="shortage",
        severity="critical",
        confidence=0.90,
        lead_time_impact_weeks=18,
        price_impact_pct=22.0,
        summary="内置Flash≥256KB或含SRAM≥64KB的MCU因存储晶圆产能紧张，交期更长且涨价幅度更大",
        business_advice="含大容量存储的MCU应作为战略物料管理：①确认每个型号的库存depth。②提前与代理商锁单。③系统级方案上评估MCU+外挂Flash替代内置大Flash MCU。",
        sources=["产业链调研", "原厂交期报告"],
        effective_date="2026-04-01",
        expiry_date="2026-09-01",
    ),

    # ── 5. PCB行业 ──
    MarketIntelEntry(
        brand="",
        category="pcb",
        event_type="shortage",
        severity="critical",
        confidence=0.92,
        lead_time_impact_weeks=12,
        price_impact_pct=20.0,
        summary="高端PCB（HDI/多层/高频板）产能紧张，核心瓶颈在日本日东纺（Nitto Boseki）垄断的纺布设备产能不足，导致玻纤布基板供给受限",
        business_advice="①所有≥4层PCB的BOM项目标记为交期风险。②HDI/高频板/厚铜板需提前10周以上下单。③评估是否可用双面板替代部分四层板设计。④确认PCB供应商的玻纤布库存和备料情况。",
        sources=["PCB行业调研", "日东纺产能公告", "深南电路/景旺电子供应商反馈", "国际电子商情PCB专题"],
        effective_date="2026-04-01",
        expiry_date="2026-09-01",
    ),
    MarketIntelEntry(
        brand="",
        category="pcb",
        event_type="lead_time",
        severity="high",
        confidence=0.90,
        lead_time_impact_weeks=8,
        summary="普通双面板交期从4周延长至6-8周，四层板从6周延长至8-12周",
        business_advice="所有PCB板的采购提前期应在上游设计阶段即启动备料流程，避免因PCB交期延误拖累整机排产。",
        sources=["嘉立创/JLCPCB交期公告", "PCB厂商反馈"],
        effective_date="2026-04-01",
        expiry_date="2026-09-01",
    ),

    # ── 6. 高端功率模块（三菱/英飞凌晶圆紧缺） ──
    MarketIntelEntry(
        brand="",
        category="power_module",
        event_type="shortage",
        severity="critical",
        confidence=0.93,
        lead_time_impact_weeks=24,
        price_impact_pct=30.0,
        summary="IGBT/IPM/SiC等高端功率模块因8英寸/12英寸晶圆产能紧缺，三菱/英飞凌/赛米控交期普遍20-30周，部分工业级模块暂停接新单",
        business_advice="①所有IGBT/IPM等功率模块标记为最高战略风险。②立即确认代理商分货配额。③评估国产替代（斯达半导/士兰微/华润微的IGBT模块）。④SiC器件建议提前半年锁单。",
        sources=["三菱电机功率器件交期更新", "英飞凌代理商通知", "赛米控产能公告", "国际电子商情功率器件专题"],
        effective_date="2026-04-01",
        expiry_date="2026-09-01",
    ),
    MarketIntelEntry(
        brand="Infineon",
        category="power_module",
        event_type="shortage",
        severity="critical",
        confidence=0.93,
        lead_time_impact_weeks=26,
        price_impact_pct=35.0,
        summary="英飞凌IGBT模块交期26周以上，工业级EconoPACK系列暂停接单，汽车级HybridPACK配额削减40%",
        business_advice="英飞凌功率模块应启动紧急替代流程：①确认现有订单是否被削减。②评估斯达半导/中车时代电气替代型号。③提前6个月以上做forecast。",
        sources=["英飞凌官方交期更新", "代理商紧急通知"],
        effective_date="2026-04-01",
        expiry_date="2026-09-01",
    ),
    MarketIntelEntry(
        brand="",
        category="mosfet",
        event_type="shortage",
        severity="high",
        confidence=0.88,
        lead_time_impact_weeks=12,
        price_impact_pct=15.0,
        summary="中高压MOSFET（≥100V）因8英寸晶圆产能不足导致交期延长至10-14周，价格上浮10-18%",
        business_advice="中高压MOSFET建议：①按电压等级分档管理。②≥100V规格提前锁单。③评估华润微/新洁能/东微半导等国产替代。",
        sources=["MOSFET市场调研", "代理商反馈"],
        effective_date="2026-04-01",
        expiry_date="2026-09-01",
    ),

    # ── 7. 晶圆代工产能紧张（波及效应） ──
    MarketIntelEntry(
        brand="",
        category="semiconductor",
        event_type="capacity_issue",
        severity="high",
        confidence=0.90,
        summary="全球8英寸晶圆代工产能持续紧张，台积电/联电/中芯国际产能利用率接近100%，影响大部分模拟IC/电源IC/MOSFET/二三极管",
        business_advice="晶圆产能紧张属于底层问题：①模拟IC/电源IC交期预期偏长。②尽量选择采用12英寸晶圆工艺的先进制程型号（如部分新型电源IC）。③对交期敏感的BOM，优先选用IDM原厂而非Fabless品牌。",
        sources=["台积电财报", "联电产能公告", "SEMI行业报告"],
        effective_date="2026-04-01",
        expiry_date="2026-09-01",
    ),

    # ── 8. 被动元件通用型 ──
    MarketIntelEntry(
        brand="",
        category="resistor",
        event_type="price_increase",
        severity="medium",
        confidence=0.85,
        lead_time_impact_weeks=6,
        price_impact_pct=5.0,
        summary="片式电阻因铜/镍原材料上涨，价格温和上调3-5%，0402/0603通用规格交期4-6周",
        business_advice="片式电阻交期可控、涨幅温和，无需过度备货。建议按常规MRP采购即可。",
        sources=["国巨/Yageo报价更新", "华强北指数"],
        effective_date="2026-04-01",
        expiry_date="2026-09-01",
    ),
    MarketIntelEntry(
        brand="",
        category="tantalum",
        event_type="shortage",
        severity="high",
        confidence=0.88,
        lead_time_impact_weeks=14,
        price_impact_pct=20.0,
        summary="钽电容因钽矿石供应链紧张（主要来自刚果金），交期延长至12-16周，价格大幅上涨",
        business_advice="钽电容物料：①确认每个型号的库存和期货状态。②评估用聚合物电容或高容MLCC替代。③避免在新设计中新增钽电容料号。",
        sources=["AVX/KEMET代理商通知", "钽矿石供应链报告"],
        effective_date="2026-04-01",
        expiry_date="2026-09-01",
    ),

    # ── 9. 连接器/线束 ──
    MarketIntelEntry(
        brand="",
        category="connector",
        event_type="lead_time",
        severity="medium",
        confidence=0.85,
        lead_time_impact_weeks=8,
        summary="连接器交期整体偏长（6-8周），车规级/工业级连接器因汽车电子需求旺盛受影响更大",
        business_advice="连接器类建议：①车规/工规连接器提前10周下单。②消费级连接器（如USB/HDMI/排针）交期正常。③考虑国产连接器替代TE/Molex/JST的高端型号。",
        sources=["TE/Molex交期更新", "代理商反馈"],
        effective_date="2026-04-01",
        expiry_date="2026-09-01",
    ),

    # ── 10. 晶振/时钟 ──
    MarketIntelEntry(
        brand="",
        category="crystal",
        event_type="lead_time",
        severity="medium",
        confidence=0.85,
        lead_time_impact_weeks=8,
        summary="晶振交期从4周延长至6-8周，高精度温补晶振(TCXO)和恒温晶振(OCXO)交期更长",
        business_advice="晶振类物料提前6周备货即可。TCXO/OCXO等特殊晶振需提前10周确认交期。",
        sources=["晶振厂商反馈", "代理商通知"],
        effective_date="2026-04-01",
        expiry_date="2026-09-01",
    ),
]


# ================================================================
# 品类映射表：将BOM中的品类文本映射到标准化品类
# 同时定义每个品类的当前风险等级和交期/价格影响
# ================================================================
CATEGORY_MARKET_RISK: dict = {
    "high_cap_mlcc": {
        "risk_level": "red",
        "lead_time_weeks": 16,
        "price_impact_pct": 15.0,
        "advice": "高容MLCC全球缺货，立即排查库存并锁单",
    },
    "MLCC": {
        "risk_level": "yellow",
        "lead_time_weeks": 8,
        "price_impact_pct": 8.0,
        "advice": "普通MLCC跟涨，关注品牌和规格",
    },
    "dram": {
        "risk_level": "red",
        "lead_time_weeks": 20,
        "price_impact_pct": 25.0,
        "advice": "DRAM严重缺货，DDR3需确认EOL状态，DDR4锁单锁价",
    },
    "nand": {
        "risk_level": "yellow",
        "lead_time_weeks": 12,
        "price_impact_pct": 15.0,
        "advice": "NAND Flash涨价明显，大容量优先锁单",
    },
    "mcu": {
        "risk_level": "red",
        "lead_time_weeks": 16,
        "price_impact_pct": 20.0,
        "advice": "MCU全线紧缺，STM32系列启动国产替代",
    },
    "mcu_with_storage": {
        "risk_level": "red",
        "lead_time_weeks": 18,
        "price_impact_pct": 22.0,
        "advice": "含大存储MCU属战略物料，备足12周库存",
    },
    "pcb": {
        "risk_level": "yellow",
        "lead_time_weeks": 10,
        "price_impact_pct": 15.0,
        "advice": "PCB交期延长，高端PCB提前10周下单",
    },
    "power_module": {
        "risk_level": "red",
        "lead_time_weeks": 24,
        "price_impact_pct": 30.0,
        "advice": "功率模块极度紧缺，确认配额并启动国产替代",
    },
    "mosfet": {
        "risk_level": "yellow",
        "lead_time_weeks": 12,
        "price_impact_pct": 15.0,
        "advice": "中高压MOSFET紧缺，提前锁单",
    },
    "discrete_passive": {
        "risk_level": "yellow",
        "lead_time_weeks": 10,
        "price_impact_pct": 15.0,
        "advice": "被动分立器件涨价，锁主力品牌渠道",
    },
    "resistor": {
        "risk_level": "green",
        "lead_time_weeks": 6,
        "price_impact_pct": 5.0,
        "advice": "电阻交期可控，按常规采购",
    },
    "tantalum": {
        "risk_level": "red",
        "lead_time_weeks": 14,
        "price_impact_pct": 20.0,
        "advice": "钽电容缺货严重，评估替代方案",
    },
    "connector": {
        "risk_level": "yellow",
        "lead_time_weeks": 8,
        "price_impact_pct": 5.0,
        "advice": "连接器交期偏长，车规级需提前下单",
    },
    "crystal": {
        "risk_level": "yellow",
        "lead_time_weeks": 8,
        "price_impact_pct": 5.0,
        "advice": "晶振交期延长至6-8周",
    },
    "semiconductor": {
        "risk_level": "yellow",
        "lead_time_weeks": 12,
        "price_impact_pct": 10.0,
        "advice": "晶圆产能紧张，影响大部分半导体品类",
    },
    "power_ic": {
        "risk_level": "yellow",
        "lead_time_weeks": 12,
        "price_impact_pct": 12.0,
        "advice": "电源IC交期偏长，优先选用IDM原厂型号",
    },
}

# 高风险品牌列表：这些品牌的料号在当前市场环境下应额外关注
HIGH_RISK_BRANDS: dict = {
    "ST": {"reason": "STM32 MCU全线缺货涨价", "priority": "critical"},
    "Murata": {"reason": "村田高容MLCC交期16周+", "priority": "critical"},
    "Infineon": {"reason": "英飞凌IGBT模块交期26周，部分暂停接单", "priority": "critical"},
    "长晶": {"reason": "长晶科技分立器件涨价15-20%", "priority": "high"},
    "杨杰": {"reason": "杨杰电子分立器件涨价12-18%", "priority": "high"},
    "NXP": {"reason": "NXP MCU交期延长至16周", "priority": "high"},
    "Microchip": {"reason": "Microchip MCU/模拟IC涨价交期延长", "priority": "high"},
    "美光": {"reason": "美光DRAM/NAND产能紧张", "priority": "high"},
    "三星": {"reason": "三星DRAM/MLCC产能紧张", "priority": "high"},
    "Samsung": {"reason": "三星DRAM/MLCC产能紧张", "priority": "high"},
    "TI": {"reason": "TI模拟IC部分料号交期延长", "priority": "medium"},
    "Yageo": {"reason": "国巨跟随日系原厂涨价", "priority": "medium"},
    "国巨": {"reason": "国巨跟随日系原厂涨价", "priority": "medium"},
    "TDK": {"reason": "TDK MLCC/电感交期偏长", "priority": "medium"},
}

# 品类文本模糊匹配表：从BOM raw_category/raw_description 映射到标准化品类
CATEGORY_FUZZY_MAP = {
    "MLCC": "MLCC",
    "mlcc": "MLCC",
    "瓷介电容": "MLCC",
    "陶瓷电容": "MLCC",
    "贴片电容": "MLCC",
    "高容MLCC": "high_cap_mlcc",
    "大容MLCC": "high_cap_mlcc",
    "钽电容": "tantalum",
    "电解电容": "aluminum_electrolytic_capacitor",
    "铝电解": "aluminum_electrolytic_capacitor",
    "电阻": "resistor",
    "片式电阻": "resistor",
    "贴片电阻": "resistor",
    "MCU": "mcu",
    "微控制器": "mcu",
    "单片机": "mcu",
    "主控IC": "mcu",
    "DRAM": "dram",
    "SDRAM": "dram",
    "DDR": "dram",
    "NAND": "nand",
    "Flash": "nand",
    "MOSFET": "mosfet",
    "MOS管": "mosfet",
    "PCB": "pcb",
    "印制板": "pcb",
    "电路板": "pcb",
    "IGBT": "power_module",
    "IPM": "power_module",
    "功率模块": "power_module",
    "电源IC": "power_ic",
    "电源管理": "power_ic",
    "DCDC": "power_ic",
    "LDO": "power_ic",
    "晶振": "crystal",
    "晶体": "crystal",
    "连接器": "connector",
    "接插件": "connector",
    "二极管": "discrete_passive",
    "三极管": "discrete_passive",
    "整流桥": "discrete_passive",
    "分立器件": "discrete_passive",
    "二三极管": "discrete_passive",
    "半导体": "semiconductor",
}
