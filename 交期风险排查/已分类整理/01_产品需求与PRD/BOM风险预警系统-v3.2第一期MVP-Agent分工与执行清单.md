# BOM风险预警系统 v3.2 第一期 MVP Agent 分工与执行清单

> 目标：把 v3.2 第一阶段 MVP 拆成可交给不同 Agent 执行的任务包。每个任务包都包含职责、输入、输出、依赖、测试和验收标准。  
> 原则：一个 Agent 一次只处理一个边界清晰的任务，严禁“一次性实现整个系统”。

## 1. 第一阶段 MVP 目标

第一期 MVP 要打通一条完整业务链路：

```text
上传BOM
→ 识别高容MLCC、MCU、PCB等关键品类
→ 人工录入“高容MLCC涨价缺货”
→ 系统匹配历史BOM和当前BOM
→ 双轨风险引擎输出风险等级
→ 生成风险依据链
→ 保存预测验证记录
→ 前端最小展示
```

如果这条链路打通，v3.2 的方向即可被验证。

## 2. Agent 角色分工

| Agent | 类型 | 主要职责 | 是否写代码 |
|---|---|---|---|
| A0 需求守门 Agent | Plan / Explore | 维护需求矩阵，防止开发偏离 v3.2 | 否 |
| A1 品类识别 Agent | General Purpose | 实现品类识别和高容 MLCC 识别 | 是 |
| A2 人工事件 Agent | General Purpose | 实现人工录入涨价/缺货事件及 BOM 命中 | 是 |
| A3 情报可信度 Agent | General Purpose | 实现公众号/媒体/原厂/人工来源可信度评分 | 是 |
| A4 双轨风险 Agent | General Purpose | 实现材料传导轨、供需信号轨和高容 MLCC 风险模型 | 是 |
| A5 依据链 Agent | General Purpose | 实现风险依据链和信息不足状态 | 是 |
| A6 预测验证 Agent | General Purpose | 实现风险预测记录和后续验证结构 | 是 |
| A7 前端最小闭环 Agent | General Purpose | 实现人工录入页、风险轨道标识、依据链展示 | 是 |
| A8 验证 Agent | Explore / General Purpose | 跑测试、查遗漏、输出验收记录 | 不新增业务功能 |
| A9 Code Review Agent | Explore | 审查需求一致性、误报风险、可解释性 | 否 |

## 3. 执行顺序

```text
A0 → A1 → A2 → A3 → A4 → A5 → A6 → A7 → A8 → A9
```

A1–A6 是后端核心闭环，必须先完成。A7 可以在 A2–A5 接口基本稳定后开始。A8 和 A9 必须在每个阶段结束后执行。

## 4. A0 需求守门 Agent

### 职责

- 读取 v3.2 方案、开发过程保障方案、需求矩阵。
- 每次开发前确认任务是否有需求编号。
- 每次开发后确认需求矩阵是否被覆盖。

### 输入

```text
BOM物料风险预警系统-双轨情报与自进化方案-v3.2.md
BOM风险预警系统-v3.2开发过程保障方案.md
BOM风险预警系统-v3.2需求-模块-测试-验收矩阵.md
```

### 输出

```text
当前任务需求编号
允许开发/不允许开发判断
缺少的测试或验收标准
```

### 推荐提示词

```text
请作为需求守门 Agent，检查本次开发任务是否能映射到 v3.2 需求矩阵。输出需求编号、验收标准、必须覆盖的正例和反例。不写代码。
```

## 5. A1 品类识别 Agent

### 覆盖需求

```text
R-CAT-001
R-CAT-002
R-CAT-003
```

### 文件范围

```text
创建：backend/app/services/upstream/category_classifier.py
创建：backend/app/services/upstream/mlcc_classifier.py
创建：tests/test_category_classifier.py
创建：tests/test_mlcc_classifier.py
可能修改：backend/app/services/bom_parser.py
```

### 任务目标

- 识别常见品类：MCU、PMIC、功率器件、分立器件、PCB、继电器、连接器、电感、变压器、铝电解、MLCC。
- 识别高容 MLCC。
- 普通 MLCC 不能误判为高容 MLCC。

### 必须先写的测试

```python
def test_identifies_high_cap_mlcc_22uf_25v_0805():
    result = classify_mlcc("22uF 25V X7R 0805 MLCC")
    assert result.high_capacitance_flag is True
    assert result.capacitance == "22uF"
    assert result.voltage == "25V"
    assert result.dielectric == "X7R"
    assert result.package_size == "0805"


def test_does_not_mark_100nf_as_high_cap_mlcc():
    result = classify_mlcc("100nF 50V X7R 0603")
    assert result.high_capacitance_flag is False
```

### 验收标准

```text
pytest tests/test_mlcc_classifier.py -v 通过
pytest tests/test_category_classifier.py -v 通过
高容MLCC正例通过
普通MLCC反例通过
无法识别品类时返回 unknown 和信息不足原因
```

## 6. A2 人工事件 Agent

### 覆盖需求

```text
R-MANUAL-001
R-MANUAL-002
R-MANUAL-003
```

### 文件范围

```text
创建：backend/app/models/intelligence.py
创建：backend/app/api/manual_events.py
创建：backend/app/services/upstream/manual_event_service.py
创建：tests/test_manual_event_service.py
可能修改：backend/app/main.py
可能修改：backend/app/database.py
```

### 任务目标

- 支持人工录入涨价、缺货、交期延长、控单、产能紧张。
- 人工事件保存为结构化事件。
- 人工事件可以匹配 BOM 行。
- 人工事件会生成预测验证记录。

### 必须先写的测试

```python
def test_manual_high_cap_mlcc_event_matches_bom_items():
    event = ManualAlertInput(
        category="high_cap_mlcc",
        brand="Yageo",
        signal_type="price_up_shortage",
        affected_specs=["22uF", "47uF"],
        confidence=0.9,
    )
    bom_items = [
        FakeBomItem(id=1, description="22uF 25V X7R 0805 MLCC", brand="Yageo"),
        FakeBomItem(id=2, description="100nF 50V X7R 0603 MLCC", brand="Yageo"),
    ]

    result = match_manual_event_to_bom(event, bom_items)

    assert result.matched_item_ids == [1]
    assert result.unmatched_item_ids == [2]
```

### 验收标准

```text
人工录入事件可保存
高容MLCC事件能命中BOM中的高容MLCC
普通MLCC不被误命中
事件能生成预测验证记录
API返回命中BOM摘要
```

## 7. A3 情报可信度 Agent

### 覆盖需求

```text
R-INTEL-001
R-INTEL-002
R-INTEL-003
R-GATE-003
```

### 文件范围

```text
创建：backend/app/services/upstream/intelligence_scoring.py
创建：backend/app/api/intelligence.py
创建：tests/test_intelligence_scoring.py
可能修改：backend/app/models/intelligence.py
可能修改：backend/app/main.py
```

### 任务目标

- 区分官方、研究机构、行业媒体、公众号、渠道自媒体、人工来源。
- 根据来源可信度、字段完整度、多源验证、历史命中率计算情报可信度。
- 单一公众号传闻不能直接触发高风险。
- 原厂涨价函或授权代理通知可进入高可信候选。

### 必须先写的测试

```python
def test_single_wechat_rumor_without_fields_is_observation_only():
    event = IntelligenceEventInput(
        source_type="wechat",
        title="某类芯片即将涨价",
        category="ic",
        brand=None,
        increase_max_pct=None,
        original_source_url=None,
        cross_validation_count=0,
    )

    result = score_intelligence_event(event)

    assert result.review_recommendation == "observe"
    assert result.can_trigger_high_risk is False


def test_oem_price_notice_is_high_confidence():
    event = IntelligenceEventInput(
        source_type="official",
        title="原厂涨价通知",
        category="high_cap_mlcc",
        brand="Yageo",
        increase_max_pct=15,
        original_source_url="https://example.com/notice.pdf",
        cross_validation_count=1,
    )

    result = score_intelligence_event(event)

    assert result.review_recommendation in ["auto_confirm", "manual_confirm"]
    assert result.can_trigger_high_risk is True
```

### 验收标准

```text
单一公众号传闻不触发高风险
原厂/代理通知可进入确认事件
所有情报结果包含可信度和建议动作
```

## 8. A4 双轨风险 Agent

### 覆盖需求

```text
R-RISK-001
R-RISK-002
R-RISK-003
R-RISK-004
R-RISK-005
```

### 文件范围

```text
创建：backend/app/services/upstream/dual_track_risk_engine.py
创建：backend/app/services/upstream/propagation_rules.py
创建：tests/test_dual_track_risk_engine.py
可能修改：backend/app/services/supply_risk.py
```

### 任务目标

- 材料传导轨：PCB、继电器、连接器、电感、铝电解。
- 供需信号轨：MCU、PMIC、功率器件、高容 MLCC。
- 高容 MLCC 涨价缺货必须进入重点风险。
- MCU 不能因单一硅片涨价直接红色。
- 缓冲因子降低紧急程度。

### 必须先写的测试

```python
def test_high_cap_mlcc_shortage_becomes_orange_or_red():
    result = evaluate_dual_track_risk(
        category="high_cap_mlcc",
        body_signals={"stock_down": True, "lead_time_weeks": 16},
        market_facts={"price_up_confirmed": True, "shortage_confirmed": True},
        material_signals={"ceramic_powder_pressure": True},
        buffers={"safety_stock_days": 0},
    )

    assert result.risk_level in ["orange", "red"]
    assert result.primary_track == "demand_supply"
    assert "高容MLCC" in result.reason


def test_mcu_silicon_price_only_does_not_become_red():
    result = evaluate_dual_track_risk(
        category="mcu",
        body_signals={"stock_down": False, "lead_time_weeks": 8},
        market_facts={"price_up_confirmed": False},
        material_signals={"silicon_wafer_price_up": True},
        buffers={"safety_stock_days": 0},
    )

    assert result.risk_level != "red"
    assert result.primary_track != "material"
```

### 验收标准

```text
高容MLCC涨价缺货至少橙色
MCU仅材料上涨不能红色
PCB铜价传导可触发材料轨风险
风险结果包含 primary_track、risk_level、score、reason
```

## 9. A5 依据链 Agent

### 覆盖需求

```text
R-EVID-001
R-EVID-002
```

### 文件范围

```text
创建：backend/app/services/upstream/evidence_chain_builder.py
创建：tests/test_evidence_chain_builder.py
```

### 任务目标

- 每条风险输出依据链。
- 数据不足时输出信息不足。
- 输出结构可供前端展示。

### 必须先写的测试

```python
def test_builds_evidence_chain_for_high_cap_mlcc():
    chain = build_evidence_chain(
        item={"mpn": "TEST-MLCC", "description": "22uF 25V X7R 0805 MLCC"},
        risk_result={"risk_level": "orange", "primary_track": "demand_supply"},
        evidence=["高容MLCC涨价缺货", "库存下降", "交期16周"],
    )

    assert chain[0]["type"] == "bom_item"
    assert any(node["type"] == "market_fact" for node in chain)
    assert any(node["type"] == "suggestion" for node in chain)


def test_unknown_item_returns_insufficient_information():
    result = build_evidence_chain(
        item={"mpn": "", "description": "unknown"},
        risk_result=None,
        evidence=[],
    )

    assert result.information_status == "insufficient"
```

### 验收标准

```text
每条风险有依据链
未知物料返回信息不足
依据链包含 BOM行、事件、风险轨道、风险等级、建议动作
```

## 10. A6 预测验证 Agent

### 覆盖需求

```text
R-PRED-001
R-PRED-002
```

### 文件范围

```text
创建：backend/app/models/prediction.py
创建：backend/app/services/upstream/prediction_verifier.py
创建：backend/app/api/predictions.py
创建：tests/test_prediction_verifier.py
可能修改：backend/app/database.py
可能修改：backend/app/main.py
```

### 任务目标

- 风险预警生成预测验证记录。
- 支持 hit、partial_hit、miss、unverifiable。
- 后续可修正来源和联动规则命中率。

### 必须先写的测试

```python
def test_prediction_record_created_for_orange_risk():
    prediction = create_risk_prediction(
        bom_item_id=1,
        mpn="TEST-MLCC",
        category="high_cap_mlcc",
        risk_level="orange",
        expected_outcome="price_up_or_shortage",
        expected_window_days=60,
        model_version="v3.2",
        confidence=0.82,
    )

    assert prediction.verify_after is not None
    assert prediction.hit_result == "pending"


def test_verifies_prediction_as_hit_when_price_increases():
    result = verify_prediction(
        prediction={"expected_outcome": "price_up_or_shortage", "baseline_price": 1.0},
        actual={"current_price": 1.2, "stock_out": False},
    )

    assert result.hit_result == "hit"
```

### 验收标准

```text
橙色/红色风险生成预测记录
预测记录包含模型版本和验证窗口
验证后可更新命中状态
```

## 11. A7 前端最小闭环 Agent

### 覆盖需求

```text
R-UI-001
R-UI-002
R-UI-003
R-UI-004
```

### 文件范围

```text
创建：frontend/src/views/ManualEvents.vue
创建：frontend/src/views/IntelligenceReview.vue
创建：frontend/src/views/RiskEvidence.vue
创建：frontend/src/components/DualTrackRiskBadge.vue
创建：frontend/src/components/EvidenceChainPanel.vue
可能修改：frontend/src/router/index.js
可能修改：frontend/src/views/BomAnalyze.vue
```

### 任务目标

- 页面能录入人工行情事件。
- BOM分析页能显示风险轨道。
- 风险详情能显示依据链。
- 情报审核能显示来源可信度和建议动作。

### 验收标准

```text
用户能录入高容MLCC涨价缺货事件
页面返回命中BOM摘要
风险列表显示材料轨/供需轨
风险详情显示依据链、置信度和建议动作
```

## 12. A8 验证 Agent

### 职责

- 运行后端测试。
- 运行前端测试或构建。
- 检查需求矩阵覆盖情况。
- 输出验收记录。

### 必跑命令

```powershell
pytest tests/test_mlcc_classifier.py -v
pytest tests/test_category_classifier.py -v
pytest tests/test_manual_event_service.py -v
pytest tests/test_intelligence_scoring.py -v
pytest tests/test_dual_track_risk_engine.py -v
pytest tests/test_evidence_chain_builder.py -v
pytest tests/test_prediction_verifier.py -v
```

如前端测试环境具备：

```powershell
npm test
npm run build
```

### 验收输出

```text
通过测试：
失败测试：
覆盖需求编号：
未覆盖需求编号：
阻塞问题：
是否允许进入Code Review：是/否
```

## 13. A9 Code Review Agent

### 审查范围

- 所有新增后端服务。
- 所有新增 API。
- 所有新增测试。
- 前端最小页面。

### 审查重点

```text
是否符合 v3.2 需求矩阵
是否每个风险都有依据链
是否高容MLCC被单独处理
是否普通MLCC不误判
是否公众号传闻被降权
是否MCU材料传导被降权
是否人工事件可命中BOM
是否预测验证记录被保存
是否有硬编码品牌或临时逻辑
```

### 审查结论格式

```text
通过项：
问题项：
必须修改：
建议优化：
是否允许合并：是/否
```

## 14. 第一轮建议执行任务包

建议第一轮只派发三个 coding 任务，先打核心底座。

### 第一轮 Task 1

```text
A1 品类识别 Agent：实现高容MLCC识别和基础品类识别。
```

原因：高容 MLCC 是本轮用户明确强调的现实风险，必须先确保识别正确。

### 第一轮 Task 2

```text
A3 情报可信度 Agent：实现公众号/媒体/原厂/人工来源可信度评分。
```

原因：防止后续情报流进入系统时误报。

### 第一轮 Task 3

```text
A4 双轨风险 Agent：实现最小双轨风险引擎。
```

原因：验证“材料传导轨 + 供需信号轨”能否正确区分 PCB、高容 MLCC 和 MCU。

完成第一轮后再做人工触发、依据链、预测验证和前端页面。