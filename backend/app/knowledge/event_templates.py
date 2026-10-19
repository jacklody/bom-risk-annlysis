"""
已知市场事件模板（用于快速匹配和辅助LLM推理）
"""

EVENT_TEMPLATES = [
    {
        "id": "T001",
        "name": "MLCC高容短缺",
        "keywords": ["MLCC", "高容", "缺货", "交期延长", "涨价", "多层陶瓷电容"],
        "affected_brands": ["村田/Murata", "三星电机/SEMCO", "国巨/Yageo", "太阳诱电/Taiyo"],
        "affected_categories": ["MLCC高容", "MLCC"],
        "typical_lead_time_impact": "8-20周",
        "typical_price_impact_pct": [10, 30],
        "historical_periods": ["2017-2018", "2026Q2"],
        "severity": "high",
    },
    {
        "id": "T002",
        "name": "ST MCU全线交期延长",
        "keywords": ["ST", "STM", "MCU", "交期", "紧缺", "分配", "缺货"],
        "affected_brands": ["意法半导体/ST"],
        "affected_categories": ["MCU/微控制器"],
        "typical_lead_time_impact": "20-52周",
        "historical_periods": ["2021-2022"],
        "severity": "critical",
    },
    {
        "id": "T003",
        "name": "存储芯片涨价周期",
        "keywords": ["存储", "DRAM", "NAND", "涨价", "供需失衡", "存储器"],
        "affected_brands": ["美光/Micron", "三星/Samsung", "SK海力士"],
        "affected_categories": ["DRAM", "NAND Flash", "存储芯片"],
        "typical_price_impact_pct": [15, 50],
        "severity": "high",
    },
    {
        "id": "T004",
        "name": "晶圆代工产能紧张",
        "keywords": ["晶圆", "产能", "代工", "制程", "台积电", "SMIC", "产能利用率"],
        "affected_brands": [],
        "affected_categories": ["半导体"],
        "typical_lead_time_impact": "4-26周",
        "severity": "high",
        "ripple_effect": True,
    },
    {
        "id": "T005",
        "name": "TI模拟芯片价格调整",
        "keywords": ["TI", "模拟", "电源", "价格", "调整"],
        "affected_brands": ["德州仪器/TI"],
        "affected_categories": ["电源管理IC", "模拟芯片"],
        "typical_price_impact_pct": [5, 15],
        "severity": "medium",
    },
    {
        "id": "T006",
        "name": "原厂EOL停产通知",
        "keywords": ["EOL", "停产", "Last Time Buy", "替代", "NRND", "不推荐"],
        "severity": "critical",
        "typical_lead_time_impact": "断供",
    },
]
