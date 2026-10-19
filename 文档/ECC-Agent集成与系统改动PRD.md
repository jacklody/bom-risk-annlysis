# 系统改动 PRD：集成 electronic-component-cycle 行情周期智能体

> 版本：v2.1（与调研报告 v1.1 第七章 ECC Agent 衔接对齐）
> 日期：2026-07-25
> 状态：待评审
> 依赖文档：
> - [多维度风险驱动框架调研报告.md](./多维度风险驱动框架调研报告.md)（第七章 ECC Agent 详解）
> - [risk-authenticity-gate-redesign.md](./.trae/documents/risk-authenticity-gate-redesign.md)
> - 外部仓库：https://github.com/jacklody/electronic-component-cycle.git
> - 本地路径：`C:\Users\27017\.doubao\chats\2026-07-24\new-chat\electronic-component-cycle`

---

## 一、背景与目标

### 1.1 业务痛点

用户最担心的三件事（详见调研报告第一章与第七章）：

1. **行情解读能力弱**：系统能采集事件，但缺乏对事件真实性的深度解读。无法判断"这次涨价是真趋势还是炒作"、"这次缺货是产能问题还是中间商囤货"。
2. **历史经验缺失**：没有沉淀历史行情案例的机制。每次新事件都从零判断，无法参考"2017年MLCC涨价是怎么演化的"、"2021年MCU缺芯潮持续了多久"。
3. **决策支持不足**：风险预警只输出等级，无法回答业务最关心的问题——"要不要备货？备多少？备多久？"、"研发选型时应该避开哪些料？"。

### 1.2 解决方案

引入独立的 `electronic-component-cycle` 智能体（以下简称 ECC Agent）作为行情解读和历史经验沉淀的核心引擎。

**与多维度风险框架的关系**（详见调研报告 7.7 节）：
- **多维度风险框架**：提供风险维度的结构化分类（十大维度 + 四层产业链 + 品类权重矩阵）
- **ECC Agent**：提供行情解读的智能引擎（RCA 根因 + 时序校验 + A/B/C 分级 + 自学习知识图谱）

两者协同：ECC Agent 的 9 种周期类型覆盖多维度框架的核心场景，且通过自动 RCA 根因分析实现多维度的自动归类。

**ECC Agent 核心能力**（已实现，基于 2016-2026 三轮大周期深度复盘）：

| 能力 | 说明 |
|---|---|
| 自动根因分析（RCA） | 自动区分根因/催化剂/放大器，自动排除8种市场噪音 |
| 时序因果校验 | 强制"原因早于结果"，杜绝马后炮式因果倒置 |
| A/B/C 三级可信度 | 官方数据/媒体报道/市场传言自动分级 |
| 三级预警机制 | 红/橙/绿三级，明确告诉业务什么时候该备货/去库存/观望 |
| 自学习经验库 | 每分析一个事件，知识图谱自动增长，判断越来越准 |
| 28大类品类覆盖 | 被动元件/存储/芯片/显示/制造全品类 |
| 9种周期类型 | 涨跌双向：供给收缩/供需错配/成本推动/需求革命/政策驱动/产能过剩/需求疲软/价格战/需求冲击 |
| 18条预警规则 | 8条红色+4条橙色+6条绿色，历史验证 |

### 1.3 集成目标

| 目标 | 衡量指标 |
|---|---|
| 风险真实性验证准确率提升 | 从当前 60% 提升至 90%+ |
| EOL 准确率 | 99%+ |
| 误报率下降 | 从 30% 降至 <5% |
| 历史经验沉淀 | 每月新增 20+ 案例到知识图谱 |
| 备货决策支持 | 每条红色预警附备货建议（数量/周期） |
| 研发选型支持 | 输出"避坑清单"和"推荐清单" |

---

## 二、ECC Agent 功能详解

### 2.1 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│  事件发现层  按年+品类自动搜索，自动去重已入库事件           │
├─────────────────────────────────────────────────────────────┤
│  信息收集层  对接通用搜索/金融数据/行业网站，多源交叉验证     │
├─────────────────────────────────────────────────────────────┤
│  智能分析层  自动信息分级 + 自动RCA根因分析 + 自动生成预警    │
├─────────────────────────────────────────────────────────────┤
│  自动校验层  时序因果校验 + 字段完整性校验 + 噪音自动排除     │
├─────────────────────────────────────────────────────────────┤
│  经验库层    Graphiti时序知识图谱，自动追加事件/案例/因果     │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 核心 API

**一键分析新事件**（最常用入口）：

```python
from scripts.auto_cycle_pipeline import AutoCyclePipeline

pipeline = AutoCyclePipeline("graphiti/cycle_knowledge_graph.json")

result = pipeline.auto_analyze_new_event(
    event_description="2026Q3 TI宣布全系列模拟芯片涨价15%",
    category="模拟芯片",
    source="TI官方公告"
)

# 输出
result["warning_level"]       # 🔴红色涨价预警
result["action_suggestion"]   # 建议逐步建安全库存，预计持续2-4季度
result["cause_analysis"]      # 根因/催化剂/放大器/噪音排除
result["cycle_type"]          # 供给收缩型上涨
result["event_id"]            # EVT025（已自动入库）
result["case_id"]             # CASE006（已沉淀为标杆案例）
```

**核心数据结构**：

```python
@dataclass
class CycleEvent:
    event_id: str
    time: str              # YYYYQn 格式
    category: str          # 品类
    event_type: str
    subject: str
    description: str
    confidence: str        # A/B/C 三级
    price_impact: float    # 正数上涨，负数下跌
    duration_impact: int   # 影响持续月数

class Confidence(Enum):
    A = "A - 事后证实事实"     # 官方/财报/反垄断/事后复盘
    B = "B - 同期市场传闻"     # 媒体/供应链/代理商
    C = "C - 无法确认信息"     # 自媒体/股吧/传言
```

### 2.3 已覆盖能力

**28 大类电子元器件**：
- 被动元件：MLCC、片阻、钽电容、铝电解、薄膜电容、电感、磁珠
- 存储芯片：DRAM、NAND、NOR、HBM、通用存储
- 芯片：MCU、车规MCU、模拟、电源IC、MOSFET、IGBT、功率、射频、FPGA、传感器、驱动IC
- 显示：LCD面板、OLED面板
- 制造/其他：PCB、晶圆代工、封测、连接器、继电器、晶振

**9 种周期类型**（涨跌双向）：
- 📈 上涨：供给收缩型、供需错配+黑天鹅型、成本推动型、需求革命型、政策驱动型
- 📉 下跌：产能过剩型、需求疲软型、价格战型、需求冲击型

**18 条预警规则**：
- 🔴 红色预警（8条）：大级别行情信号，建议行动
- 🟠 橙色预警（4条）：高峰提醒，不要追高
- 🟢 绿色预警（6条）：拐点信号，反向操作

**8 种噪音自动排除**：
游资炒作 / 永远涨价 / 卡脖子 / 缺货3-5年 / 超级周期 / 外国控产 / 国家收储 / 销售话术

### 2.4 标杆案例库

| 案例 | 周期类型 | 最大涨幅 | 核心教训 |
|---|---|---|---|
| 2016-2018 LCD面板涨价 | 供给收缩型 | +105% | 逆周期扩产是周期终结者 |
| 2020-2022 MCU/缺芯潮 | 供需错配+黑天鹅 | +900% | 黑天鹅只放大周期，不创造周期 |
| 2021 被动元件涨价 | 成本推动型 | +100% | 成本推动型涨幅小、周期短 |
| 2025-至今 AI/HBM涨价 | 需求革命型 | +200% | 结构性行情，不会全品类普涨 |

---

## 三、集成方案设计

### 3.1 总体架构

```
┌───────────────────────────────────────────────────────────────────┐
│                     BOM 交期风险排查系统                            │
│                                                                   │
│  ┌──────────┐    ┌──────────────┐    ┌────────────────────────┐   │
│  │ 事件采集  │───▶│ 事件级门禁    │───▶│ ECC Agent 验证         │   │
│  │ (自动/手动)│    │ (基础过滤)    │    │ (RCA+时序+A/B/C分级)   │   │
│  └──────────┘    └──────────────┘    └───────────┬────────────┘   │
│                                                  │                │
│                                       ┌──────────▼──────────┐     │
│                                       │ 三态裁决             │     │
│                                       │ authentic/存疑/误报  │     │
│                                       └──────────┬──────────┘     │
│                                                  │                │
│                          ┌───────────────────────┼──────────┐    │
│                          ▼                       ▼          ▼    │
│                   ┌──────────────┐    ┌──────────────┐  ┌─────┐ │
│                   │ BOM 匹配      │    │ 知识图谱反哺  │  │误报 │ │
│                   │ (仅 verified) │    │ (事件喂回ECC) │  │案例库│ │
│                   └──────┬───────┘    └──────┬───────┘  └─────┘ │
│                          │                   │                   │
│                          ▼                   ▼                   │
│                   ┌──────────────────────────────┐               │
│                   │  决策支持引擎                  │               │
│                   │  - 备货建议（数量/周期）       │               │
│                   │  - 研发选型避坑清单            │               │
│                   │  - 历史相似案例参考            │               │
│                   └──────────────────────────────┘               │
└───────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │
                    ┌───────────────┴───────────────┐
                    │   ECC Agent (独立运行)          │
                    │   - graphiti/cycle_knowledge_  │
                    │     graph.json (经验库)        │
                    │   - auto_cycle_pipeline.py     │
                    │   - cycle_analyzer.py          │
                    │   - 自我迭代进化               │
                    └───────────────────────────────┘
```

### 3.2 集成层次

集成分为四个层次，由浅入深：

#### Layer 1：事件级验证（被动调用）

**触发时机**：事件入库前，由事件级门禁调用 ECC Agent 验证事件真实性。

```python
# event_authenticity_gate.py
from electronic_component_cycle.scripts.auto_cycle_pipeline import AutoCyclePipeline

class EventAuthenticityGate:
    def __init__(self):
        self.ecc_pipeline = AutoCyclePipeline(
            "electronic-component-cycle/graphiti/cycle_knowledge_graph.json"
        )

    async def verify_event(self, event: MarketEvent) -> VerificationResult:
        """事件级门禁：调用 ECC Agent 验证事件真实性"""
        ecc_result = self.ecc_pipeline.auto_analyze_new_event(
            event_description=event.raw_text,
            category=event.category or "unknown",
            source=event.source_name or "auto_collect"
        )

        # ECC 的 A/B/C 分级 → 系统的三态裁决
        confidence = ecc_result["cause_analysis"]
        if ecc_result.get("case_id"):  # 信息完整，已入库为标杆案例
            return VerificationResult(status="authentic", ...)
        elif confidence["confidence"] == "A":
            return VerificationResult(status="authentic", ...)
        elif confidence["confidence"] == "B":
            return VerificationResult(status="pending_validation", ...)
        else:  # C 级
            return VerificationResult(status="rejected", ...)
```

#### Layer 2：知识图谱反哺（主动喂回）

**触发时机**：每次 BOM 分析完成后，将本次行情事件喂回 ECC Agent，让其自我迭代进化。

```python
# risk_analysis.py analyze_bom 末尾
async def _feed_back_to_ecc_agent(events: list[MarketEvent], item: BomItem):
    """将本次行情事件喂回 ECC Agent，知识图谱自我迭代"""
    pipeline = get_ecc_pipeline()
    for event in events:
        pipeline.auto_analyze_new_event(
            event_description=event.raw_text,
            category=item.category or "unknown",
            source=event.source_name or "bom_analysis_feedback"
        )
```

#### Layer 3：备货决策支持

**触发时机**：风险等级为 RED/ORANGE 时，调用 ECC Agent 生成备货建议。

```python
# decision_support_service.py
class DecisionSupportService:
    def __init__(self):
        self.ecc_pipeline = get_ecc_pipeline()

    def generate_stocking_advice(
        self, item: BomItem, risk_level: RiskLevel, events: list
    ) -> StockingAdvice:
        """生成备货建议"""
        # 调用 ECC 的预警模板
        ecc_result = self.ecc_pipeline.auto_analyze_new_event(
            event_description=self._build_event_text(events, item),
            category=item.category,
            source="bom_risk_system"
        )

        warning_templates = ecc_result.get("warning_template", [])
        cycle_type = ecc_result.get("cycle_type", "")

        # 基于周期类型和历史案例生成备货建议
        return StockingAdvice(
            action="stock_up",  # stock_up / hold / destock
            quantity_weeks=self._calc_stocking_weeks(cycle_type, warning_templates),
            duration_months=self._estimate_duration(cycle_type),
            reason=ecc_result.get("cause_analysis", {}),
            historical_reference=self._find_similar_cases(item.category, cycle_type),
        )
```

#### Layer 4：研发选型支持

**触发时机**：研发新项目选型时，查询 ECC Agent 的历史经验库，输出避坑清单和推荐清单。

```python
# selection_advisor.py
class SelectionAdvisor:
    def __init__(self):
        self.analyzer = ComponentCycleAnalyzer(
            "electronic-component-cycle/graphiti/cycle_knowledge_graph.json"
        )

    def advise_component_selection(
        self, category: str, brand: str = "", mpn: str = ""
    ) -> SelectionAdvice:
        """研发选型建议"""
        # 查询历史案例
        similar_cases = self.analyzer.find_similar_cases(
            category=category, brand=brand
        )

        # 查询当前周期位置
        cycle_position = self.analyzer.detect_cycle_position(category)

        return SelectionAdvice(
            risk_level=self._assess_selection_risk(cycle_position, similar_cases),
            avoid_list=self._build_avoid_list(similar_cases),  # 高风险型号
            recommend_list=self._build_recommend_list(category),  # 稳定型号
            cycle_advice=self._cycle_advice(cycle_position),  # 当前周期建议
            historical_cases=similar_cases[:5],  # 最近5个相似案例
        )
```

### 3.3 ECC Agent 部署方式

**方案：本地部署 + Git 同步**

```
交期风险排查/
├── production-v1/
│   └── backend/
│       └── app/
│           ├── services/
│           │   ├── ecc_agent_client.py        # 新增：ECC Agent 客户端
│           │   ├── decision_support_service.py # 新增：决策支持服务
│           │   └── selection_advisor.py        # 新增：选型顾问服务
│           └── ...
├── electronic-component-cycle/                # 新增：ECC Agent（子模块或本地副本）
│   ├── graphiti/
│   │   └── cycle_knowledge_graph.json         # 经验库（自迭代进化）
│   ├── scripts/
│   │   ├── auto_cycle_pipeline.py
│   │   └── cycle_analyzer.py
│   └── config.json
└── ...
```

**部署选项**：

| 方案 | 优点 | 缺点 | 适用场景 |
|---|---|---|---|
| A. Git submodule | 代码独立维护，ECC 可独立升级 | 跨仓库依赖管理复杂 | ECC 持续独立迭代 |
| B. 本地副本 | 部署简单，无跨仓库依赖 | 需手动同步更新 | 初期快速集成（推荐） |
| C. HTTP API | 完全解耦，ECC 独立部署 | 需要部署 ECC 服务，网络延迟 | 后期微服务化 |

**推荐方案 B**：初期以本地副本方式集成，ECC 知识图谱作为共享数据资产。后期可升级为方案 C（HTTP API）。

---

## 四、新增模块设计

### 4.1 ECC Agent 客户端（ecc_agent_client.py）

```python
"""
ECC Agent 客户端 — 封装对 electronic-component-cycle 的调用
"""
from __future__ import annotations
import sys
import os
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass

# 将 ECC Agent 路径加入 sys.path
ECC_AGENT_PATH = Path(__file__).parent.parent.parent.parent / "electronic-component-cycle"
sys.path.insert(0, str(ECC_AGENT_PATH / "scripts"))

from auto_cycle_pipeline import AutoCyclePipeline, InformationGrader, RCAAnalyzer
from cycle_analyzer import ComponentCycleAnalyzer, Confidence, CycleEvent


@dataclass
class ECCVerificationResult:
    """ECC Agent 验证结果"""
    is_authentic: bool
    confidence_level: str           # A/B/C
    cycle_type: str                 # 周期类型
    root_cause: list[str]           # 根因
    catalysts: list[str]            # 催化剂
    amplifiers: list[str]           # 放大器
    false_narratives: list[str]     # 排除的噪音
    warning_level: str              # 🔴/🟠/🟢
    warning_templates: list[dict]   # 预警规则
    event_id: str                   # ECC 事件ID
    case_id: Optional[str]          # 标杆案例ID（如有）
    price_impact: Optional[float]   # 预估价格影响
    duration_months: Optional[int]  # 预估持续月数


class ECCAgentClient:
    """ECC Agent 客户端单例"""

    _instance: Optional["ECCAgentClient"] = None
    _pipeline: Optional[AutoCyclePipeline] = None
    _analyzer: Optional[ComponentCycleAnalyzer] = None

    def __new__(cls) -> "ECCAgentClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._pipeline is None:
            kg_path = str(ECC_AGENT_PATH / "graphiti" / "cycle_knowledge_graph.json")
            self._pipeline = AutoCyclePipeline(kg_path)
            self._analyzer = ComponentCycleAnalyzer(kg_path)

    def verify_event(
        self,
        event_description: str,
        category: str,
        source: str = "bom_risk_system",
    ) -> ECCVerificationResult:
        """验证单个事件的真实性"""
        result = self._pipeline.auto_analyze_new_event(
            event_description=event_description,
            category=category,
            source=source,
        )

        cause = result.get("cause_analysis", {})
        confidence = self._extract_confidence(result)
        warning_templates = result.get("warning_template", [])

        return ECCVerificationResult(
            is_authentic=confidence == "A" or result.get("case_id") is not None,
            confidence_level=confidence,
            cycle_type=result.get("cycle_type", ""),
            root_cause=cause.get("root_cause", []),
            catalysts=cause.get("catalysts", []),
            amplifiers=cause.get("amplifiers", []),
            false_narratives=cause.get("false_narratives", []),
            warning_level=self._extract_warning_level(warning_templates),
            warning_templates=warning_templates,
            event_id=result.get("event_id", ""),
            case_id=result.get("case_id"),
            price_impact=self._extract_price_impact(result),
            duration_months=self._extract_duration(result),
        )

    def find_similar_cases(
        self, category: str, brand: str = "", top_n: int = 5
    ) -> list[dict]:
        """查找历史相似案例"""
        # 调用 analyzer 的案例匹配功能
        return self._analyzer.find_similar_cases(
            category=category, brand=brand, top_n=top_n
        )

    def detect_cycle_position(self, category: str) -> dict:
        """检测品类当前周期位置"""
        return self._analyzer.detect_cycle_phase(category)

    def _extract_confidence(self, result: dict) -> str:
        """从 ECC 结果中提取 A/B/C 置信度"""
        # ECC 自动对事件打 A/B/C 标签
        events = self._pipeline.updater.kg.get("events", [])
        if events:
            latest = events[-1]
            return latest.get("confidence", "B")
        return "B"

    def _extract_warning_level(self, templates: list) -> str:
        """从预警模板中提取预警级别"""
        if not templates:
            return "🟢绿色"
        for t in templates:
            level = t.get("level", "")
            if "红" in level:
                return "🔴红色"
            if "橙" in level:
                return "🟠橙色"
        return "🟢绿色"

    def _extract_price_impact(self, result: dict) -> Optional[float]:
        """提取预估价格影响"""
        # 从预警模板或价格数据中提取
        templates = result.get("warning_template", [])
        for t in templates:
            if "涨幅" in t.get("prediction", ""):
                # 解析涨幅百分比
                pass
        return None

    def _extract_duration(self, result: dict) -> Optional[int]:
        """提取预估持续月数"""
        cycle_type = result.get("cycle_type", "")
        duration_map = {
            "供给收缩型上涨": 12,    # 12-24个月
            "供需错配+黑天鹅型上涨": 18,  # 18-30个月
            "成本推动型上涨": 6,     # 6-12个月
            "需求革命型上涨": 24,    # 24-48个月
            "政策驱动型上涨": 9,     # 9-18个月
        }
        return duration_map.get(cycle_type)
```

### 4.2 决策支持服务（decision_support_service.py）

```python
"""
决策支持服务 — 基于 ECC Agent 输出生成备货/选型建议
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from app.services.ecc_agent_client import ECCAgentClient
from app.models.bom import BomItem, RiskLevel


@dataclass
class StockingAdvice:
    """备货建议"""
    action: str                          # stock_up / hold / destock
    quantity_weeks: int                   # 建议备货周数
    duration_months: int                  # 预计风险持续月数
    reason: dict                          # 决策依据
    historical_reference: list[dict]       # 历史相似案例
    urgency: str                          # immediate / short_term / mid_term


@dataclass
class SelectionAdvice:
    """研发选型建议"""
    risk_level: str                       # high / medium / low
    avoid_list: list[str]                 # 应避开的型号/品牌
    recommend_list: list[str]             # 推荐的稳定型号/品牌
    cycle_advice: str                     # 当前周期建议
    historical_cases: list[dict]          # 历史相似案例
    alternative_brands: list[str]         # 替代品牌


class DecisionSupportService:
    """决策支持服务"""

    def __init__(self):
        self.ecc = ECCAgentClient()

    def generate_stocking_advice(
        self,
        item: BomItem,
        risk_level: RiskLevel,
        events: list,
        ecc_result: Optional[dict] = None,
    ) -> StockingAdvice:
        """生成备货建议

        决策矩阵：
        - RED + 涨价周期 → 立即备货，覆盖预计持续期
        - RED + EOL → 立即 LTB 采购
        - ORANGE + 涨价周期 → 适度备货，覆盖50%持续期
        - YELLOW → 观望，保持安全库存
        - GREEN → 无需行动
        """
        cycle_type = ecc_result.get("cycle_type", "") if ecc_result else ""
        duration = self.ecc._extract_duration(ecc_result) if ecc_result else 6

        if risk_level == RiskLevel.RED:
            if "lifecycle" in str(events).lower() or "eol" in str(events).lower():
                return StockingAdvice(
                    action="stock_up",
                    quantity_weeks=52,  # EOL 备货一年
                    duration_months=duration,
                    reason={"type": "EOL", "action": "LTB采购"},
                    historical_reference=self.ecc.find_similar_cases(item.category or ""),
                    urgency="immediate",
                )
            return StockingAdvice(
                action="stock_up",
                quantity_weeks=min(duration * 4, 24),  # 覆盖预计持续期，最多24周
                duration_months=duration,
                reason={"type": cycle_type, "action": "逐步建安全库存"},
                historical_reference=self.ecc.find_similar_cases(item.category or ""),
                urgency="immediate",
            )
        elif risk_level == RiskLevel.ORANGE:
            return StockingAdvice(
                action="stock_up",
                quantity_weeks=min(duration * 2, 12),  # 覆盖50%持续期
                duration_months=duration,
                reason={"type": cycle_type, "action": "适度备货"},
                historical_reference=self.ecc.find_similar_cases(item.category or ""),
                urgency="short_term",
            )
        elif risk_level == RiskLevel.YELLOW:
            return StockingAdvice(
                action="hold",
                quantity_weeks=4,  # 保持安全库存
                duration_months=duration,
                reason={"type": "observe", "action": "观望，跟踪变化"},
                historical_reference=[],
                urgency="mid_term",
            )
        else:
            return StockingAdvice(
                action="hold",
                quantity_weeks=0,
                duration_months=0,
                reason={"type": "no_action", "action": "无需行动"},
                historical_reference=[],
                urgency="mid_term",
            )
```

### 4.3 选型顾问服务（selection_advisor.py）

```python
"""
选型顾问服务 — 研发新项目选型时的避坑与推荐
"""
from __future__ import annotations
from app.services.ecc_agent_client import ECCAgentClient


class SelectionAdvisor:
    """研发选型顾问"""

    # 品类 → 推荐品牌（基于历史稳定性）
    STABLE_BRANDS = {
        "mcu": ["ST", "NXP", "Renesas", "兆易创新"],
        "mlcc": ["村田", "三星", "国巨"],
        "aluminum_electrolytic_capacitor": ["尼吉康", "红宝石", "松下"],
        "connector": ["TE", "Molex", "Amphenol"],
        "relay": ["欧姆龙", "宏发", "松下"],
    }

    # 高风险信号品类（当前周期上行）
    HIGH_RISK_CATEGORIES = {"high_cap_mlcc", "mcu", "memory"}

    def __init__(self):
        self.ecc = ECCAgentClient()

    def advise_selection(
        self, category: str, brand: str = "", mpn: str = ""
    ) -> dict:
        """研发选型建议

        输出：
        - risk_level: 当前选择该品类的风险等级
        - avoid_list: 建议避开的型号/品牌（基于历史案例）
        - recommend_list: 推荐的稳定型号/品牌
        - cycle_advice: 当前周期位置和建议
        - historical_cases: 最近5个相似案例
        - alternative_brands: 替代品牌
        """
        # 查询历史案例
        similar_cases = self.ecc.find_similar_cases(category, brand, top_n=5)

        # 检测当前周期位置
        cycle_position = self.ecc.detect_cycle_position(category)

        # 评估风险
        risk_level = self._assess_risk(cycle_position, similar_cases)

        # 构建避坑清单
        avoid_list = self._build_avoid_list(similar_cases)

        # 构建推荐清单
        recommend_list = STABLE_BRANDS.get(category, [])

        return {
            "risk_level": risk_level,
            "avoid_list": avoid_list,
            "recommend_list": recommend_list,
            "cycle_advice": self._cycle_advice(cycle_position),
            "historical_cases": similar_cases,
            "alternative_brands": recommend_list,
        }

    def _assess_risk(self, cycle_position: dict, cases: list) -> str:
        """评估当前选型风险"""
        phase = cycle_position.get("phase", "")
        if phase in ("expansion", "peak"):
            return "high"
        if phase in ("early_contraction",):
            return "medium"
        return "low"

    def _build_avoid_list(self, cases: list) -> list[str]:
        """基于历史案例构建避坑清单"""
        avoid = []
        for case in cases:
            if case.get("false_narratives"):
                avoid.extend(case["false_narratives"])
        return list(set(avoid))

    def _cycle_advice(self, cycle_position: dict) -> str:
        """当前周期建议"""
        phase = cycle_position.get("phase", "unknown")
        advice_map = {
            "trough": "当前处于周期底部，是选型导入的好时机",
            "recovery": "周期正在恢复，可正常选型",
            "expansion": "周期上行中，建议优先选择有备货保障的供应商",
            "peak": "周期顶部，避免选择紧缺型号，优先 pin-to-pin 替代方案",
            "contraction": "周期下行，价格可能回落，可暂缓大批量采购",
        }
        return advice_map.get(phase, "周期位置不明，建议常规选型")
```

### 4.4 知识图谱反哺服务（ecc_feedback_service.py）

```python
"""
知识图谱反哺服务 — 将本次行情事件喂回 ECC Agent，自我迭代进化
"""
from __future__ import annotations
import logging
from app.services.ecc_agent_client import ECCAgentClient
from app.models.event import MarketEvent

logger = logging.getLogger(__name__)


class ECCFeedbackService:
    """将系统采集的行情事件反哺给 ECC Agent"""

    def __init__(self):
        self.ecc = ECCAgentClient()

    async def feed_events_to_ecc(
        self, events: list[MarketEvent], category: str = ""
    ) -> dict:
        """将事件批量喂回 ECC Agent

        每次喂入会：
        1. 自动去重（ECC 内置去重逻辑）
        2. 自动 RCA 分析
        3. 自动 A/B/C 分级
        4. 自动入库为标杆案例（信息完整时）
        5. 自动更新知识图谱版本
        """
        fed_count = 0
        for event in events:
            try:
                result = self.ecc.verify_event(
                    event_description=event.raw_text or event.raw_title or "",
                    category=event.category or category or "unknown",
                    source=event.source_name or "bom_risk_feedback",
                )
                if result.event_id:
                    fed_count += 1
                    logger.info(
                        f"ECC 反哺: 事件 {event.id} → ECC {result.event_id} "
                        f"[{result.confidence_level}级 / {result.cycle_type}]"
                    )
            except Exception as e:
                logger.warning(f"ECC 反哺失败 (事件 {event.id}): {e}")

        return {
            "fed_count": fed_count,
            "total": len(events),
            "kg_version": self.ecc._pipeline.updater.kg["metadata"]["version"],
        }
```

---

## 五、API 设计

### 5.1 新增 API 端点

```python
# app/api/decision_support.py
from fastapi import APIRouter, Depends
from app.services.decision_support_service import DecisionSupportService
from app.services.selection_advisor import SelectionAdvisor
from app.services.ecc_feedback_service import ECCFeedbackService

router = APIRouter(prefix="/api/v1/decision", tags=["决策支持"])


@router.get("/stocking-advice/{item_id}")
async def get_stocking_advice(item_id: int):
    """获取备货建议"""
    service = DecisionSupportService()
    return await service.get_stocking_advice_by_item(item_id)


@router.get("/selection-advice")
async def get_selection_advice(category: str, brand: str = "", mpn: str = ""):
    """获取研发选型建议"""
    advisor = SelectionAdvisor()
    return advisor.advise_selection(category, brand, mpn)


@router.post("/ecc/feedback")
async def feed_events_to_ecc(project_id: int = None, item_id: int = None):
    """将行情事件反哺给 ECC Agent"""
    service = ECCFeedbackService()
    return await service.feed_from_project_or_item(project_id, item_id)


@router.get("/ecc/cases")
async def get_historical_cases(category: str, top_n: int = 5):
    """查询历史相似案例"""
    ecc = ECCAgentClient()
    return ecc.find_similar_cases(category, top_n=top_n)


@router.get("/ecc/cycle-position")
async def get_cycle_position(category: str):
    """查询品类当前周期位置"""
    ecc = ECCAgentClient()
    return ecc.detect_cycle_position(category)
```

### 5.2 前端集成

**BOM 分析页新增**：
- 每条 RED/ORANGE 风险物料旁新增"备货建议"按钮
- 点击展示备货数量、周期、历史案例

**新增"研发选型顾问"页面**：
- 输入品类/品牌/型号
- 输出风险等级、避坑清单、推荐清单、周期建议、历史案例

**新增"行情周期看板"页面**：
- 展示各品类当前周期位置（底部/恢复/扩张/顶部/收缩）
- 展示 ECC 知识图谱统计（事件数/案例数/预警规则数）

---

## 六、数据流设计

### 6.1 事件验证数据流

```
事件采集
    ↓
事件级门禁 (event_authenticity_gate.py)
    ↓ 调用
ECC Agent 验证 (ecc_agent_client.py)
    ↓ 返回
ECCVerificationResult
    ├── A级 + 有标杆案例 → authentic (通过)
    ├── B级 → pending_validation (观察池)
    └── C级 → rejected (误报库)
```

### 6.2 知识图谱反哺数据流

```
BOM 分析完成
    ↓
提取本次匹配的行情事件
    ↓
feed_events_to_ecc (ecc_feedback_service.py)
    ↓
ECC Agent auto_analyze_new_event()
    ├── 自动去重（已入库的跳过）
    ├── 自动 RCA 分析
    ├── 自动 A/B/C 分级
    ├── 自动生成标杆案例
    └── 自动更新知识图谱版本
    ↓
返回反哺结果 (fed_count, kg_version)
```

### 6.3 备货决策数据流

```
BOM 物料风险等级 = RED/ORANGE
    ↓
DecisionSupportService.generate_stocking_advice()
    ├── 查询 ECC 周期类型
    ├── 估算风险持续月数
    ├── 查询历史相似案例
    └── 生成备货建议
    ↓
StockingAdvice
    ├── action: stock_up / hold / destock
    ├── quantity_weeks: 建议备货周数
    ├── duration_months: 预计风险持续月数
    ├── historical_reference: 历史案例参考
    └── urgency: immediate / short_term / mid_term
```

---

## 七、实施计划

### 7.1 分阶段实施

| 阶段 | 任务 | 依赖 |
|---|---|---|
| **Phase 1** | ECC Agent 本地部署 + 客户端封装 | 无 |
| **Phase 2** | 事件级验证集成（Layer 1） | Phase 1 + 事件级门禁 |
| **Phase 3** | 知识图谱反哺集成（Layer 2） | Phase 1 |
| **Phase 4** | 备货决策支持（Layer 3） | Phase 1 + BOM 分析 |
| **Phase 5** | 研发选型顾问（Layer 4） | Phase 1 |
| **Phase 6** | 前端页面集成 | Phase 3-5 |

### 7.2 文件变更清单

**新增文件（6 个）**：

| 文件路径 | 用途 |
|---|---|
| `backend/app/services/ecc_agent_client.py` | ECC Agent 客户端封装 |
| `backend/app/services/decision_support_service.py` | 备货决策支持服务 |
| `backend/app/services/selection_advisor.py` | 研发选型顾问服务 |
| `backend/app/services/ecc_feedback_service.py` | 知识图谱反哺服务 |
| `backend/app/api/decision_support.py` | 决策支持 API |
| `frontend/src/views/SelectionAdvisor.vue` | 选型顾问前端页面 |

**修改文件（5 个）**：

| 文件路径 | 改动要点 |
|---|---|
| `backend/app/services/event_authenticity_gate.py` | 集成 ECC Agent 验证 |
| `backend/app/api/risk_analysis.py` | BOM 分析末尾调用 ECC 反哺 |
| `backend/app/main.py` | 注册决策支持路由 |
| `frontend/src/views/BomAnalyze.vue` | 新增备货建议按钮 |
| `frontend/src/router/index.js` | 新增选型顾问路由 |

**ECC Agent 部署**：
- 将 `electronic-component-cycle` 仓库克隆到项目根目录
- `graphiti/cycle_knowledge_graph.json` 作为共享经验库
- 定期 Git 推送知识图谱更新到远程仓库

### 7.3 验证标准

| 验证项 | 标准 |
|---|---|
| ECC Agent 可调用 | `AutoCyclePipeline` 初始化成功，知识图谱可加载 |
| 事件验证准确率 | 对历史 100 个事件验证，准确率 ≥90% |
| 反哺去重 | 重复喂入同一事件，不会重复入库 |
| 备货建议可用 | 每条 RED 预警附备货建议，包含数量/周期/历史案例 |
| 选型建议覆盖 | 28 大类品类均可输出选型建议 |
| 知识图谱增长 | 每月新增 20+ 事件入库 |
| 性能 | ECC 验证单个事件 <2 秒 |

---

## 八、风险与应对

| 风险 | 影响 | 应对 |
|---|---|---|
| ECC Agent 知识图谱未初始化 | 验证能力弱 | 预置 2016-2026 四轮大周期标杆案例 |
| ECC 与系统品类映射不一致 | 验证遗漏 | 建立品类映射表（28类→20类） |
| ECC 调用延迟 | BOM 分析变慢 | 异步调用 + 结果缓存 |
| 知识图谱冲突 | 多源数据矛盾 | 以 A 级来源为准，B/C 级仅参考 |
| ECC 独立演进导致不兼容 | 接口变更 | 锁定 ECC 版本，定期同步升级 |

---

## 九、与多维度风险驱动框架的关系

本 PRD 是[多维度风险驱动框架调研报告](./多维度风险驱动框架调研报告.md)的落地实现之一：

| 调研报告维度 | 本 PRD 对应实现 |
|---|---|
| 维度1：材料成本 | ECC 成本推动型周期识别 |
| 维度2：能源电力 | ECC 政策驱动型周期识别 |
| 维度3：政策合规 | ECC 政策驱动型周期识别 |
| 维度4：行业需求 | ECC 需求革命型周期识别 |
| 维度5：产能供给 | ECC 供给收缩型周期识别 |
| 维度6：物流运输 | ECC 供需错配型周期识别 |
| 维度7：灾害事件 | ECC 供需错配+黑天鹅型识别 |
| 维度8：资本投机 | ECC 8种噪音自动排除 |
| 维度9：劳动力 | 归入产能供给维度 |
| 维度10：生命周期 | 系统原有 EOL 检测 + ECC 历史案例 |

ECC Agent 的 9 种周期类型覆盖了多维度框架的核心场景，且通过自动 RCA 根因分析实现了多维度的自动归类。

---

## 十、待决策点

1. **ECC 部署方式**：本地副本（推荐） vs Git submodule vs HTTP API？
2. **品类映射**：ECC 的 28 类与系统分类器的 20 类如何映射？（需建映射表）
3. **反哺频率**：每次 BOM 分析后立即反哺 vs 每日批量反哺？
4. **知识图谱所有权**：知识图谱作为独立 Git 仓库版本管理，还是与主项目同仓库？
5. **ECC 升级策略**：锁定版本 vs 定期同步 vs 自动跟踪最新？

---

**PRD 结束。等待评审与决策。**
