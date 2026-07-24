# 知识库操作日志

> 按时间倒序记录所有知识库操作。

---

## [2026-07-24 16:00] ingest | EXPERT-DIAGNOSIS.md + EXECUTION-HISTORY.md

- 新增原始资料：
  - `raw/articles/EXPERT-DIAGNOSIS.md` — 专家诊断报告完整原文
  - `raw/notes/EXECUTION-HISTORY.md` — 执行过程复盘

- 新增概念页面：
  - `wiki/concepts/five-level-mpn-matching.md` — 五级 MPN 匹配
  - `wiki/concepts/signal-origin.md` — 信号来源分类
  - `wiki/concepts/multi-factor-risk-engine.md` — 多因子风险引擎
  - `wiki/concepts/risk-event-bom-matches.md` — 风险事件-BOM 命中持久化表
  - `wiki/concepts/risk-lifecycle.md` — 风险生命周期

- 新增实体页面：
  - `wiki/entities/production-v1.md` — production-v1 生产版本
  - `wiki/entities/expert-diagnosis.md` — 专家诊断报告

- 更新索引：
  - `wiki/index.md` — 全局目录

- 关键发现：
  - 项目已完成从 V4 到 production-v1 的完整架构演进
  - 实现了专家诊断报告要求的所有 P0/P1 项（5/5 P0, 7/7 P1）
  - 建立了完整的风险评估体系（事实/推断双通道）
  - 具备生产级部署能力（PostgreSQL、Redis、Celery、监控告警）

---

## [2026-07-24 15:30] init | 知识库初始化

- 创建目录结构：
  - `raw/articles/` — 文章类原始资料
  - `raw/papers/` — 论文类原始资料
  - `raw/notes/` — 笔记类原始资料
  - `raw/assets/` — 图片等资产
  - `wiki/concepts/` — 概念类页面
  - `wiki/entities/` — 实体类页面
  - `wiki/comparisons/` — 对比分析页面
- 创建基础文件：
  - `wiki/index.md` — 全局目录
  - `wiki/log.md` — 操作日志
  - `CLAUDE.md` — Schema 配置