# EMS全链路风险预警系统开发实施计划

> **执行基准**：本计划以《EMS行业全链路风险预警系统调整建议.md》为源需求文档。开发过程中不允许脱离该文档随意新增方向；所有代码变更必须能映射到本计划中的需求编号、任务编号和验收标准。

## 目标

把现有 BOM 交期风险系统从“材料价格列表 + 风险链路示例”升级为“EMS行业全链路风险响应系统”。系统应能把行情、政策、灾害、库存、原厂生命周期、供应商和物流事件，传导到 EMS 产业链节点、上游材料、BOM元器件类别、具体BOM型号，并输出新项目选型评审结论和老项目交付风险结论。

## 架构原则

系统采用“规则引擎 + 行业知识图谱 + 数据源适配器 + LLM分析层 + 人工确认”的组合。价格、库存、灾害、政策等事实数据来自外部数据源和人工录入；LLM只负责非结构化内容解析、链路推理解释和建议生成，不直接生成事实价格，也不直接决定最终风险等级。

## 技术栈

- 后端：FastAPI、Pydantic、SQLAlchemy、SQLite默认数据库
- 前端：Vue 3、Element Plus、Vite
- 测试：pytest、Vitest
- 数据源适配：HTTP API、可配置API Key、降级为来源链接和人工确认
- LLM：现有 `app/services/llm_client.py` 扩展，支持 DeepSeek、网宿网关、现有 Anthropic 模式的统一封装

## 全局约束

1. 没有真实数据源时，不允许把风险显示为“正常”，必须显示“待确认/未接入/数据不足”。
2. SMM、Mysteel、DigiKey、Mouser、网宿网关、DeepSeek 等需要账号或API Key的数据源，先做适配器、配置位和未配置状态，不伪造实时取数。
3. LLM输出必须保留来源引用和置信度，最终风险等级由风险评分引擎计算。
4. 每个功能必须先有测试，再实现代码。
5. 每个阶段完成后必须跑对应后端测试、前端测试和前端构建。
6. 最终交付前必须重新生成服务器部署ZIP包。

---

## 一、需求追踪矩阵

| 需求编号 | 源文档要求 | 开发任务 | 验收标准 |
|---|---|---|---|
| R1 | 风险链路驾驶舱从静态展示变成“事件 → 链路 → BOM影响” | Task 1、Task 4、Task 7 | 首页展示风险信号流、EMS链路图谱、BOM影响和业务结论 |
| R2 | 建立EMS行业链路知识库 | Task 1 | 覆盖半导体、PCB、MLCC、电容、电阻、连接器、线束、继电器、磁性件、功率器件、散热、结构、电池、显示光电等类别 |
| R3 | 建立BOM元器件分类到上游材料映射 | Task 2 | BOM行可匹配到元器件类别、材料、制程、行情源 |
| R4 | 风险等级从价格单因子改为多因子 | Task 3 | 风险分包含行情、供应、政策、灾害、BOM暴露度、替代难度、置信度 |
| R5 | 数据不足显示灰色，不得显示正常 | Task 3、Task 6 | 无行情源或无基线时返回 `unknown` 并在前端显示“待确认” |
| R6 | 输出新项目BOM选型评审结论 | Task 5 | API和页面能输出“通过/有条件通过/不建议”及原因 |
| R7 | 输出老项目交付风险结论 | Task 5 | API和页面能输出未来4-8周交付风险、触发原因、建议动作 |
| R8 | 材料链路库改成元器件上游组成库 | Task 6 | 材料链路库按元器件类别展示材料、制程、行情源、命中BOM |
| R9 | 接入多源数据体系 | Task 8 | 数据源注册表包含SMM、Mysteel、LME、SHFE、BIS、USTR、Trade.gov、USGS、GDACS、NOAA、SEMI、IPC、DigiKey、Mouser、LCSC |
| R10 | 支持公众号/涨价函/PCN等半自动输入 | Task 9 | 支持文本粘贴/文件上传进入人工确认队列 |
| R11 | 引入LLM分析层 | Task 10 | 支持事件抽取、BOM分类辅助、链路推理、建议生成、报告摘要 |
| R12 | 风险运营闭环 | Task 11 | 风险有状态、负责人、动作、处理结果和解除记录 |
| R13 | 更新部署包 | Task 12 | 重新生成ZIP，包含修复后的前后端、文档和dist构建产物 |

---

## 二、目标文件结构

### 后端新增文件

```text
backend/app/knowledge/industry_chain_library.py
backend/app/knowledge/source_registry.py
backend/app/services/industry_chain/component_classifier.py
backend/app/services/industry_chain/material_decomposer.py
backend/app/services/industry_chain/bom_exposure_engine.py
backend/app/services/industry_chain/risk_scoring_engine.py
backend/app/services/industry_chain/event_normalizer.py
backend/app/services/industry_chain/recommendation_engine.py
backend/app/services/industry_chain/review_queue.py
backend/app/services/llm_analysis_service.py
backend/app/services/sources/market_source_registry.py
backend/app/services/sources/commodity/smm_source.py
backend/app/services/sources/commodity/mysteel_source.py
backend/app/services/sources/commodity/lme_source.py
backend/app/services/sources/commodity/shfe_source.py
backend/app/services/sources/policy/bis_source.py
backend/app/services/sources/policy/ustr_source.py
backend/app/services/sources/policy/trade_csl_source.py
backend/app/services/sources/disaster/usgs_source.py
backend/app/services/sources/disaster/gdacs_source.py
backend/app/services/sources/weather/noaa_source.py
backend/app/api/industry_chain.py
backend/app/api/llm_analysis.py
backend/tests/test_industry_chain_library.py
backend/tests/test_component_classifier.py
backend/tests/test_bom_exposure_engine.py
backend/tests/test_risk_scoring_engine.py
backend/tests/test_industry_chain_api.py
backend/tests/test_llm_analysis_service.py
backend/tests/test_source_registry.py
```

### 后端修改文件

```text
backend/app/api/risk_chain.py
backend/app/api/material_alerts.py
backend/app/api/bom_project.py
backend/app/main.py
backend/app/config.py
backend/app/services/llm_client.py
backend/app/knowledge/risk_chain_library.py
backend/app/knowledge/material_mapping.py
```

### 前端新增文件

```text
frontend/src/api/industryChain.js
frontend/src/api/llmAnalysis.js
frontend/src/components/risk-chain/RiskSignalStream.vue
frontend/src/components/risk-chain/IndustryChainGraph.vue
frontend/src/components/risk-chain/BomImpactPanel.vue
frontend/src/components/risk-chain/BusinessConclusionPanel.vue
frontend/src/components/materials/ComponentMaterialChain.vue
frontend/src/views/LlmAnalysis.vue
frontend/src/views/__tests__/IndustryChainGraph.test.js
frontend/src/views/__tests__/LlmAnalysis.test.js
```

### 前端修改文件

```text
frontend/src/views/RiskChainDashboard.vue
frontend/src/views/MaterialWatch.vue
frontend/src/views/BomAnalyze.vue
frontend/src/views/BomProjectDetail.vue
frontend/src/views/MarketEvents.vue
frontend/src/App.vue
frontend/src/router/index.js
frontend/src/api/riskChain.js
frontend/src/views/__tests__/RiskChainDashboard.test.js
frontend/src/views/__tests__/BomAnalyze.test.js
frontend/src/views/__tests__/MaterialWatch.test.js
```

---

## 三、数据对象设计

### RiskEvent

```python
class RiskEvent(BaseModel):
    id: str
    title: str
    event_type: Literal[
        "commodity_price", "shortage", "policy", "tariff", "export_control",
        "disaster", "weather", "logistics", "pcn", "eol", "supplier", "manual"
    ]
    severity: Literal["red", "orange", "yellow", "green", "unknown"]
    source_id: str
    source_level: Literal["S", "A", "B", "C"]
    occurred_at: str
    summary: str
    affected_material_ids: list[str]
    affected_component_categories: list[str]
    affected_regions: list[str]
    confidence_score: int
    raw_url: str | None = None
```

### IndustryNode

```python
class IndustryNode(BaseModel):
    id: str
    name: str
    node_type: Literal["macro", "policy", "region", "process", "material", "component", "bom_item", "project"]
    parent_ids: list[str] = []
    source_ids: list[str] = []
    risk_factors: list[str] = []
```

### ComponentMaterialProfile

```python
class ComponentMaterialProfile(BaseModel):
    category_id: str
    category_name: str
    aliases: list[str]
    upstream_materials: list[str]
    processes: list[str]
    source_ids: list[str]
    typical_risk_factors: list[str]
    substitution_difficulty: Literal["high", "medium", "low"]
```

### BomExposure

```python
class BomExposure(BaseModel):
    bom_item_id: str
    item_code: str
    item_name: str
    project_id: int | None
    project_name: str | None
    category_id: str
    matched_materials: list[str]
    matched_events: list[str]
    exposure_score: int
    exposure_reason: str
```

### RiskAssessment

```python
class RiskAssessment(BaseModel):
    id: str
    target_type: Literal["material", "component", "bom_item", "project"]
    target_id: str
    risk_level: Literal["red", "orange", "yellow", "green", "unknown"]
    score: int
    factor_scores: dict[str, int]
    reasons: list[str]
    recommendations: list[str]
    confidence_score: int
```

### BusinessConclusion

```python
class BusinessConclusion(BaseModel):
    conclusion_type: Literal["selection_review", "delivery_risk"]
    target_id: str
    decision: Literal["通过", "有条件通过", "不建议", "红色", "橙色", "黄色", "绿色", "待确认"]
    summary: str
    reasons: list[str]
    procurement_actions: list[str]
    rd_actions: list[str]
    project_actions: list[str]
```

---

## 四、实施任务

### Task 1：建立EMS行业全链路知识库

**目标**：把源文档中的EMS行业链路沉淀为可被后端调用的结构化知识库。

**文件**：

- 新增：`backend/app/knowledge/industry_chain_library.py`
- 新增：`backend/tests/test_industry_chain_library.py`

**接口产出**：

```python
def get_component_profiles() -> list[dict]: ...
def get_profile_by_category(category_id: str) -> dict | None: ...
def get_material_to_component_index() -> dict[str, list[str]]: ...
def get_source_to_material_index() -> dict[str, list[str]]: ...
```

**必须覆盖的元器件类别**：

- PCB/FPC/铝基板
- MCU/DSP/FPGA/存储/电源IC/驱动IC/模拟IC
- MOSFET/IGBT/二极管/TVS/ESD/功率模块
- MLCC/钽电容/铝电解/薄膜电容
- 电阻/热敏/压敏/保险丝
- 电感/变压器/磁珠/共模电感
- 继电器/开关
- 连接器/端子/线束/排针排母
- 风扇/电机
- 散热器/热管/导热材料
- 结构件/钣金/压铸/塑胶壳
- 显示屏/LED/光耦/传感器
- 电池/电源模块

**测试要求**：

```python
def test_industry_chain_covers_core_ems_categories():
    profiles = get_component_profiles()
    category_ids = {item["category_id"] for item in profiles}
    assert "pcb" in category_ids
    assert "connector" in category_ids
    assert "relay" in category_ids
    assert "mlcc" in category_ids
    assert "mosfet" in category_ids
    assert "aluminum_electrolytic_capacitor" in category_ids
    assert "inductor_transformer" in category_ids
    assert "mechanical_thermal" in category_ids


def test_connector_profile_links_metals_plastics_and_sources():
    profile = get_profile_by_category("connector")
    assert "copper_alloy" in profile["upstream_materials"]
    assert "tin" in profile["upstream_materials"]
    assert "nickel" in profile["upstream_materials"]
    assert "engineering_plastic" in profile["upstream_materials"]
    assert "smm" in profile["source_ids"]
    assert "lme" in profile["source_ids"]
```

**验收标准**：

- 至少覆盖14个EMS核心物料大类。
- 每个类别至少包含3个上游材料/制程节点。
- 每个类别至少关联1个行情源或事件源。
- 铜价事件能反向关联到PCB、连接器、线束、继电器、电感、变压器、功率器件。

---

### Task 2：建立BOM元器件分类与材料拆解服务

**目标**：把BOM中的物料描述、分类、型号映射到EMS元器件类别和上游材料。

**文件**：

- 新增：`backend/app/services/industry_chain/component_classifier.py`
- 新增：`backend/app/services/industry_chain/material_decomposer.py`
- 新增：`backend/tests/test_component_classifier.py`
- 修改：`backend/app/knowledge/material_mapping.py`

**接口产出**：

```python
def classify_component(item_code: str, item_name: str, category: str | None = None) -> str:
    ...


def decompose_component(category_id: str) -> ComponentMaterialProfile:
    ...
```

**分类规则**：

- 优先使用BOM已有类别字段。
- 类别缺失时，使用型号前缀、物料名称关键词、封装关键词识别。
- 低置信度识别结果返回 `unknown`，进入人工确认。

**测试要求**：

```python
def test_classify_connector_from_name():
    assert classify_component("JST-XH-2P", "JST连接器 2P", None) == "connector"


def test_classify_mosfet_from_item_code():
    assert classify_component("IRLZ44N", "N沟道MOSFET", None) == "mosfet"


def test_unknown_when_no_signal():
    assert classify_component("ABC-001", "定制件", None) == "unknown"


def test_decompose_relay_contains_silver_contact_and_copper_coil():
    profile = decompose_component("relay")
    assert "silver" in profile.upstream_materials
    assert "copper_wire" in profile.upstream_materials
    assert "steel_alloy" in profile.upstream_materials
```

**验收标准**：

- 常见BOM行能自动识别为EMS类别。
- 识别失败不误判为正常，而是进入待确认。
- 前端后续能展示“BOM型号 → 元器件类别 → 材料组成”。

---

### Task 3：重构风险评分引擎

**目标**：把风险等级从价格单因子改成多因子评分。

**文件**：

- 新增：`backend/app/services/industry_chain/risk_scoring_engine.py`
- 新增：`backend/tests/test_risk_scoring_engine.py`
- 修改：`backend/app/api/material_alerts.py`
- 修改：`backend/app/api/risk_chain.py`

**评分公式**：

```text
总风险分 = 行情趋势分 × 25%
        + 供应紧张分 × 20%
        + 政策合规分 × 15%
        + 灾害区域分 × 10%
        + BOM暴露度 × 15%
        + 替代难度 × 10%
        + 数据置信度调整 × 5%
```

**风险等级边界**：

| 分数 | 等级 |
|---|---|
| 80-100 | red |
| 60-79 | orange |
| 40-59 | yellow |
| 1-39 | green |
| 无有效数据 | unknown |

**自动提级规则**：

- S级来源出现出口管制、实体清单、关税变化，至少橙色。
- 原厂PCN/EOL/LTB命中BOM型号，至少橙色；无替代料则红色。
- 关键材料7日涨幅超过阈值且命中高用量BOM，提升一级。
- 供应商所在地出现红色灾害事件，提升一级并标记区域风险。
- 分销库存低于安全库存且交期拉长，至少橙色。
- 单一品牌/单一供应商且无替代料，至少黄色。
- 数据缺失但BOM关键度高，显示 `unknown`。

**测试要求**：

```python
def test_unknown_when_no_valid_data():
    result = score_risk({"has_price": False, "has_event": False, "bom_criticality": "high"})
    assert result.risk_level == "unknown"
    assert "数据不足" in result.reasons[0]


def test_policy_event_from_s_level_source_promotes_to_orange():
    result = score_risk({"policy_score": 90, "source_level": "S", "event_type": "export_control"})
    assert result.risk_level in ["orange", "red"]


def test_price_event_with_bom_exposure_promotes_one_level():
    result = score_risk({"price_trend_score": 65, "bom_exposure_score": 80, "confidence_score": 85})
    assert result.risk_level == "orange"
```

**验收标准**：

- 材料链路库不再出现“无数据但正常”。
- 风险等级能解释因子分。
- 前端展示材料、供应、政策、灾害、BOM暴露度、替代难度的拆解。

---

### Task 4：建立BOM暴露度引擎

**目标**：让风险事件能够自动命中BOM行和项目。

**文件**：

- 新增：`backend/app/services/industry_chain/bom_exposure_engine.py`
- 新增：`backend/tests/test_bom_exposure_engine.py`
- 修改：`backend/app/api/risk_chain.py`

**接口产出**：

```python
def calculate_bom_exposure(event: RiskEvent, bom_items: list[BomItem]) -> list[BomExposure]:
    ...
```

**命中逻辑**：

1. 事件影响材料命中元器件上游材料。
2. 元器件类别命中BOM行类别。
3. BOM行关键度、用量、项目阶段、交付窗口参与暴露度计算。
4. 命中结果返回原因说明。

**测试要求**：

```python
def test_copper_event_hits_multiple_component_categories():
    event = RiskEvent(
        id="event-cu-up",
        title="铜价上涨",
        event_type="commodity_price",
        severity="orange",
        source_id="smm",
        source_level="A",
        occurred_at="2026-07-08",
        summary="铜价7日上涨",
        affected_material_ids=["copper", "copper_foil", "copper_alloy", "copper_wire"],
        affected_component_categories=[],
        affected_regions=[],
        confidence_score=85,
    )
    bom_items = [
        make_bom_item("PCB-001", "8层HDI PCB", "pcb"),
        make_bom_item("CONN-001", "连接器", "connector"),
        make_bom_item("WIRE-001", "线束", "wire_harness"),
    ]
    exposures = calculate_bom_exposure(event, bom_items)
    assert {item.category_id for item in exposures} == {"pcb", "connector", "wire_harness"}
```

**验收标准**：

- 任一风险事件能输出被影响的BOM型号。
- 铜、铝、钢、锡、镍、银、锂、树脂、工程塑料等材料都能向下传导。
- 暴露结果能解释“为什么命中”。

---

### Task 5：新增新项目选型评审和老项目交付风险结论

**目标**：系统不只显示风险，还要输出业务结论。

**文件**：

- 新增：`backend/app/services/industry_chain/recommendation_engine.py`
- 修改：`backend/app/api/bom_project.py`
- 新增或修改：`backend/tests/test_bom_project_business_conclusion.py`
- 修改：`frontend/src/views/BomAnalyze.vue`
- 修改：`frontend/src/views/BomProjectDetail.vue`
- 修改：`frontend/src/views/__tests__/BomAnalyze.test.js`

**后端API**：

```text
GET /api/bom-projects/{project_id}/selection-review
GET /api/bom-projects/{project_id}/delivery-risk
```

**选型评审输出**：

```json
{
  "conclusion_type": "selection_review",
  "decision": "有条件通过",
  "summary": "存在单品牌MCU、PCB铜箔成本和连接器镀层风险，建议补充替代方案后通过。",
  "reasons": ["主控MCU单品牌", "PCB为高铜耗8层板", "连接器镀金规格受贵金属影响"],
  "procurement_actions": ["确认8周报价有效期"],
  "rd_actions": ["补充Pin-to-Pin替代料"],
  "project_actions": ["把关键料验证纳入EVT出口条件"]
}
```

**交付风险输出**：

```json
{
  "conclusion_type": "delivery_risk",
  "decision": "橙色",
  "summary": "未来4-8周存在连接器、PCB和功率器件交付风险。",
  "reasons": ["铜价上涨命中12个BOM行", "关键连接器库存低于安全线", "台风可能影响华南供应商出货"],
  "procurement_actions": ["提前锁定8周需求"],
  "rd_actions": ["确认替代料验证周期"],
  "project_actions": ["更新交付缓冲"]
}
```

**测试要求**：

```python
def test_selection_review_returns_conditional_pass_for_single_source_mcu():
    response = client.get("/api/bom-projects/1/selection-review")
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] in ["通过", "有条件通过", "不建议", "待确认"]
    assert "reasons" in data
    assert "rd_actions" in data


def test_delivery_risk_returns_4_to_8_week_risk_summary():
    response = client.get("/api/bom-projects/1/delivery-risk")
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] in ["红色", "橙色", "黄色", "绿色", "待确认"]
    assert "未来" in data["summary"] or "交付" in data["summary"]
```

**验收标准**：

- 每个项目详情页能看到选型评审结论和交付风险结论。
- 结论不是泛泛文字，必须引用命中风险、BOM行、材料或事件。
- 无充分数据时输出“待确认”，不输出虚假的通过。

---

### Task 6：重构材料链路库页面

**目标**：把材料链路库从“固定材料价格列表”改成“元器件类型驱动的上游组成库”。

**文件**：

- 新增：`backend/app/api/industry_chain.py`
- 修改：`backend/app/main.py`
- 新增：`frontend/src/api/industryChain.js`
- 新增：`frontend/src/components/materials/ComponentMaterialChain.vue`
- 修改：`frontend/src/views/MaterialWatch.vue`
- 新增或修改：`frontend/src/views/__tests__/MaterialWatch.test.js`

**后端API**：

```text
GET /api/industry-chain/component-profiles
GET /api/industry-chain/component-profiles/{category_id}
GET /api/industry-chain/material-exposure?material_id=copper
```

**页面交互**：

- 左侧选择元器件类别。
- 中间显示该类别的上游材料、制程、行情源。
- 右侧显示命中的BOM行、风险等级和建议。
- 无数据源时显示“待确认/未接入”，不显示正常。

**前端测试要求**：

```javascript
it('材料链路库按元器件类别展示上游材料', async () => {
  expect(wrapper.text()).toContain('连接器')
  expect(wrapper.text()).toContain('铜合金')
  expect(wrapper.text()).toContain('镀锡')
  expect(wrapper.text()).toContain('工程塑料')
})

it('无行情数据时显示待确认而不是正常', async () => {
  expect(wrapper.text()).toContain('待确认')
  expect(wrapper.text()).not.toContain('全部正常')
})
```

**验收标准**：

- 截图中“风险等级全正常”的问题彻底消失。
- 物料数量不再固定为33个材料，而是按BOM类别和EMS链路动态展开。
- 能看到“连接器 → 铜合金/镀锡/镀镍/LCP/PBT/PA66”等深度链路。

---

### Task 7：重构风险链路驾驶舱

**目标**：把首页改成“风险信号流 + EMS链路图谱 + BOM影响 + 业务结论”。

**文件**：

- 修改：`backend/app/api/risk_chain.py`
- 新增：`frontend/src/components/risk-chain/RiskSignalStream.vue`
- 新增：`frontend/src/components/risk-chain/IndustryChainGraph.vue`
- 新增：`frontend/src/components/risk-chain/BomImpactPanel.vue`
- 新增：`frontend/src/components/risk-chain/BusinessConclusionPanel.vue`
- 修改：`frontend/src/views/RiskChainDashboard.vue`
- 修改：`frontend/src/views/__tests__/RiskChainDashboard.test.js`

**新版Dashboard返回结构**：

```json
{
  "summary": {},
  "riskSignals": [],
  "industryGraph": {
    "nodes": [],
    "edges": []
  },
  "bomImpacts": [],
  "selectionConclusions": [],
  "deliveryRiskConclusions": [],
  "strategies": []
}
```

**页面结构**：

```text
顶部：今日新增风险、自动提级BOM、受影响项目、高风险交付项目、建议立即处理事项
左侧：风险信号流
中间：EMS产业链风险图谱
右侧：BOM影响和处理建议
底部：新项目选型结论、老项目交付风险结论
```

**前端测试要求**：

```javascript
it('首页展示风险信号到BOM影响的完整链路', async () => {
  expect(wrapper.text()).toContain('风险信号流')
  expect(wrapper.text()).toContain('EMS产业链风险图谱')
  expect(wrapper.text()).toContain('BOM影响')
  expect(wrapper.text()).toContain('选型评审结论')
  expect(wrapper.text()).toContain('交付风险结论')
})
```

**验收标准**：

- 首页不再只是材料链路示例。
- 任一风险信号都能看到传导路径。
- BOM影响结果能打开证据链路。
- 页面能直接服务领导汇报。

---

### Task 8：建立多源数据注册表和适配器

**目标**：统一管理所有数据源，已配置的源可取数，未配置的源明确返回未接入。

**文件**：

- 新增：`backend/app/knowledge/source_registry.py`
- 新增：`backend/app/services/sources/market_source_registry.py`
- 新增：`backend/app/services/sources/commodity/smm_source.py`
- 新增：`backend/app/services/sources/commodity/mysteel_source.py`
- 新增：`backend/app/services/sources/commodity/lme_source.py`
- 新增：`backend/app/services/sources/commodity/shfe_source.py`
- 新增：`backend/app/services/sources/policy/bis_source.py`
- 新增：`backend/app/services/sources/policy/ustr_source.py`
- 新增：`backend/app/services/sources/policy/trade_csl_source.py`
- 新增：`backend/app/services/sources/disaster/usgs_source.py`
- 新增：`backend/app/services/sources/disaster/gdacs_source.py`
- 新增：`backend/app/services/sources/weather/noaa_source.py`
- 新增：`backend/tests/test_source_registry.py`
- 修改：`backend/app/config.py`

**配置项**：

```python
smm_api_key: str | None = None
mysteel_api_key: str | None = None
digikey_client_id: str | None = None
digikey_client_secret: str | None = None
mouser_api_key: str | None = None
deepseek_api_key: str | None = None
llm_gateway_url: str | None = None
llm_gateway_api_key: str | None = None
```

**统一返回**：

```python
class SourceFetchResult(BaseModel):
    source_id: str
    status: Literal["ok", "not_configured", "error"]
    records: list[dict]
    message: str
```

**测试要求**：

```python
def test_smm_source_returns_not_configured_without_api_key():
    source = SmmSource(api_key=None)
    result = source.fetch("copper")
    assert result.status == "not_configured"
    assert result.records == []


def test_source_registry_contains_required_sources():
    registry = get_source_registry()
    for source_id in ["smm", "mysteel", "lme", "shfe", "bis", "ustr", "trade_csl", "usgs", "gdacs", "noaa", "digikey", "mouser", "lcsc"]:
        assert source_id in registry
```

**验收标准**：

- 系统知道哪些源已接入、哪些未配置。
- 未配置不会报错，也不会显示正常。
- 前端能显示“数据源未配置，需要API Key”。

---

### Task 9：建立人工确认和半自动输入队列

**目标**：处理公众号、涨价函、供应商邮件、采购反馈等暂不能自动读取的信息。

**文件**：

- 新增：`backend/app/services/industry_chain/review_queue.py`
- 修改：`backend/app/api/market_inbox.py`
- 修改：`frontend/src/views/MarketInbox.vue`
- 新增或修改：`backend/tests/test_review_queue.py`

**输入方式**：

- 文本粘贴
- 链接归档
- 文件上传
- 手工录入
- 采购反馈

**队列状态**：

```text
pending_review → confirmed → rejected → converted_to_event
```

**验收标准**：

- 公众号内容不能自动读取时，用户可粘贴文本进入风险池。
- LLM可对待确认内容给出结构化建议，但必须人工确认后进入正式风险事件。

---

### Task 10：接入LLM分析层

**目标**：让LLM辅助事件解析、BOM分类、链路推理、建议生成和报告摘要。

**文件**：

- 修改：`backend/app/services/llm_client.py`
- 新增：`backend/app/services/llm_analysis_service.py`
- 新增：`backend/app/api/llm_analysis.py`
- 新增：`backend/tests/test_llm_analysis_service.py`
- 新增：`frontend/src/api/llmAnalysis.js`
- 新增：`frontend/src/views/LlmAnalysis.vue`
- 新增：`frontend/src/views/__tests__/LlmAnalysis.test.js`
- 修改：`frontend/src/router/index.js`
- 修改：`frontend/src/App.vue`

**LLM Provider**：

```python
class LLMProvider(str, Enum):
    anthropic = "anthropic"
    deepseek = "deepseek"
    gateway = "gateway"
```

**能力接口**：

```text
POST /api/llm-analysis/extract-event
POST /api/llm-analysis/infer-risk-chain
POST /api/llm-analysis/generate-recommendation
POST /api/llm-analysis/summarize-daily-risk
```

**约束**：

- LLM输入必须脱敏客户名、供应商报价、商业敏感字段。
- LLM输出必须包含 `confidence`。
- LLM输出风险等级为建议值，最终等级由 `risk_scoring_engine` 决定。

**测试要求**：

```python
def test_llm_analysis_returns_not_configured_without_key():
    service = LlmAnalysisService(client=FakeUnavailableClient())
    result = service.extract_event("某原厂发布涨价函")
    assert result["status"] == "not_configured"


def test_llm_recommendation_requires_source_context():
    service = LlmAnalysisService(client=FakeClient())
    result = service.generate_recommendation({"event": "铜价上涨", "sources": []})
    assert result["status"] == "need_source_context"
```

**验收标准**：

- 配置DeepSeek或网宿网关后可切换Provider。
- 未配置时页面明确显示“LLM未配置”，不影响主流程。
- 可上传或粘贴涨价函/PCN文本并得到结构化提取结果。

---

### Task 11：建立风险运营闭环

**目标**：让风险有状态、有负责人、有处理动作、有解除记录。

**文件**：

- 新增：`backend/app/models/risk_workflow.py`
- 新增：`backend/app/api/risk_workflow.py`
- 新增：`backend/tests/test_risk_workflow.py`
- 修改：`frontend/src/views/RiskChainDashboard.vue`
- 修改：`frontend/src/views/MarketEvents.vue`

**状态流**：

```text
new → acknowledged → assigned → in_progress → mitigated → closed
```

**验收标准**：

- 红色/橙色风险可以创建处理任务。
- 任务能分配采购、研发、项目经理、供应链。
- 风险解除后保留处理记录。

---

### Task 12：测试、构建、部署包更新

**目标**：完成全量验证并重新打包供应商部署ZIP。

**文件**：

- 修改：`服务器部署说明-交付供应商.md`
- 更新：`BOM交期风险智能排查系统-服务器部署包.zip`

**验证命令**：

```powershell
python -m pytest tests -q
npm run test -- --run
npm run build
python c:\Users\HAIER\.trae-cn\work\6a3a1656122fe7f887f6ea50\create_deploy_zip.py
```

**ZIP校验**：

必须包含：

```text
backend/app/knowledge/industry_chain_library.py
backend/app/knowledge/source_registry.py
backend/app/services/industry_chain/risk_scoring_engine.py
backend/app/services/llm_analysis_service.py
frontend/src/views/RiskChainDashboard.vue
frontend/src/views/MaterialWatch.vue
frontend/dist/index.html
服务器部署说明-交付供应商.md
```

必须排除：

```text
node_modules
.git
.venv
venv
__pycache__
.pytest_cache
.vite
```

**验收标准**：

- 后端测试通过。
- 前端测试通过。
- 前端构建通过。
- ZIP重新生成并校验。
- 打开系统能看到新驾驶舱、材料链路库、BOM评审结论、交付风险结论。

---

## 五、阶段交付安排

### 第一阶段：核心链路逻辑修正

包含 Task 1 到 Task 7。

交付结果：

- 风险链路驾驶舱逻辑正确。
- 材料链路库按元器件类型展开。
- 风险等级不再全部正常。
- BOM有选型评审结论和交付风险结论。

### 第二阶段：数据源框架和半自动输入

包含 Task 8 到 Task 9。

交付结果：

- SMM、Mysteel、LME、SHFE、BIS、USTR、Trade.gov、USGS、GDACS、NOAA等源进入注册表。
- 有API Key的源可启用，未配置源显示未接入。
- 公众号、涨价函、采购反馈可进入人工确认队列。

### 第三阶段：LLM分析层

包含 Task 10。

交付结果：

- 可接DeepSeek或网宿网关。
- 可解析公告、涨价函、PCN/EOL。
- 可生成链路推理和采购/研发/项目建议。

### 第四阶段：风险运营闭环和部署交付

包含 Task 11 到 Task 12。

交付结果：

- 风险事件可分派、处理、关闭。
- 部署说明更新。
- ZIP部署包重新生成。

---

## 六、开发过程保障机制

### 需求覆盖检查

每个阶段完成后必须更新以下覆盖表：

| 需求编号 | 状态 | 证据 |
|---|---|---|
| R1 | 未开始/进行中/完成 | 测试文件、API返回、页面截图或构建结果 |
| R2 | 未开始/进行中/完成 | 知识库文件和测试结果 |
| R3 | 未开始/进行中/完成 | 分类服务和测试结果 |
| R4 | 未开始/进行中/完成 | 风险评分测试结果 |
| R5 | 未开始/进行中/完成 | unknown状态测试结果 |
| R6 | 未开始/进行中/完成 | 选型评审API和页面测试 |
| R7 | 未开始/进行中/完成 | 交付风险API和页面测试 |
| R8 | 未开始/进行中/完成 | 材料链路库页面测试 |
| R9 | 未开始/进行中/完成 | source registry测试 |
| R10 | 未开始/进行中/完成 | review queue测试 |
| R11 | 未开始/进行中/完成 | LLM分析测试 |
| R12 | 未开始/进行中/完成 | risk workflow测试 |
| R13 | 未开始/进行中/完成 | ZIP校验输出 |

### 不允许上线的情况

- 风险无数据却显示“正常”。
- 外部API未配置却显示为已实时取数。
- LLM生成没有来源的事实价格。
- BOM选型结论没有任何原因说明。
- 老项目交付风险没有具体影响窗口或建议动作。
- 测试未跑完就重新打包。

### 每阶段完成定义

每阶段必须满足：

1. 本阶段任务测试全部通过。
2. 前端页面能正常打开。
3. 与源MD对应需求能找到证据。
4. 没有伪造外部数据。
5. 更新必要文档。
6. 如果影响部署包，重新打包ZIP。

---

## 七、建议执行方式

建议采用 **Subagent-Driven** 方式执行，按任务派发独立开发和审查：

1. 每个任务由独立子任务完成。
2. 主会话负责审查任务结果和跑测试。
3. 每完成一个任务，更新需求覆盖表。
4. 每阶段结束后启动系统给用户查看。

如果采用当前会话内联执行，也必须按 Task 1 到 Task 12 顺序推进，不允许跳过测试直接写页面。

---

## 八、第一阶段完成后的验收画面

第一阶段完成后，用户打开系统应看到：

```text
风险链路驾驶舱
- 今日新增风险事件
- 自动提级BOM型号
- 受影响项目
- 高风险交付项目
- 建议立即处理事项

中间主图
风险信号 → 产业链节点 → 材料/制程 → 元器件类别 → BOM型号 → 项目风险

材料链路库
选择“连接器”后显示：铜合金、镀锡、镀镍、LCP、PBT、PA66、电镀制程、关联行情源、命中BOM行

BOM分析
显示新项目选型评审结论和老项目交付风险结论
```

这是判断第一阶段是否真正执行源MD的关键标准。
