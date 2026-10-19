"""电子物料风险链路知识库。

本文件集中维护风险链路驾驶舱需要的高置信来源、类别链路、示例事件、BOM影响和策略。
后续接入真实行情/供应商 API 时，优先替换这里的数据源填充逻辑，而不是在页面里硬编码。
"""

from __future__ import annotations


SOURCE_LIBRARY = {
    "src-lme-copper": {
        "sourceName": "LME Copper",
        "sourceLevel": "S",
        "sourceType": "交易所行情",
        "url": "https://www.lme.com/en/Metals/Non-ferrous/LME-Copper",
        "summary": "铜全球基准行情，适用于 PCB、连接器、线缆、电感、变压器和散热件。",
    },
    "src-lme-nickel": {
        "sourceName": "LME Nickel",
        "sourceLevel": "S",
        "sourceType": "交易所行情",
        "url": "https://www.lme.com/en/Metals/Non-ferrous/LME-Nickel",
        "summary": "镍行情，适用于 MLCC 内电极、镀层、电池和部分合金件。",
    },
    "src-lme-aluminium": {
        "sourceName": "LME Aluminium",
        "sourceLevel": "S",
        "sourceType": "交易所行情",
        "url": "https://www.lme.com/en/Metals/Non-ferrous/LME-Aluminium",
        "summary": "铝行情，适用于散热器、外壳、铝电解电容和铝基板。",
    },
    "src-lme-tin": {
        "sourceName": "LME Tin",
        "sourceLevel": "S",
        "sourceType": "交易所行情",
        "url": "https://www.lme.com/en/Metals/Non-ferrous/LME-Tin",
        "summary": "锡行情，适用于焊料、端子镀锡和电子装联成本。",
    },
    "src-lme-cobalt": {
        "sourceName": "LME Cobalt",
        "sourceLevel": "S",
        "sourceType": "交易所行情",
        "url": "https://www.lme.com/en/Metals/EV/LME-Cobalt",
        "summary": "钴行情，适用于锂电池和部分磁性材料。",
    },
    "src-shfe": {
        "sourceName": "SHFE 上海期货交易所",
        "sourceLevel": "S",
        "sourceType": "国内期货行情",
        "url": "https://www.shfe.com.cn/eng/",
        "summary": "国内铜、铝、镍、橡胶等期货行情，适合中国本地采购口径。",
    },
    "src-usgs": {
        "sourceName": "USGS Mineral Commodity Summaries",
        "sourceLevel": "S",
        "sourceType": "政府矿产统计",
        "url": "https://www.usgs.gov/centers/national-minerals-information-center/mineral-commodity-summaries",
        "summary": "关键矿产供需、关税、政府项目和五年统计。",
    },
    "src-semi": {
        "sourceName": "SEMI Market Data",
        "sourceLevel": "A",
        "sourceType": "行业协会数据",
        "url": "https://china.semi.org.cn/article/77",
        "summary": "晶圆厂、硅片、半导体材料、设备和封装市场数据。",
    },
    "src-sia": {
        "sourceName": "SIA Semiconductor Industry Association",
        "sourceLevel": "A",
        "sourceType": "行业协会数据",
        "url": "https://www.semiconductors.org/",
        "summary": "半导体供应链韧性、产能和政策信息。",
    },
    "src-ipc": {
        "sourceName": "IPC / Global Electronics Association",
        "sourceLevel": "A",
        "sourceType": "电子制造行业数据",
        "url": "https://www.ipc.org/",
        "summary": "电子制造、EMS、贸易政策和供应链可见性。",
    },
    "src-bis": {
        "sourceName": "BIS Bureau of Industry and Security",
        "sourceLevel": "S",
        "sourceType": "出口管制政策",
        "url": "https://www.bis.gov/",
        "summary": "出口管制、EAR、先进计算和半导体相关规则。",
    },
    "src-ustr": {
        "sourceName": "USTR Section 301",
        "sourceLevel": "S",
        "sourceType": "关税政策",
        "url": "https://ustr.gov/issue-areas/enforcement/section-301-investigations/tariff-actions",
        "summary": "Section 301 关税行动和排除流程。",
    },
    "src-trade-csl": {
        "sourceName": "Trade.gov Consolidated Screening List",
        "sourceLevel": "S",
        "sourceType": "合规筛查",
        "url": "https://www.trade.gov/data-visualization/csl-search",
        "summary": "受限实体、制裁和合规筛查。",
    },
    "src-digikey-api": {
        "sourceName": "DigiKey API",
        "sourceLevel": "A",
        "sourceType": "授权分销商库存/报价/PCN",
        "url": "https://developer.digikey.com/",
        "summary": "型号库存、报价、供应链库存和 PCN 查询。",
    },
}


def source_link(source_id: str) -> dict:
    source = SOURCE_LIBRARY[source_id]
    return {"id": source_id, **source}


CATEGORY_FILTERS = [
    {"key": "all", "label": "全部"},
    {"key": "semiconductor", "label": "IC/半导体"},
    {"key": "pcb", "label": "PCB/FPC"},
    {"key": "passive", "label": "被动件"},
    {"key": "connector_cable", "label": "连接器线缆"},
    {"key": "magnetic", "label": "磁性件"},
    {"key": "battery_power", "label": "电池电源"},
    {"key": "display_opto", "label": "显示光电"},
    {"key": "mechanical_thermal", "label": "结构散热"},
]

CATEGORY_CHAIN_TEMPLATES = [
    {
        "id": "chain-semiconductor-001",
        "group": "semiconductor",
        "category": "IC/半导体",
        "title": "IC → 晶圆制造 → 硅片/电子气体/光刻胶 → 封装材料",
        "summary": "IC 风险以晶圆产能、封装测试、出口管制和原厂 PCN/EOL 为主，材料侧关注硅片、电子气体、光刻胶、引线框和封装基板。",
        "sourceIds": ["src-semi", "src-sia", "src-bis", "src-digikey-api"],
        "nodes": [
            {"name": "IC/半导体", "materialType": "finished_category", "riskLevel": "orange", "evidence": "BOM 类别命中", "priceChangeText": "供需敏感", "confidenceScore": 88},
            {"name": "晶圆制造", "materialType": "manufacturing", "riskLevel": "orange", "evidence": "SEMI 晶圆厂与材料数据", "priceChangeText": "产能波动", "confidenceScore": 86},
            {"name": "硅片", "materialType": "upstream_material", "riskLevel": "yellow", "evidence": "SEMI 硅片监控", "priceChangeText": "观察", "confidenceScore": 82},
            {"name": "封装基板/引线框", "materialType": "intermediate", "riskLevel": "orange", "evidence": "封装材料供需", "priceChangeText": "交期波动", "confidenceScore": 80},
        ],
    },
    {
        "id": "chain-pcb-001",
        "group": "pcb",
        "category": "PCB/FPC",
        "title": "PCB/FPC → CCL/PI膜 → 铜箔/树脂/玻纤布",
        "summary": "PCB 成本主要通过覆铜板、铜箔、环氧树脂和玻纤布向下游传导，FPC 还需要关注 PI 膜与铜箔。",
        "sourceIds": ["src-lme-copper", "src-shfe", "src-ipc"],
        "nodes": [
            {"name": "PCB/FPC", "materialType": "finished_category", "riskLevel": "red", "evidence": "BOM 类别命中", "priceChangeText": "受影响", "confidenceScore": 90},
            {"name": "覆铜板 CCL", "materialType": "intermediate", "riskLevel": "red", "evidence": "行业成本结构", "priceChangeText": "成本上行", "confidenceScore": 86},
            {"name": "铜箔", "materialType": "upstream_material", "riskLevel": "red", "evidence": "LME/SHFE 铜价", "priceChangeText": "+8~12%", "confidenceScore": 88},
            {"name": "环氧树脂/玻纤布", "materialType": "upstream_material", "riskLevel": "orange", "evidence": "材料供应偏紧", "priceChangeText": "+3~9%", "confidenceScore": 76},
        ],
    },
    {
        "id": "chain-passive-mlcc-001",
        "group": "passive",
        "category": "MLCC/被动件",
        "title": "MLCC → 陶瓷介质/内电极 → 钛酸钡/镍粉/端头镀层",
        "summary": "MLCC 受镍粉、陶瓷粉体、车规高容产能和原厂配额影响；钽电容、电阻、电感分别关注钽、贵金属、铜和磁芯。",
        "sourceIds": ["src-lme-nickel", "src-lme-tin", "src-usgs", "src-digikey-api"],
        "nodes": [
            {"name": "MLCC/被动件", "materialType": "finished_category", "riskLevel": "orange", "evidence": "BOM 类别命中", "priceChangeText": "高容规格敏感", "confidenceScore": 86},
            {"name": "陶瓷粉体", "materialType": "upstream_material", "riskLevel": "yellow", "evidence": "材料供需", "priceChangeText": "观察", "confidenceScore": 72},
            {"name": "镍粉/镍内电极", "materialType": "upstream_material", "riskLevel": "orange", "evidence": "LME Nickel", "priceChangeText": "成本波动", "confidenceScore": 84},
            {"name": "钽/锡/贵金属", "materialType": "upstream_material", "riskLevel": "yellow", "evidence": "USGS/LME", "priceChangeText": "观察", "confidenceScore": 78},
        ],
    },
    {
        "id": "chain-connector-cable-001",
        "group": "connector_cable",
        "category": "连接器/线缆",
        "title": "连接器/线缆 → 端子/镀层/塑胶/导体 → 铜/锡/镍/工程塑料",
        "summary": "连接器和线缆对铜、锡、镍、工程塑料、关税和物流扰动敏感，价格传导通常较快。",
        "sourceIds": ["src-lme-copper", "src-lme-tin", "src-lme-nickel", "src-ustr", "src-digikey-api"],
        "nodes": [
            {"name": "连接器/线缆", "materialType": "finished_category", "riskLevel": "orange", "evidence": "BOM 类别命中", "priceChangeText": "受影响", "confidenceScore": 88},
            {"name": "铜合金端子/导体", "materialType": "intermediate", "riskLevel": "orange", "evidence": "LME Copper", "priceChangeText": "成本上行", "confidenceScore": 88},
            {"name": "锡/镍镀层", "materialType": "upstream_material", "riskLevel": "yellow", "evidence": "LME Tin/Nickel", "priceChangeText": "观察", "confidenceScore": 82},
            {"name": "工程塑料/橡胶", "materialType": "upstream_material", "riskLevel": "yellow", "evidence": "化工与供应商报价", "priceChangeText": "观察", "confidenceScore": 70},
        ],
    },
    {
        "id": "chain-magnetic-001",
        "group": "magnetic",
        "category": "磁性件/电机",
        "title": "磁性件/电机 → 磁芯/绕组/磁钢 → 铜/镍锌锰材料/稀土",
        "summary": "电感、变压器、电机主要受铜线、磁芯材料、稀土磁钢和能源限产影响。",
        "sourceIds": ["src-lme-copper", "src-lme-nickel", "src-usgs", "src-shfe"],
        "nodes": [
            {"name": "磁性件/电机", "materialType": "finished_category", "riskLevel": "yellow", "evidence": "BOM 类别命中", "priceChangeText": "观察", "confidenceScore": 82},
            {"name": "铜线绕组", "materialType": "intermediate", "riskLevel": "orange", "evidence": "LME Copper", "priceChangeText": "成本上行", "confidenceScore": 86},
            {"name": "磁芯/稀土磁钢", "materialType": "upstream_material", "riskLevel": "yellow", "evidence": "USGS 关键矿产", "priceChangeText": "供应观察", "confidenceScore": 78},
        ],
    },
    {
        "id": "chain-battery-power-001",
        "group": "battery_power",
        "category": "电池/电源",
        "title": "电池/电源 → 电芯/保护板/功率器件 → 锂/钴/镍/石墨/铜铝箔",
        "summary": "电池和电源模块同时受到关键矿产、功率半导体、运输限制和认证周期影响。",
        "sourceIds": ["src-lme-nickel", "src-lme-cobalt", "src-usgs", "src-semi", "src-digikey-api"],
        "nodes": [
            {"name": "电池/电源", "materialType": "finished_category", "riskLevel": "orange", "evidence": "BOM 类别命中", "priceChangeText": "受影响", "confidenceScore": 86},
            {"name": "锂/钴/镍/石墨", "materialType": "upstream_material", "riskLevel": "orange", "evidence": "USGS/LME", "priceChangeText": "矿产波动", "confidenceScore": 84},
            {"name": "MOSFET/电源IC", "materialType": "semiconductor", "riskLevel": "orange", "evidence": "SEMI/DigiKey", "priceChangeText": "交期波动", "confidenceScore": 80},
        ],
    },
    {
        "id": "chain-display-opto-001",
        "group": "display_opto",
        "category": "显示/光电",
        "title": "显示光电 → 面板/背光/LED/驱动IC → 玻璃/ITO/稀土/半导体材料",
        "summary": "显示模组和光电器件受面板产能、驱动 IC、稀有金属、区域灾害和原厂停产影响。",
        "sourceIds": ["src-semi", "src-sia", "src-usgs", "src-digikey-api"],
        "nodes": [
            {"name": "显示/光电", "materialType": "finished_category", "riskLevel": "yellow", "evidence": "BOM 类别命中", "priceChangeText": "观察", "confidenceScore": 80},
            {"name": "驱动IC/LED", "materialType": "semiconductor", "riskLevel": "orange", "evidence": "SEMI/SIA", "priceChangeText": "供需波动", "confidenceScore": 82},
            {"name": "ITO/稀土/玻璃基板", "materialType": "upstream_material", "riskLevel": "yellow", "evidence": "USGS", "priceChangeText": "观察", "confidenceScore": 76},
        ],
    },
    {
        "id": "chain-mechanical-thermal-001",
        "group": "mechanical_thermal",
        "category": "结构/散热",
        "title": "结构散热件 → 铝型材/压铸/热管/镀层 → 铝/铜/镍/工程塑料",
        "summary": "结构和散热件受铝、铜、镍、能源限产、模具产能和关税影响。",
        "sourceIds": ["src-lme-aluminium", "src-lme-copper", "src-lme-nickel", "src-shfe", "src-ustr"],
        "nodes": [
            {"name": "结构/散热", "materialType": "finished_category", "riskLevel": "yellow", "evidence": "BOM 类别命中", "priceChangeText": "观察", "confidenceScore": 80},
            {"name": "铝型材/压铸", "materialType": "intermediate", "riskLevel": "orange", "evidence": "LME Aluminium", "priceChangeText": "成本波动", "confidenceScore": 86},
            {"name": "铜热管/镀层", "materialType": "intermediate", "riskLevel": "yellow", "evidence": "LME Copper/Nickel", "priceChangeText": "观察", "confidenceScore": 80},
        ],
    },
]

MARKET_SIGNAL_TEMPLATES = [
    # ═══ 用户已确认的真实行情信号 ═══
    # MLCC — 1000%涨幅，加价买不到货
    {"id": "sig-mlcc-shortage-critical", "group": "passive", "title": "MLCC 涨价接近1000%，全品类严重缺货", "signalType": "shortage", "severity": "red", "sourceId": "src-digikey-api", "confidenceScore": 98, "occurredAt": "2026-07-07", "summary": "高容MLCC涨幅接近1000%，加价也买不到货。村田、TDK、三星电机、国巨全线控单，高容/小尺寸/车规规格严重短缺，AI服务器和汽车电子需求挤占产能。", "linkedMaterials": ["镍", "钛酸钡", "陶瓷粉体", "铜", "银钯"], "linkedCategories": ["MLCC/被动件"]},
    # PCB — 翻倍涨价
    {"id": "sig-pcb-doubled", "group": "pcb", "title": "PCB价格翻倍上涨，铜箔/覆铜板供应紧张", "signalType": "price", "severity": "red", "sourceId": "src-lme-copper", "confidenceScore": 96, "occurredAt": "2026-07-07", "summary": "PCB价格已翻倍，铜箔、覆铜板、玻纤布全链条涨价。铜价持续高位+PCB厂产能饱和+服务器/汽车订单挤占，多层板和高TG板交期大幅延长。", "linkedMaterials": ["铜", "铜箔", "覆铜板", "环氧树脂", "玻纤布"], "linkedCategories": ["PCB/FPC"]},
    # 功率器件 — 英飞凌/芯联集成涨价函
    {"id": "sig-power-increase-letter", "group": "semiconductor", "title": "英飞凌、芯联集成等功率器件厂商发涨价函", "signalType": "price", "severity": "red", "sourceId": "src-semi", "confidenceScore": 95, "occurredAt": "2026-07-07", "summary": "英飞凌IGBT/MOSFET、芯联集成SiC模块发涨价函，涨幅15-25%。新能源车/光伏/储能需求强劲，8寸/12寸晶圆产能紧张，封装测试排产饱和。", "linkedMaterials": ["硅片", "SiC衬底", "铜", "陶瓷基板", "银烧结"], "linkedCategories": ["IC/半导体", "电池/电源"]},
    # 分立器件 — 扬杰/长晶涨价函
    {"id": "sig-discrete-increase-letter", "group": "semiconductor", "title": "扬杰科技、长晶科技分立器件全面涨价", "signalType": "price", "severity": "red", "sourceId": "src-semi", "confidenceScore": 94, "occurredAt": "2026-07-07", "summary": "扬杰科技、长晶科技发涨价函，二极管/TVS/ESD/肖特基/三极管/MOSFET全品类涨价10-20%，2026年7月起生效。影响整流二极管、稳压管、保护器件等。", "linkedMaterials": ["硅片", "铜", "引线框架", "塑封料"], "linkedCategories": ["IC/半导体", "MLCC/被动件"]},
    # 薄膜电容 — 松下涨价
    {"id": "sig-film-cap-increase", "group": "passive", "title": "松下薄膜电容涨价，新能源逆变器需求拉动", "signalType": "price", "severity": "orange", "sourceId": "src-digikey-api", "confidenceScore": 90, "occurredAt": "2026-07-07", "summary": "松下薄膜电容（CBB/金属化聚丙烯）发涨价通知，新能源逆变器、车载OBC、工业电源需求旺盛，聚丙烯薄膜和喷金材料成本上行。", "linkedMaterials": ["聚丙烯薄膜", "锌", "铝", "环氧树脂"], "linkedCategories": ["MLCC/被动件"]},
    # 继电器 — 银触点涨价传导
    {"id": "sig-relay-increase", "group": "connector_cable", "title": "继电器全品类涨价，银触点成本大幅上升", "signalType": "price", "severity": "red", "sourceId": "src-lme-copper", "confidenceScore": 92, "occurredAt": "2026-07-07", "summary": "继电器受银价和铜价双重影响，宏发、欧姆龙、松下继电器均已调价。大功率继电器（30A以上）银触点暴露最高，银价上涨直接推高成本15-25%。", "linkedMaterials": ["银", "铜", "铁镍合金", "工程塑料"], "linkedCategories": ["连接器/线缆"]},
    # ═══ 原有行情信号（保留） ═══
    {"id": "sig-copper-cross-001", "group": "connector_cable", "title": "铜价高位运行影响连接器、线缆和磁性件", "signalType": "price", "severity": "orange", "sourceId": "src-lme-copper", "confidenceScore": 90, "occurredAt": "2026-07-07", "summary": "铜是连接器端子、线缆导体、PCB铜箔、电感绕组的共享上游，LME铜价持续高位，已传导至下游报价。", "linkedMaterials": ["铜", "铜合金端子", "铜线", "铜箔"], "linkedCategories": ["PCB/FPC", "连接器/线缆", "磁性件/电机"]},
    {"id": "sig-semi-capacity-001", "group": "semiconductor", "title": "8寸成熟制程产能持续紧张", "signalType": "shortage", "severity": "orange", "sourceId": "src-semi", "confidenceScore": 86, "occurredAt": "2026-07-07", "summary": "8寸成熟制程（BCD/模拟/功率器件）产能紧张，汽车和工业MCU/电源IC/驱动IC交期12-26周。", "linkedMaterials": ["硅片", "封装基板", "电子气体"], "linkedCategories": ["IC/半导体", "电池/电源"]},
]

BOM_IMPACT_TEMPLATES = [
    # ═══ 用户已确认的真实风险案例 ═══
    {"id": "impact-mlcc-critical", "group": "passive", "bomProjectName": "全项目 MLCC", "itemCode": "MLCC-HIGH-CAP-ALL", "itemName": "高容MLCC（全规格）", "category": "MLCC/被动件", "riskLevel": "red", "priceImpactText": "涨幅接近1000%", "leadTimeImpactText": "加价也买不到", "reasonSummary": "村田/TDK/三星电机/国巨全线控单，AI服务器+汽车电子需求挤占产能，高容/小尺寸/车规规格严重短缺。", "linkedSignalIds": ["sig-mlcc-shortage-critical"], "linkedMaterials": ["镍", "钛酸钡", "陶瓷粉体", "铜", "银钯"], "suggestedStrategyIds": ["act-passive-second-source-001", "act-lock-pcb-001"], "impactBreakdown": {"materialCost": "极高", "supply": "极高", "policy": "低", "substitution": "高"}},
    {"id": "impact-pcb-doubled", "group": "pcb", "bomProjectName": "全项目 PCB", "itemCode": "PCB-ALL-LAYERS", "itemName": "PCB/线路板（全层数）", "category": "PCB/FPC", "riskLevel": "red", "priceImpactText": "价格已翻倍", "leadTimeImpactText": "交期大幅延长", "reasonSummary": "铜箔/覆铜板/玻纤布全链条涨价，PCB厂产能饱和，服务器/汽车订单挤占产能，多层板和高TG板交期翻倍。", "linkedSignalIds": ["sig-pcb-doubled", "sig-copper-cross-001"], "linkedMaterials": ["铜", "铜箔", "覆铜板", "环氧树脂", "玻纤布"], "suggestedStrategyIds": ["act-lock-pcb-001"], "impactBreakdown": {"materialCost": "极高", "supply": "高", "policy": "低", "substitution": "中"}},
    {"id": "impact-power-increase", "group": "semiconductor", "bomProjectName": "全项目功率器件", "itemCode": "POWER-IGBT-MOSFET", "itemName": "IGBT/MOSFET/SiC功率器件", "category": "IC/半导体", "riskLevel": "red", "priceImpactText": "涨价15-25%", "leadTimeImpactText": "交期12-26周", "reasonSummary": "英飞凌、芯联集成发涨价函，新能源车/光伏/储能需求强劲拉动，8寸/12寸晶圆产能+封测排产紧张。", "linkedSignalIds": ["sig-power-increase-letter", "sig-semi-capacity-001"], "linkedMaterials": ["硅片", "SiC衬底", "铜", "陶瓷基板"], "suggestedStrategyIds": ["act-semi-alt-001"], "impactBreakdown": {"materialCost": "中", "supply": "极高", "policy": "中", "substitution": "高"}},
    {"id": "impact-discrete-increase", "group": "semiconductor", "bomProjectName": "全项目分立器件", "itemCode": "DISCRETE-DIODE-TVS", "itemName": "二极管/TVS/ESD/三极管", "category": "IC/半导体", "riskLevel": "red", "priceImpactText": "涨价10-20%", "leadTimeImpactText": "2026年7月起生效", "reasonSummary": "扬杰科技、长晶科技发涨价函，全品类分立器件（整流二极管/肖特基/TVS/ESD/稳压管/三极管）涨价，7月起执行。", "linkedSignalIds": ["sig-discrete-increase-letter"], "linkedMaterials": ["硅片", "铜", "引线框架", "塑封料"], "suggestedStrategyIds": ["act-semi-alt-001"], "impactBreakdown": {"materialCost": "中", "supply": "中", "policy": "低", "substitution": "高"}},
    {"id": "impact-film-cap-increase", "group": "passive", "bomProjectName": "全项目薄膜电容", "itemCode": "CAP-FILM-CBB", "itemName": "薄膜电容/安规电容", "category": "MLCC/被动件", "riskLevel": "orange", "priceImpactText": "松下发涨价通知", "leadTimeImpactText": "预计 +2-4周", "reasonSummary": "松下薄膜电容涨价，新能源逆变器+车载OBC+工业电源需求旺盛，聚丙烯薄膜和喷金材料成本上行。", "linkedSignalIds": ["sig-film-cap-increase"], "linkedMaterials": ["聚丙烯薄膜", "锌", "铝", "环氧树脂"], "suggestedStrategyIds": ["act-passive-second-source-001"], "impactBreakdown": {"materialCost": "中", "supply": "中", "policy": "低", "substitution": "中"}},
    {"id": "impact-relay-increase", "group": "connector_cable", "bomProjectName": "全项目继电器", "itemCode": "RELAY-POWER-30A", "itemName": "功率继电器（30A以上）", "category": "连接器/线缆", "riskLevel": "red", "priceImpactText": "银触点成本推高15-25%", "leadTimeImpactText": "预计 +2-4周", "reasonSummary": "银价上涨+铜价高位，宏发/欧姆龙/松下继电器已调价。大功率继电器银触点暴露最高，需紧急锁价。", "linkedSignalIds": ["sig-relay-increase", "sig-copper-cross-001"], "linkedMaterials": ["银", "铜", "铁镍合金"], "suggestedStrategyIds": ["act-lock-pcb-001"], "impactBreakdown": {"materialCost": "高", "supply": "中", "policy": "低", "substitution": "中"}},
    # ═══ 原有模板（保留） ═══
    {"id": "impact-mcu-001", "group": "semiconductor", "bomProjectName": "示例控制器 BOM", "itemCode": "MCU-STM32-ALT-001", "itemName": "32位主控 MCU", "category": "IC/半导体", "riskLevel": "orange", "priceImpactText": "预计 +3~8%", "leadTimeImpactText": "预计 +2~6 周", "reasonSummary": "晶圆产能、封装材料和出口管制共同影响 MCU 交期。", "linkedSignalIds": ["sig-semi-capacity-001"], "linkedMaterials": ["硅片", "封装基板", "电子气体"], "suggestedStrategyIds": ["act-semi-alt-001"], "impactBreakdown": {"materialCost": "低到中", "supply": "高", "policy": "中", "substitution": "高"}},
    {"id": "impact-conn-001", "group": "connector_cable", "bomProjectName": "示例整机 BOM", "itemCode": "CONN-USB-C-009", "itemName": "USB-C 连接器", "category": "连接器/线缆", "riskLevel": "orange", "priceImpactText": "预计 +5~9%", "leadTimeImpactText": "预计 +1~3 周", "reasonSummary": "铜合金端子、镀锡镀镍与关税风险共同影响连接器采购。", "linkedSignalIds": ["sig-copper-cross-001", "sig-tariff-connector-001"], "linkedMaterials": ["铜合金端子", "锡", "镍", "工程塑料"], "suggestedStrategyIds": ["act-connector-dual-source-001"], "impactBreakdown": {"materialCost": "高", "supply": "中", "policy": "中", "substitution": "中"}},
    {"id": "impact-battery-001", "group": "battery_power", "bomProjectName": "示例便携设备 BOM", "itemCode": "BAT-LI-18650-PACK", "itemName": "锂电池包", "category": "电池/电源", "riskLevel": "orange", "priceImpactText": "预计 +6~12%", "leadTimeImpactText": "预计 +2~5 周", "reasonSummary": "钴、镍、石墨和功率保护器件共同影响电池包报价与交付。", "linkedSignalIds": ["sig-battery-minerals-001"], "linkedMaterials": ["钴", "镍", "石墨", "MOSFET"], "suggestedStrategyIds": ["act-battery-buffer-001"], "impactBreakdown": {"materialCost": "高", "supply": "中", "policy": "中", "substitution": "高"}},
]

ACTION_STRATEGY_TEMPLATES = [
    {"id": "act-semi-alt-001", "group": "semiconductor", "strategyType": "alternative", "priority": "P0", "title": "启动关键 IC 替代料认证", "detail": "对 MCU、模拟芯片和功率器件优先建立二供清单，并复核封装、软件兼容和认证周期。", "ownerRole": "研发", "triggerReason": "半导体产能和政策信号命中。", "expectedEffect": "降低单一型号断供风险。"},
    {"id": "act-lock-pcb-001", "group": "pcb", "strategyType": "price", "priority": "P0", "title": "锁定关键 PCB 价格和产能", "detail": "对 HDI、多层板和高频高速板锁定 4~8 周需求，并复核铜箔/CCL 调价窗口。", "ownerRole": "采购", "triggerReason": "铜箔和 CCL 成本上行。", "expectedEffect": "降低短期涨价暴露。"},
    {"id": "act-passive-second-source-001", "group": "passive", "strategyType": "alternative", "priority": "P1", "title": "建立被动件规格替代池", "detail": "针对高容 MLCC、钽电容和功率电感建立可替代封装、电压、容差和品牌清单。", "ownerRole": "研发", "triggerReason": "被动件材料与产能信号命中。", "expectedEffect": "缩短缺货时工程确认时间。"},
    {"id": "act-connector-dual-source-001", "group": "connector_cable", "strategyType": "trade", "priority": "P1", "title": "复核连接器线缆关税和二供", "detail": "按原产地和 HTS 编码复核关税影响，同时确认 TE/Molex/Amphenol/国产二供替代可行性。", "ownerRole": "供应链", "triggerReason": "铜价和关税风险共同命中。", "expectedEffect": "避免报价漏算和交期被动。"},
    {"id": "act-battery-buffer-001", "group": "battery_power", "strategyType": "lead_time", "priority": "P1", "title": "增加电池电源安全库存", "detail": "对电池包、电源模块和关键 MOSFET 设置安全库存阈值，并同步运输认证周期。", "ownerRole": "项目经理", "triggerReason": "关键矿产和功率器件信号命中。", "expectedEffect": "降低交付延期概率。"},
    {"id": "act-watch-shared-materials-001", "group": "all", "strategyType": "watch", "priority": "P2", "title": "持续监控共享上游材料", "detail": "持续监控铜、镍、锡、铝、钴、钽、石墨等共享材料，并按影响类别自动提示 BOM 风险。", "ownerRole": "供应链", "triggerReason": "多类别共享材料暴露。", "expectedEffect": "提前识别跨品类连锁风险。"},
]
