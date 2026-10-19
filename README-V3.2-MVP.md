# BOM Risk Analyzer v3.2 第一轮 MVP 补丁说明

本补丁实现 v3.2/v3.3 MVP 核心能力，覆盖后端独立服务模块、BOM 分析 API 行级字段、人工事件 API、BOM 分析页前端最小闭环，以及“行情情报收件箱”原文识别和历史 BOM 扫描闭环。

## 本轮实现范围

| Agent | 能力 | 新增模块 | 测试 |
|---|---|---|---|
| A1 | 高容MLCC识别与基础品类识别 | `backend/app/services/upstream/mlcc_classifier.py`、`category_classifier.py` | `tests/test_mlcc_classifier.py`、`tests/test_category_classifier.py` |
| A3 | 情报源可信度评分 | `backend/app/services/upstream/intelligence_scoring.py` | `tests/test_intelligence_scoring.py` |
| A4 | 最小双轨风险引擎 | `backend/app/services/upstream/dual_track_risk_engine.py`、`propagation_rules.py` | `tests/test_dual_track_risk_engine.py` |
| A2 | 人工事件结构化 | `backend/app/services/upstream/manual_event_service.py`、`backend/app/api/events.py` | `tests/test_manual_event_service.py` |
| A5 | 依据链生成 | `backend/app/services/upstream/evidence_chain_builder.py` | `tests/test_evidence_chain_builder.py` |
| 集成 | BOM分析行级v3.2字段 | `backend/app/services/upstream/risk_context_builder.py`、`backend/app/api/risk_analysis.py` | `tests/test_risk_analysis_v32_integration.py` |
| 前端 | BOM分析页v3.2风险展示和人工事件入口 | `frontend/src/components/V32EvidencePanel.vue`、`ManualEventQuickAdd.vue`、`RiskDetailTable.vue`、`frontend/src/views/BomAnalyze.vue` | `frontend/src/components/__tests__/V32EvidencePanel.test.js`、`ManualEventQuickAdd.test.js` |
| 演示 | 完整演示闭环 | `demo/sample-bom-v32.csv`、`scripts/start-demo.ps1`、`DEMO-V3.2.md` | `tests/test_v32_demo_loop.py` |
| v3.3 | 行情情报收件箱、原文保存、信号抽取、可信事件生成和历史 BOM 扫描 | `backend/app/services/upstream/market_notice_parser.py`、`market_inbox_service.py`、`backend/app/api/market_inbox.py`、`frontend/src/views/MarketInbox.vue` | `tests/test_market_notice_parser.py`、`tests/test_market_inbox_api.py`、`frontend/src/views/__tests__/MarketInbox.test.js`、`frontend/e2e/v33-market-inbox.spec.js` |

## 已验证行为

- `22uF 25V X7R 0805 MLCC`、`47uF 10V X5R 0603` 可识别为高容MLCC。
- `100nF 50V X7R 0603`、`10nF 50V C0G 0402` 不会误判为高容MLCC。
- 铝电解、电解、薄膜、钽电容不会因大容量被误判为MLCC。
- MCU、PCB、继电器可识别基础品类及主导风险驱动类型。
- 单一公众号传闻，若缺少品牌、型号、原始出处和交叉验证，只进入观察池，不触发高风险。
- 原厂涨价通知、采购人工确认的高容MLCC缺货涨价通知可按置信度触发高风险候选。
- 高容MLCC在供需紧张、涨价缺货确认时可升为橙色或红色风险。
- MCU 仅有硅片上涨时不会直接红色预警。
- PCB 铜箔/玻纤压力以材料传导轨为主。
- 安全库存会降低总风险分。
- BOM 分析页可展示 v3.2 风险等级、主导轨道、依据摘要、处置建议和依据链弹层。
- 采购/工程人员可在 BOM 分析页快速录入供应商涨价/缺货通知，提交后由后端可信度模型决定是否自动确认或进入观察。
- 导出 CSV 会包含 v3.2 品类、主导轨道、风险等级、评分、依据摘要和处置建议。
- 样例 BOM 可通过上传、人工事件录入和重分析跑通完整演示闭环。
- v3.2 人工事件品类（如 `high_cap_mlcc`）已桥接到 BOM 行级匹配和依据链。
- 浏览器端到端验收可自动完成样例 BOM 上传、人工行情事件录入、重新分析和页面关键结果校验。
- 行情情报收件箱可接收邮件、微信、公众号、官网或供应商通知原文，原文会保存到 `RawMarketNotice`，抽取结果会保存到 `ExtractedMarketSignal`。
- 高置信度且非传闻的信号会自动生成 `MarketEvent`，并扫描历史 BOM；社交传闻会被降权，保留为待复核或观察信号。
- 高容 MLCC 通知可抽取 `high_cap_mlcc`、品牌、型号、涨幅和交期，并通过 v3.3 品类桥接影响历史 BOM 行。
- 优选库治理独立窗口支持导入二三级优选库 Excel，对 BOM 输出优选命中、非优选、历史新料、禁用/限用/待评审和替代建议。
- 交期红色风险、确认缺货且交期超 12 周的物料自动进入临时禁选；中等风险或低置信度进入限选或观察。
- BOM 风险页和优选库治理页分开独立展示。

## 部署方法

在 PowerShell 中运行：

```powershell
powershell -ExecutionPolicy Bypass -File "d:\1项目清单\交期风险排查\BOM-Risk-Analyzer-patch\deploy-v3.2-mvp.ps1" -TargetProject "D:\软件\workbuddy\WorkBuddy\BOM-Risk-Analyzer"
```

脚本会复制新增模块和测试到 WorkBuddy 项目，并依次运行：

```powershell
py -3.11 -m py_compile backend\app\services\upstream\*.py
py -3.11 -m pytest tests\test_mlcc_classifier.py tests\test_category_classifier.py tests\test_intelligence_scoring.py tests\test_dual_track_risk_engine.py tests\test_manual_event_service.py tests\test_evidence_chain_builder.py tests\test_risk_analysis_v32_integration.py tests\test_v32_demo_loop.py tests\test_market_notice_parser.py tests\test_market_inbox_api.py -q
py -3.11 -m pytest tests -q
npm test -- --run
npm run build
```

## 当前限制

- 本轮没有自动爬取邮箱、微信、公众号或官网，只先支持用户手动粘贴/转发原文。
- v3.3 解析器先采用本地规则，不依赖 LLM；复杂 PDF、图片 OCR 和多附件邮件仍需后续扩展。
- 置信度模型已能区分官方/供应商事实与社交传闻，但更细的来源白名单、交叉验证和复核队列还未产品化。
- v3.2/v3.3 风险仍是 MVP 规则引擎，后续可加入更多真实 API、行情时间序列、预测验证和命中率统计。

## 下一轮建议

1. 做行情收件箱复核队列，让 `need_review` 信号可以由采购确认、驳回或补充证据。
2. 接入邮箱转发入口和附件解析，把邮件、PDF、图片 OCR 统一沉淀为 RawMarketNotice。
3. 将立创/华秋/贸泽/得捷/云汉等真实 API 数据源接入 v3.2 供需轨。
4. 增加行情趋势视图和预测验证记录，统计预警命中率和误报率。
5. 扩展 MarketEvents 页面，支持更完整的人工事件管理、复核和影响项目追踪。
