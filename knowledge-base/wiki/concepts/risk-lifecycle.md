---
title: "风险生命周期"
confidence: 0.95
last_ingested: 2026-07-24
sources:
  - raw/articles/EXPERT-DIAGNOSIS.md
stale: false
---

## 定义

风险生命周期是风险从产生到关闭的完整状态流转过程，包含 7 个状态和 14 种有效状态转换。

## 状态定义

| 状态 | 说明 |
|------|------|
| pending | 待审核：风险刚被识别，等待人工确认 |
| under_review | 审核中：分析师正在评估风险 |
| confirmed | 已确认：风险被确认，需要采取行动 |
| action_taken | 已处理：已采取应对措施 |
| monitoring | 监控中：处理后持续监控 |
| resolved | 已解决：风险已解除 |
| ignored | 已忽略：人工判定为误报或不关注 |

## 状态转换

```
pending → under_review → confirmed → action_taken → monitoring → resolved
    ↓                        ↓                              ↓
  ignored                  ignored                        ignored
```

## 处理动作类型

| 动作类型 | 说明 |
|----------|------|
| lock_stock | 锁定库存 |
| find_alternative | 寻找替代料 |
| negotiate_price | 价格协商 |
| update_forecast | 更新预测 |
| notify_customer | 通知客户 |
| wait_and_see | 观望 |
| escalate | 升级处理 |

## 实现位置

- `risk_lifecycle_service.py`：状态机实现
- `models/risk_action.py`：处理动作模型

## 关联概念

- [[multi-factor-risk-engine]]：多因子风险引擎
- [[risk-event-bom-matches]]：命中持久化表