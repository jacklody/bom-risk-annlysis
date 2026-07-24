# BOM风险预警系统 v3.2 开发过程保障方案

> 目标：把 v3.2 方案转化为可被 Agent 执行、可被测试验证、可被业务验收的开发架构，避免代码实现偏离真实需求。  
> 适用项目：`BOM-Risk-Analyzer` 现有 FastAPI + Vue 项目。  
> 核心约束：所有新增功能必须先有需求编号、测试样例、验收标准，再进入代码实现。

## 1. 开发保障总原则

v3.2 不是普通功能迭代，而是把 BOM 风险系统升级成“材料传导轨 + 供需信号轨 + 情报可信度 + 人工触发 + 自进化验证”的电子供应链情报系统。开发过程必须从一开始就防止三类问题：

1. 代码能跑，但不符合业务需求。
2. 风险评分有结果，但没有依据链和可解释性。
3. 模型看似完整，但无法用测试样例证明高容 MLCC、MCU、PCB、公众号情报等关键场景判断正确。

因此后续开发采用四层保障：

```text
需求矩阵层
→ 每个功能绑定需求编号、业务来源、验收标准

TDD测试层
→ 每个核心判断先写失败测试，再实现代码

Agent分工层
→ 探索、计划、编码、验证、审查分离

交付门禁层
→ 没有测试、没有依据链、没有验收记录，不允许标记完成
```

## 2. 推荐 Agent 架构

### 2.1 Explore Agent

职责：只读分析，不改代码。

适合任务：

- 读取现有 `BOM-Risk-Analyzer` 代码。
- 找出已有模块和缺口。
- 对照 v3.2 判断哪些文件要改、哪些文件要新增。
- 调研外部平台、行情源、公众号情报规则。

产出：

```text
现有能力清单
可复用文件清单
缺失模块清单
建议新增文件和测试文件清单
```

使用时机：

- 每个大模块开发前。
- 接入新数据源前。
- 不清楚现有代码能力时。

### 2.2 Plan Agent

职责：写实施计划，不写生产代码。

适合任务：

- 把 v3.2 方案拆成开发任务。
- 设计数据库、服务、API、前端页面、测试。
- 明确每个任务的输入、输出、依赖、验收标准。

产出：

```text
实施计划
文件改动清单
接口设计
测试设计
验收门禁
```

使用时机：

- 开始一个新阶段前。
- 开始一个相对独立模块前。

### 2.3 General Purpose Coding Agent

职责：按单个模块实现代码。

使用规则：

- 每次只实现一个边界清晰的模块。
- 必须先看需求编号和测试样例。
- 不允许一次性实现整个 v3.2。
- 不允许修改测试期望来适配错误代码。

适合模块：

```text
高容MLCC识别
人工触发行情事件
情报源可信度模型
双轨风险引擎
同行联动规则
预测验证记录
前端风险依据链展示
```

### 2.4 Verification Agent

职责：独立验证，不新增业务功能。

验证内容：

- 测试是否通过。
- 需求矩阵是否覆盖。
- 反例是否防止误报。
- 输出是否包含风险依据链。
- 高容 MLCC、MCU、PCB、公众号情报等核心场景是否符合预期。

### 2.5 Code Review Agent

职责：交付前审查质量和需求一致性。

审查重点：

- 是否硬编码特定品牌或型号。
- 是否把公众号传闻直接当强证据。
- 是否把 IC 类材料传导权重写得过高。
- 是否区分材料传导轨和供需信号轨。
- 是否保留信息不足状态。
- 是否记录预测验证数据。

## 3. 必用 Skill 组合

### 3.1 writing-plans

用途：每个阶段开始前生成计划。

强制要求：

- 每个开发任务必须绑定需求编号。
- 每个任务必须有测试样例。
- 每个任务必须有验收标准。

### 3.2 test-driven-development

用途：所有风险判断、识别规则、评分模型都必须测试先行。

强制要求：

```text
先写失败测试
确认测试失败原因正确
再写最小实现
再确认测试通过
```

适用模块：

- 高容 MLCC 识别。
- MCU 供需驱动判断。
- PCB 材料传导判断。
- 公众号情报降权。
- 人工触发命中 BOM。
- 同行联动。

### 3.3 systematic-debugging

用途：测试失败或结果异常时使用。

适用问题：

```text
普通MLCC被误判为高容MLCC
MCU因硅片涨价被误判红色
人工录入事件没有命中BOM
公众号传闻直接触发高风险
同行联动导致过度误报
```

### 3.4 verification-before-completion

用途：任何模块完成前必须使用。

完成声明前必须回答：

```text
跑了哪些测试
测试结果是什么
覆盖了哪些需求编号
哪些需求还没有覆盖
是否存在已知限制
```

### 3.5 requesting-code-review

用途：模块合并前使用。

重点检查：

- 需求一致性。
- 风险评分可解释性。
- 数据模型扩展是否合理。
- 测试是否覆盖反例。
- 前端是否展示依据链。

### 3.6 research-guide

用途：接入第三方平台、行业媒体、公众号、行情来源时使用。

规则：

- 不把单一来源作为强结论。
- 区分官方、研究机构、行业媒体、公众号、渠道传闻。
- 任何行情事实必须保留来源和置信度。

## 4. 开发执行主流程

```text
读取需求文档
→ 生成需求-模块-测试-验收矩阵
→ Explore Agent 分析现有代码
→ Plan Agent 生成模块实施计划
→ TDD 编写测试
→ Coding Agent 实现模块
→ Verification Agent 跑测试和需求验收
→ Code Review Agent 审查
→ 记录交付状态和未覆盖项
```

每个模块的标准交付物：

```text
代码文件
测试文件
接口说明
验收记录
已知限制
下一步建议
```

## 5. 代码目录规划

基于现有项目，v3.2 建议新增或扩展以下目录。

### 5.1 后端服务目录

```text
backend/app/services/upstream/
├─ category_classifier.py       # 品类识别，高容MLCC识别，驱动类型判断
├─ mlcc_classifier.py           # 高容MLCC专项识别
├─ propagation_rules.py         # 材料传导规则、转嫁率、滞后时间
├─ dual_track_risk_engine.py    # 材料传导轨 + 供需信号轨融合评分
├─ intelligence_scoring.py      # 公众号/媒体/人工情报可信度
├─ manual_event_service.py      # 人工录入涨价缺货事件
├─ linkage_engine.py            # 同行联动、替代料挤占、配套物料联动
├─ evidence_chain_builder.py    # 风险依据链生成
└─ prediction_verifier.py       # 预测验证闭环
```

### 5.2 后端模型目录

```text
backend/app/models/intelligence.py
backend/app/models/upstream.py
backend/app/models/prediction.py
```

对应实体：

```text
intelligence_sources
market_intelligence_events
manual_alert_events
linkage_rules
mlcc_risk_profiles
risk_predictions
propagation_rules
category_risk_models
```

### 5.3 后端 API 目录

```text
backend/app/api/intelligence.py      # 情报源、公众号/媒体事件、审核池
backend/app/api/manual_events.py     # 人工触发涨价缺货事件
backend/app/api/upstream_risk.py     # v3.2 风险依据链查询
backend/app/api/predictions.py       # 预测验证记录和命中率
```

### 5.4 测试目录

```text
tests/test_mlcc_classifier.py
tests/test_category_classifier.py
tests/test_dual_track_risk_engine.py
tests/test_intelligence_scoring.py
tests/test_manual_event_service.py
tests/test_linkage_engine.py
tests/test_evidence_chain_builder.py
tests/test_prediction_verifier.py
tests/test_risk_analysis_v32.py
```

### 5.5 前端目录

```text
frontend/src/views/ManualEvents.vue       # 人工触发预警
frontend/src/views/IntelligenceReview.vue # 情报审核池
frontend/src/views/RiskEvidence.vue       # 风险依据链详情
frontend/src/views/PredictionReview.vue   # 预测验证看板
frontend/src/components/DualTrackRiskBadge.vue
frontend/src/components/EvidenceChainPanel.vue
frontend/src/components/IntelligenceSourceBadge.vue
```

## 6. 交付门禁

### 6.1 模块级门禁

任一模块必须满足以下条件才算完成：

| 门禁 | 要求 |
|---|---|
| 需求绑定 | 至少绑定一个需求编号 |
| 测试先行 | 新增核心逻辑必须有失败测试记录 |
| 正例覆盖 | 至少一个业务正例 |
| 反例覆盖 | 至少一个防误报反例 |
| 依据链 | 风险结果必须说明原因 |
| 信息不足 | 数据不足时不能强行输出低风险 |
| 回归测试 | 现有测试不能被破坏 |

### 6.2 阶段级门禁

第一期 MVP 完成时必须满足：

```text
BOM上传和解析正常
高容MLCC能识别
普通MLCC不会误判
人工涨价缺货事件能录入
人工事件能命中历史BOM
公众号传闻不能直接高风险
PCB铜价传导能触发风险
MCU单独硅片涨价不能触发红色风险
每条预警有依据链和置信度
预测记录能保存
```

## 7. Agent 执行提示模板

### 7.1 Explore Agent 模板

```text
请只读分析当前 BOM-Risk-Analyzer 项目。目标是实现 v3.2 的【模块名称】。请输出：已有可复用文件、需要新增文件、需要修改文件、测试文件建议、潜在风险。不允许修改代码。
```

### 7.2 Plan Agent 模板

```text
请基于 v3.2 需求和现有代码，为【模块名称】生成实施计划。要求包含文件清单、接口设计、测试用例、验收标准和执行顺序。必须采用 TDD。
```

### 7.3 Coding Agent 模板

```text
请实现【模块名称】。必须先编写测试并确认失败，再实现最小代码通过测试。不得修改测试期望来适配实现。完成后返回改动文件、测试命令、测试结果和已覆盖需求编号。
```

### 7.4 Verification Agent 模板

```text
请独立验证【模块名称】是否符合 v3.2 需求。重点检查测试、反例、风险依据链、信息不足状态和需求矩阵覆盖。不新增业务功能，只输出验证结论和问题清单。
```

### 7.5 Code Review Agent 模板

```text
请审查【模块名称】代码。重点检查：是否符合 v3.2 需求，是否存在硬编码，是否过度信任公众号传闻，是否误用材料传导解释 IC 风险，是否保留预测验证记录。
```

## 8. 第一阶段建议执行顺序

第一阶段不要同时铺开所有 v3.2 能力，先做最能验证系统方向的闭环。

```text
1. 需求矩阵和验收标准
2. 高容MLCC识别
3. 人工触发涨价缺货事件
4. 情报源可信度模型
5. 双轨风险引擎最小版
6. 风险依据链输出
7. 预测验证记录
8. 前端最小展示
9. 全链路验收
```

## 9. 最终交付标准

第一期 MVP 交付时，系统至少可以完成以下链路：

```text
上传BOM
→ 识别高容MLCC、MCU、PCB、继电器等品类
→ 人工录入“高容MLCC涨价缺货”
→ 系统匹配历史BOM和新BOM
→ 输出风险等级、驱动轨道、依据链、置信度、建议动作
→ 保存预测验证记录
→ 后续根据价格/库存/交期变化校准规则
```

如果这条链路打通，v3.2 的核心价值就被验证；后续再扩展更多数据源、公众号自动采集、Sub-tier 图谱和商业平台能力借鉴。