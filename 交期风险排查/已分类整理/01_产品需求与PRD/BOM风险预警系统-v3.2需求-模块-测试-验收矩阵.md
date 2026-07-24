# BOM风险预警系统 v3.2 需求-模块-测试-验收矩阵

> 用途：作为后续 coding agent 的执行约束。任何代码开发必须能回溯到本矩阵中的需求编号、模块、测试样例和验收标准。  
> 适用范围：第一期 MVP，以“双轨风险模型 + 高容 MLCC + 人工触发 + 情报可信度 + 依据链 + 预测验证”为主。

## 1. 需求编号规则

```text
R-BOM      BOM解析与物料标准化
R-CAT      品类识别与高容MLCC识别
R-MANUAL   人工触发行情事件
R-INTEL    情报源与公众号/媒体甄别
R-RISK     双轨风险引擎
R-LINK     同行联动与替代料挤占
R-EVID     风险依据链
R-PRED     预测验证闭环
R-UI       前端展示与操作页面
R-GATE     开发过程门禁
```

## 2. 第一阶段 MVP 需求矩阵

| 需求编号 | 需求描述 | 来源 | 模块 | 主要文件 | 测试文件 | 核心测试样例 | 验收标准 |
|---|---|---|---|---|---|---|---|
| R-BOM-001 | 上传 BOM 后保留原始型号、品牌、描述、数量、项目和 PCBA 信息 | 现有系统 + v3.2 | BOM解析 | `backend/app/services/bom_parser.py`、`backend/app/models/bom.py` | `tests/test_bom_parser_v2.py`、`tests/test_risk_analysis_v32.py` | 上传包含 MCU、PCB、高容MLCC、继电器的 BOM | 数据库中每行 BOM 可追溯原始字段和标准字段 |
| R-BOM-002 | BOM 行项目应能参与历史 BOM 命中和项目级影响分析 | v3.2 | BOM项目化 | `backend/app/api/bom_project.py`、`backend/app/services/incremental_scanner.py` | `tests/test_risk_analysis_v32.py` | 人工录入高容MLCC涨价事件后命中多个历史项目 | 返回命中 BOM 行、PCBA、项目数量和影响等级 |
| R-CAT-001 | 识别常见物料品类：MCU、PMIC、功率器件、分立器件、PCB、继电器、连接器、电感、变压器、铝电解、MLCC | v3.2 | 品类识别 | `backend/app/services/upstream/category_classifier.py` | `tests/test_category_classifier.py` | 输入不同描述和型号，输出对应品类 | 品类识别准确，无法识别时返回 `unknown` 和信息不足原因 |
| R-CAT-002 | 识别高容 MLCC，不把普通 MLCC 误判为高容 | 用户新增 + v3.2 | 高容MLCC识别 | `backend/app/services/upstream/mlcc_classifier.py` | `tests/test_mlcc_classifier.py` | `22uF 25V X7R 0805` 标记高容；`100nF 50V X7R 0603` 不标记高容 | 正例和反例均通过，输出容值、电压、介质、尺寸和高容标记 |
| R-CAT-003 | 高容 MLCC 应进入重点风险模型，而普通 MLCC 保持普通混合模型 | v3.2 | 高容MLCC画像 | `backend/app/models/upstream.py`、`backend/app/services/upstream/mlcc_classifier.py` | `tests/test_mlcc_classifier.py`、`tests/test_dual_track_risk_engine.py` | 高容MLCC + 缺货事件进入橙色/红色候选 | 风险结果中 `special_profile=high_cap_mlcc` |
| R-MANUAL-001 | 支持人工录入涨价、缺货、交期延长、控单、产能紧张事件 | v3.2 | 人工触发 | `backend/app/api/manual_events.py`、`backend/app/services/upstream/manual_event_service.py`、`backend/app/models/intelligence.py` | `tests/test_manual_event_service.py` | 录入“高容MLCC 涨价+缺货” | 事件被结构化保存，包含品类、品牌、涨幅、缺货等级、来源、置信度 |
| R-MANUAL-002 | 人工事件录入后立即匹配历史 BOM、新 BOM、AVL 和替代料库 | v3.2 | 事件命中 | `backend/app/services/upstream/manual_event_service.py`、`backend/app/services/bom_matcher.py` | `tests/test_manual_event_service.py` | 高容MLCC事件命中 BOM 中所有 22uF/47uF MLCC | 返回命中行项目列表和项目影响摘要 |
| R-MANUAL-003 | 人工事件应进入后续预测验证，不只是一次性提醒 | v3.2 | 人工触发 + 预测 | `backend/app/services/upstream/prediction_verifier.py` | `tests/test_prediction_verifier.py` | 人工录入 PMIC 涨价事件后生成 30/60/90 天验证任务 | `risk_predictions` 中存在对应记录 |
| R-INTEL-001 | 建立情报源库，区分官方、研究机构、行业媒体、公众号、渠道自媒体、人工来源 | v3.2 | 情报源管理 | `backend/app/models/intelligence.py`、`backend/app/services/upstream/intelligence_scoring.py` | `tests/test_intelligence_scoring.py` | 原厂公告可信度高，渠道传闻可信度低 | 返回 `source_type`、`credibility_current`、`evidence_level` |
| R-INTEL-002 | 公众号/媒体情报必须经过来源可信度、字段完整度、多源验证和历史命中率加权 | v3.2 | 情报评分 | `backend/app/services/upstream/intelligence_scoring.py` | `tests/test_intelligence_scoring.py` | 单一公众号称“芯片将涨价”，无品牌型号 | 不触发高风险，仅进入观察池 |
| R-INTEL-003 | 有原厂涨价函、代理通知或多源强验证时，可进入确认事件 | v3.2 | 情报审核 | `backend/app/api/intelligence.py`、`backend/app/services/upstream/intelligence_scoring.py` | `tests/test_intelligence_scoring.py` | 原厂涨价函包含品牌、品类、涨幅、生效日 | 自动建议确认或进入高可信候选 |
| R-RISK-001 | 风险引擎必须区分材料传导轨和供需信号轨 | v3.2 | 双轨风险引擎 | `backend/app/services/upstream/dual_track_risk_engine.py` | `tests/test_dual_track_risk_engine.py` | PCB 铜价上涨走材料轨；MCU 交期拉长走供需轨 | 输出 `risk_track=material` 或 `risk_track=demand_supply` |
| R-RISK-002 | PCB、继电器、连接器、电感、铝电解按成本驱动模型评分 | v3.1 + v3.2 | 成本驱动模型 | `dual_track_risk_engine.py`、`propagation_rules.py` | `tests/test_dual_track_risk_engine.py` | 铜价上涨 + PCB供应商报价有效期缩短 | PCB 风险升为黄色/橙色，并解释铜价传导链 |
| R-RISK-003 | MCU、PMIC、电源芯片不能因单一材料上涨直接红色预警 | v3.1 + v3.2 | 供需驱动模型 | `dual_track_risk_engine.py` | `tests/test_dual_track_risk_engine.py` | 仅硅片上涨，无库存下降、无交期拉长 | MCU 不得红色，最多弱关联提示 |
| R-RISK-004 | 高容 MLCC 已涨价缺货时应进入重点风险 | 用户新增 + v3.2 | 高容MLCC风险模型 | `dual_track_risk_engine.py`、`mlcc_classifier.py` | `tests/test_dual_track_risk_engine.py` | 高容MLCC + 多渠道涨价 + 缺货 | 风险等级至少橙色，输出“供需信号轨为主，材料轨辅助” |
| R-RISK-005 | 情报事实、同行联动、供需平衡、BOM影响、缓冲因子应参与评分 | v3.2 | 风险融合 | `dual_track_risk_engine.py` | `tests/test_dual_track_risk_engine.py` | 同品类涨价但本企业有90天库存 | 风险紧急程度被缓冲因子降低 |
| R-LINK-001 | 支持同行联动：某品牌涨价缺货后，同品类竞品和替代料风险上升 | v3.2 | 同行联动 | `backend/app/services/upstream/linkage_engine.py` | `tests/test_linkage_engine.py` | 国巨高容MLCC缺货，村田/TDK/风华同规格被提高关注 | 生成联动候选，不直接全部红色 |
| R-LINK-002 | 支持替代料挤占：主料缺货导致 pin-to-pin 替代料需求升高 | v3.2 | 替代料联动 | `linkage_engine.py`、`bom_matcher.py` | `tests/test_linkage_engine.py` | MCU A 缺货，替代 MCU B 被多个项目引用 | 替代料风险升高并说明原因 |
| R-EVID-001 | 每条预警必须输出依据链 | v3.2 | 依据链生成 | `backend/app/services/upstream/evidence_chain_builder.py` | `tests/test_evidence_chain_builder.py` | 高容MLCC涨价缺货事件 | 输出“事件→品类→BOM命中→风险等级→建议动作” |
| R-EVID-002 | 数据不足时必须输出信息不足，不能强行低风险 | v3.1 + v3.2 | 信息不足状态 | `evidence_chain_builder.py`、`dual_track_risk_engine.py` | `tests/test_evidence_chain_builder.py` | 未知型号、无品牌、无描述 | 返回 `information_status=insufficient` |
| R-PRED-001 | 风险预警应生成预测验证记录 | v3.1 + v3.2 | 预测验证 | `backend/app/models/prediction.py`、`prediction_verifier.py` | `tests/test_prediction_verifier.py` | PCB橙色预警生成验证记录 | 记录预测对象、风险类型、预期窗口、模型版本 |
| R-PRED-002 | 到期后可验证 hit、partial_hit、miss、unverifiable | v3.1 | 预测验证 | `prediction_verifier.py` | `tests/test_prediction_verifier.py` | 价格上涨符合预期 | 命中状态被更新，来源/规则命中率同步变化 |
| R-UI-001 | 前端风险总览应显示材料传导轨和供需信号轨 | v3.2 | 前端总览 | `frontend/src/views/BomAnalyze.vue`、`DualTrackRiskBadge.vue` | 前端组件测试或人工验收 | 同一 BOM 中 PCB 和高容MLCC显示不同轨道 | 用户能一眼区分风险来源 |
| R-UI-002 | 支持人工录入预警页面 | v3.2 | 前端人工触发 | `frontend/src/views/ManualEvents.vue` | 前端组件测试或人工验收 | 录入高容MLCC涨价缺货事件 | 页面提交成功并返回命中 BOM 摘要 |
| R-UI-003 | 支持情报审核页 | v3.2 | 前端情报审核 | `frontend/src/views/IntelligenceReview.vue` | 前端组件测试或人工验收 | 单条公众号情报显示来源可信度和建议动作 | 可确认、观察、丢弃 |
| R-UI-004 | 风险详情页展示依据链、置信度、信息来源和建议动作 | v3.2 | 前端依据链 | `EvidenceChainPanel.vue`、`RiskEvidence.vue` | 前端组件测试或人工验收 | 高容MLCC风险详情 | 页面包含风险轨道、依据链、命中BOM、建议动作 |
| R-GATE-001 | 所有模块交付前必须运行测试并记录结果 | 开发保障 | 验收门禁 | 文档与执行规范 | 验收记录 | 任一模块完成前 | 无测试结果不得标记完成 |
| R-GATE-002 | 不允许修改测试期望来适配错误实现 | TDD | 开发门禁 | 执行规范 | Code Review | 发现测试期望被不合理修改 | 退回重做 |
| R-GATE-003 | 不允许把公众号单一传闻直接作为强预警 | v3.2 | 情报门禁 | `intelligence_scoring.py` | `tests/test_intelligence_scoring.py` | 单一公众号，无原始出处 | 不得进入红色/橙色确认事件 |

## 3. 第一批黄金测试样例

### 3.1 高容 MLCC 正例

| 输入 | 期望 |
|---|---|
| `22uF 25V X7R 0805 MLCC` | `high_capacitance_flag=True` |
| `47uF 10V X5R 0603` | `high_capacitance_flag=True` |
| `100uF 6.3V X5R 1206` | `high_capacitance_flag=True` |

### 3.2 普通 MLCC 反例

| 输入 | 期望 |
|---|---|
| `100nF 50V X7R 0603` | `high_capacitance_flag=False` |
| `10nF 50V C0G 0402` | `high_capacitance_flag=False` |
| `1uF 50V X7R 0603` | `high_capacitance_flag=False` 或低风险普通MLCC |

### 3.3 MCU 供需风险正例

```text
输入：某32位MCU，库存连续下降，交期从8周变20周，同类品牌涨价，汽车/工业需求上升
期望：供需信号轨，橙色风险，依据链包含库存、交期、同行联动
```

### 3.4 MCU 材料传导反例

```text
输入：某32位MCU，仅硅片上涨，无库存下降，无交期拉长，无供应商涨价函
期望：不能红色预警；最多输出弱关联或信息不足
```

### 3.5 PCB 材料传导正例

```text
输入：四层FR-4 PCB，1oz铜厚，铜价上涨，PCB供应商报价有效期缩短
期望：材料传导轨，黄色/橙色风险，依据链包含铜价→铜箔/覆铜板→PCB报价压力
```

### 3.6 公众号情报反例

```text
输入：单一公众号称“某类芯片即将涨价”，无品牌、无型号、无原始出处
期望：进入观察池或噪声，不触发高风险
```

### 3.7 人工触发正例

```text
输入：人工录入“高容MLCC涨价缺货，影响22uF/47uF，品牌国巨/村田/TDK”
期望：系统匹配历史BOM和当前BOM中的高容MLCC，生成风险依据链和预测验证记录
```

## 4. 验收记录模板

每个模块交付时，必须填写以下记录。

```text
模块名称：
需求编号：
改动文件：
新增测试：
测试命令：
测试结果：
覆盖正例：
覆盖反例：
未覆盖项：
已知限制：
是否允许进入下一模块：是/否
```

## 5. 需求覆盖优先级

| 优先级 | 需求编号 | 原因 |
|---|---|---|
| P0 | R-CAT-002、R-RISK-004、R-MANUAL-001、R-MANUAL-002、R-EVID-001 | 打通高容MLCC涨价缺货到BOM命中的核心闭环 |
| P0 | R-INTEL-002、R-GATE-003 | 防止公众号/传闻导致误报 |
| P0 | R-RISK-001、R-RISK-003 | 保证双轨模型正确，避免IC误判 |
| P1 | R-LINK-001、R-LINK-002 | 支持同行联动和替代料挤占 |
| P1 | R-PRED-001、R-PRED-002 | 支持自进化验证 |
| P2 | R-UI-001 至 R-UI-004 | 前端增强，第一期可先做最小页面 |
