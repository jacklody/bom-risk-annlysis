---
title: "五级 MPN 匹配"
confidence: 0.95
last_ingested: 2026-07-24
sources:
  - raw/articles/EXPERT-DIAGNOSIS.md
stale: false
---

## 定义

五级 MPN 匹配是 BOM 交期风险预警系统中用于将风险事件映射到具体 BOM 型号的分层匹配策略，从高置信度到低置信度分为 L1-L5 五个等级。

## 匹配等级

| 等级 | 名称 | 示例 | 可信度 | 建议风险动作 |
|------|------|------|--------|-------------|
| **L1** | 精确 MPN | 通知 `STM32F103C8T6`，BOM 同型号 | 0.95 | 直接打事实风险 |
| **L2** | 规格化 MPN | 通知 `STM32F103C8T6TR`，BOM `STM32F103C8T6` | 0.90 | 直接打事实风险 |
| **L3** | 系列/前缀 | 通知 `STM32F103 系列`，BOM `STM32F103C8T6` | 0.75 | 高关注，必要时人工确认 |
| **L4** | 品牌+品类 | 通知 `ST MCU 涨价`，BOM `ST + MCU` | 0.55 | 标记为潜在影响（**不触发 RED**） |
| **L5** | 品类波及 | 通知 `MCU 缺货`，波及 `电源IC/模拟IC` | 0.30 | 仅展示观察信号 |

## 关键约束

- **L4 低置信度匹配**：根据专家诊断报告要求，L4（品牌+品类匹配，置信度 0.55）不应直接触发 RED 告警，最高为 ORANGE
- **IC 类材料传导弱约束**：MCU/Power IC/MOSFET 等品类仅靠材料上涨时，风险最高限制为黄色

## 实现位置

- `part_matcher.py`：实现 L1-L3 匹配
- `bom_matcher.py`：集成五级匹配并映射风险等级

## 关联概念

- [[signal-origin]]：信号来源分类
- [[risk-event-bom-matches]]：命中持久化表
- [[multi-factor-risk-engine]]：多因子风险引擎