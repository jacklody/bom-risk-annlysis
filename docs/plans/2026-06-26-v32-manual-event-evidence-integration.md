# v3.2 人工事件、依据链与BOM分析接入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 v3.2 第一轮算法能力进入 BOM 分析流程，支持人工事件结构化、依据链输出和行级 v3.2 风险字段。

**Architecture:** 复用现有 FastAPI + SQLAlchemy + SQLite 架构，不大改数据库。新增服务层 `manual_event_service.py` 和 `evidence_chain_builder.py`，复用 `category_classifier.py`、`intelligence_scoring.py`、`dual_track_risk_engine.py`，在 `risk_analysis.py` 中追加 v3.2 字段。

**Tech Stack:** Python 3.11、FastAPI、SQLAlchemy、pytest、SQLite。

## Global Constraints

- 不引入新第三方依赖。
- 使用 TDD：先写失败测试，再写实现。
- 不破坏现有 API 字段，只追加 v3.2 字段。
- 人工事件优先复用 `market_events` 表。
- 单一公众号传闻不得直接触发强预警。
- MCU/电源IC不得仅因硅片涨价直接红色预警。
- 每个 BOM 行风险必须能输出依据链数组和摘要。
- 每轮完成后运行 `py -3.11 -m pytest -q`。
- 同步更新补丁 Git 仓库和 bundle。

---

## Task 1: A2 人工事件服务

**Files:**
- Create: `backend/app/services/upstream/manual_event_service.py`
- Test: `tests/test_manual_event_service.py`

**Interfaces:**
- `build_market_event_from_manual_payload(payload: dict) -> dict`
- `extract_market_facts_from_events(events: list) -> dict`

Steps:
- [ ] 写失败测试：高容MLCC人工涨价缺货事件转为高置信 `MarketEvent` 数据。
- [ ] 写失败测试：从命中事件提取 `price_up_confirmed`、`shortage_confirmed`、`lead_time_weeks`。
- [ ] 实现最小服务。
- [ ] 运行 `py -3.11 -m pytest tests/test_manual_event_service.py -q`。

## Task 2: A5 依据链生成服务

**Files:**
- Create: `backend/app/services/upstream/evidence_chain_builder.py`
- Test: `tests/test_evidence_chain_builder.py`

**Interfaces:**
- `build_evidence_chain(item, category_result, matched_events, dual_track_result, realtime_data, buffers) -> EvidenceChainResult`

Steps:
- [ ] 写失败测试：高容MLCC风险输出品类、事件、双轨、供应、建议节点。
- [ ] 实现 `EvidenceChainResult` 和 `build_evidence_chain()`。
- [ ] 运行 `py -3.11 -m pytest tests/test_evidence_chain_builder.py -q`。

## Task 3: 接入人工事件 API

**Files:**
- Modify: `backend/app/api/events.py`
- Test: `tests/test_events_manual_v32.py`

Steps:
- [ ] 写失败测试：`/api/events/manual` 使用 v3.2 置信度，并保留 `status=ok/event` 返回。
- [ ] 修改 endpoint 调用 `build_market_event_from_manual_payload()`。
- [ ] 运行相关测试。

## Task 4: 接入 BOM 分析行级 v3.2 字段

**Files:**
- Modify: `backend/app/api/risk_analysis.py`
- Test: `tests/test_risk_analysis_v32_integration.py`

Expected new item fields:
- `v32_category`
- `v32_category_display`
- `v32_primary_track`
- `v32_track_scores`
- `v32_risk_level`
- `v32_risk_score`
- `v32_evidence_chain`
- `v32_evidence_summary`

Steps:
- [ ] 写 helper 级失败测试，验证高容MLCC可生成 v3.2 payload。
- [ ] 提取 `_build_v32_context()`。
- [ ] 修改 `_item_payload()` 追加 v3.2 字段。
- [ ] 运行集成测试。

## Task 5: 验证与Git移交

Steps:
- [ ] 运行 `py -3.11 -m pytest -q`。
- [ ] 提交补丁 Git 仓库。
- [ ] 重新生成 `BOM-Risk-Analyzer-v3.2-mvp.bundle`。
- [ ] 验证 bundle。
