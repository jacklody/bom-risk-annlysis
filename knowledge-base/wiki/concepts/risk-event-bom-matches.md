---
title: "风险事件-BOM 命中持久化表"
confidence: 0.95
last_ingested: 2026-07-24
sources:
  - raw/articles/EXPERT-DIAGNOSIS.md
stale: false
---

## 定义

风险事件-BOM 命中持久化表（`risk_event_bom_matches`）是用于记录风险事件与 BOM 物料匹配关系的持久化存储，支持风险的可追溯、可复盘、可确认。

## 表结构

| 字段 | 说明 |
|------|------|
| id | 主键 |
| event_id | 风险事件 ID |
| bom_project_id | BOM 项目 ID |
| bom_item_id | BOM 行 ID |
| match_level | 匹配等级（exact_mpn / normalized_mpn / series / brand_category / category_spread） |
| match_confidence | 匹配置信度（0-1） |
| match_reason | 命中说明 |
| signal_origin | 信号来源（factual / inferred / mixed） |
| risk_level | 本次映射后的风险等级 |
| evidence_snapshot | 当时证据快照（JSON） |
| created_at | 创建时间 |
| reviewed_status | 人工确认状态（pending / confirmed / ignored） |
| reviewed_by | 人工确认人 |

## 核心价值

1. **可解释**：为什么这颗料被预警？哪个事件命中了它？
2. **可复盘**：当时证据是什么？
3. **可确认**：人工是否确认？事件关闭后是否自动解除？
4. **可追溯**：什么时候变红的？之前是什么颜色？

## 写入时机

- `analyze_bom`：单个 BOM 分析时写入
- `analyze_all_projects`：批量分析所有项目时写入

## 实现位置

- `risk_match.py`：数据库模型定义
- `event_bom_match_service.py`：持久化服务实现

## 关联概念

- [[five-level-mpn-matching]]：五级 MPN 匹配
- [[signal-origin]]：信号来源分类
- [[risk-lifecycle]]：风险生命周期