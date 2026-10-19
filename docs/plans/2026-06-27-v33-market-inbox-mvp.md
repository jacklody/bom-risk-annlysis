# v3.3 行情情报收件箱 MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用户只需粘贴或上传邮件涨价函、微信消息、公众号/官网通知原文，系统自动保存原始情报、抽取行情信号、生成 MarketEvent、扫描历史 BOM，并为历史趋势和未来预测保留数据框架。

**Architecture:** 在现有 `MarketEvent` 前增加两层数据：`RawMarketNotice` 保存原始通知，`ExtractedMarketSignal` 保存从原文抽取出的行情信号；确认后的信号再生成/复用现有 `MarketEvent` 供风险引擎使用。后端新增 `market_inbox` API 和 `market_notice_parser`/`market_inbox_service`，前端新增“行情收件箱”页面，部署脚本同步新增文件并运行后端/前端/E2E 验证。

**Tech Stack:** FastAPI、SQLAlchemy、SQLite、pytest、Vue 3、Vite、Element Plus、Axios、Vitest、Playwright、PowerShell。

## Global Constraints

- 本阶段不做邮箱自动监听、微信自动接收、公众号自动爬取、官网自动爬取、PDF/OCR、大模型抽取和预测模型。
- 用户不需要整理结构化数据；第一版必须支持粘贴非结构化原文并自动抽取。
- 原始通知必须留痕，后续解析规则升级后可重新解析历史原文。
- 低置信度或传闻类内容不得直接触发强风险，必须进入复核/观察状态。
- 本阶段只使用本地规则和已有置信度模型，不依赖公网 API。
- 所有新增能力必须可通过自动化测试验证，并通过现有 v3.2 demo/E2E 回归。

---

## File Structure

- Modify: `backend/app/models/event.py`
  - 新增 `RawMarketNotice` 与 `ExtractedMarketSignal` 模型。
  - 扩展 `MarketEvent.to_dict()` 返回标题和原文摘要，方便前端展示。
- Modify: `backend/app/database.py`
  - 轻量迁移 `raw_market_notices`、`extracted_market_signals` 表。
- Create: `backend/app/services/upstream/market_notice_parser.py`
  - 本地规则抽取品牌、品类、型号、涨价、交期、缺货、来源类型和置信度。
- Create: `backend/app/services/upstream/market_inbox_service.py`
  - 保存原始通知、调用 parser、生成信号、调用现有 `build_market_event_from_manual_payload()` 和 `EventCollector._save_event()`。
  - 导入后调用历史 BOM 扫描核心逻辑。
- Create: `backend/app/api/market_inbox.py`
  - 提供 `/api/market-inbox/submit`、`/api/market-inbox/`、`/api/market-inbox/{id}`。
- Modify: `backend/app/main.py`
  - 注册 `market_inbox.router`。
- Create: `tests/test_market_notice_parser.py`
  - 验证高容 MLCC 涨价函抽取和低置信度传闻降级。
- Create: `tests/test_market_inbox_api.py`
  - 验证粘贴原文 → 原始通知 → 信号 → MarketEvent → 历史 BOM 扫描影响摘要。
- Create: `frontend/src/api/marketInbox.js`
  - 前端 API 封装。
- Create: `frontend/src/views/MarketInbox.vue`
  - 行情收件箱页面。
- Modify: `frontend/src/router/index.js`
  - 增加 `/market-inbox` 路由。
- Modify: `frontend/src/App.vue`
  - 增加“行情收件箱”菜单入口。
- Create: `frontend/src/views/__tests__/MarketInbox.test.js`
  - 验证页面提交原文并渲染识别/扫描结果。
- Modify: `frontend/e2e/v32-demo-loop.spec.js` or create `frontend/e2e/v33-market-inbox.spec.js`
  - 增加最小浏览器验收：进入收件箱，粘贴高容 MLCC 通知，识别并展示结果。
- Modify: `deploy-v3.2-mvp.ps1`
  - 同步 v3.3 后端、前端、测试和文档。
- Modify: `DEMO-V3.2.md`、`README-V3.2-MVP.md`、`GIT-HANDOFF.md`
  - 追加 v3.3 收件箱说明。

---

## Task 1: 后端模型和迁移

**Files:**
- Modify: `backend/app/models/event.py`
- Modify: `backend/app/database.py`
- Test: `tests/test_market_notice_parser.py` later consumes these models indirectly.

**Interfaces:**
- Produces: SQLAlchemy models `RawMarketNotice`、`ExtractedMarketSignal`。
- Produces: `RawMarketNotice.to_dict()`、`ExtractedMarketSignal.to_dict()`。

Implementation notes:
- `RawMarketNotice` fields: `id`, `source_type`, `source_name`, `source_url`, `received_at`, `title`, `raw_text`, `raw_file_name`, `raw_file_hash`, `sender`, `parse_status`, `created_at`, `updated_at`。
- `ExtractedMarketSignal` fields: `id`, `raw_notice_id`, `market_event_id`, `brand`, `category`, `mpn`, `series`, `event_type`, `increase_min_pct`, `increase_max_pct`, `lead_time_weeks`, `shortage_confirmed`, `effective_date_text`, `confidence`, `confidence_reason`, `evidence_text`, `review_status`, `created_at`。
- `parse_status`: `pending/parsed/need_review/failed`。
- `review_status`: `auto_confirmed/need_review/observation/rejected`。

---

## Task 2: 本地行情通知解析器

**Files:**
- Create: `backend/app/services/upstream/market_notice_parser.py`
- Test: `tests/test_market_notice_parser.py`

**Interfaces:**
- Produces dataclass `ParsedMarketSignal`。
- Produces function `parse_market_notice(raw_text: str, title: str = '', source_type: str = 'manual', source_name: str = '') -> list[ParsedMarketSignal]`。

Required behavior:
- 高容 MLCC 文本 `TDK 高容MLCC C3225X5R1A226M250AC 缺货，预计涨价 10%-20%，交期延长至 16 周` 抽取：`brand=TDK`、`category=high_cap_mlcc`、`mpn=C3225X5R1A226M250AC`、`increase_min_pct=10`、`increase_max_pct=20`、`lead_time_weeks=16`、`shortage_confirmed=True`、`event_type=price_increase`、`confidence>=0.8`、`review_status=auto_confirmed`。
- 微信/公众号传闻文本 `群里说MLCC可能要涨价` 抽取为 `category=MLCC` 或 `high_cap_mlcc`，但 `confidence<0.8` 且 `review_status` 为 `need_review` 或 `observation`，不得自动高风险。

---

## Task 3: 收件箱服务和 API

**Files:**
- Create: `backend/app/services/upstream/market_inbox_service.py`
- Create: `backend/app/api/market_inbox.py`
- Modify: `backend/app/main.py`
- Test: `tests/test_market_inbox_api.py`

**Interfaces:**
- API `POST /api/market-inbox/submit`
  - Request: `{title, raw_text, source_type, source_name, source_url, sender, auto_scan}`。
  - Response: `{notice, signals, events_created, events_skipped, scan_summary}`。
- API `GET /api/market-inbox/`
  - Response: `{total, notices}`。
- API `GET /api/market-inbox/{notice_id}`
  - Response: `{notice, signals}`。

Required behavior:
- 保存原始通知。
- 解析多条信号。
- 对 `auto_confirmed` 或 `need_review` 但高置信事实信号，生成 `MarketEvent`。
- 对 `observation` 信号只留痕，不生成高风险事件。
- `auto_scan=True` 时调用历史 BOM 分析能力并返回影响摘要。

---

## Task 4: 前端行情收件箱页面

**Files:**
- Create: `frontend/src/api/marketInbox.js`
- Create: `frontend/src/views/MarketInbox.vue`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/App.vue`
- Test: `frontend/src/views/__tests__/MarketInbox.test.js`

**Interfaces:**
- `submitMarketNotice(payload)` 调用 `/market-inbox/submit`。
- 页面 test ids:
  - `market-inbox-page`
  - `market-notice-title`
  - `market-notice-source-type`
  - `market-notice-source-name`
  - `market-notice-raw-text`
  - `market-notice-submit`
  - `market-inbox-result`

Required behavior:
- 用户粘贴原文，一键识别并扫描。
- 展示原始通知保存状态、识别信号、置信度、是否自动确认、影响项目数和关键影响物料。

---

## Task 5: E2E、部署脚本、文档和移交

**Files:**
- Create: `frontend/e2e/v33-market-inbox.spec.js`
- Modify: `scripts/e2e-browser-demo.ps1`
- Modify: `deploy-v3.2-mvp.ps1`
- Modify: `DEMO-V3.2.md`
- Modify: `README-V3.2-MVP.md`
- Modify: `GIT-HANDOFF.md`

Required verification:
- `py -3.11 -m pytest tests/test_market_notice_parser.py tests/test_market_inbox_api.py -q`
- `py -3.11 -m pytest tests -q`
- `npm test -- --run`
- `npm run build`
- `powershell -ExecutionPolicy Bypass -File .\scripts\e2e-browser-demo.ps1`

---

## Self-Review

- Spec coverage: 覆盖一键粘贴/上传原始通知、原始留痕、抽取信号、生成 MarketEvent、历史 BOM 扫描、前端入口、测试和部署。
- Placeholder scan: 无 TBD/TODO/稍后实现占位。
- Type consistency: `RawMarketNotice`、`ExtractedMarketSignal`、`ParsedMarketSignal`、API 路径和 test ids 在各任务中保持一致。
- Scope check: 未纳入邮箱监听、微信自动接收、公众号/官网爬取、PDF/OCR、大模型和预测模型，符合本阶段 MVP 边界。
