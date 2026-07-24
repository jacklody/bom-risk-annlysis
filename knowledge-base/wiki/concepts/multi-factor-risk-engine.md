---
title: "多因子风险引擎"
confidence: 0.95
last_ingested: 2026-07-24
sources:
  - raw/articles/EXPERT-DIAGNOSIS.md
stale: false
---

## 定义

多因子风险引擎是 BOM 交期风险预警系统的核心评分引擎，替代了已废弃的双轨引擎，采用七因子加权评分模型。

## 七因子模型

| 因子 | 权重 | 说明 | 归属通道 |
|------|------|------|----------|
| market_trend | 15% | 市场行情趋势（原材料价格波动） | 推断 |
| supply_tension | 20% | 供应紧张程度（库存/交期/缺货） | 事实 |
| policy_compliance | 15% | 政策合规（BIS/USTR/实体清单/关税） | 事实 |
| disaster_zone | 10% | 灾害区域影响 | 推断 |
| bom_exposure | 15% | BOM 中用量占比 | 供应 |
| substitution_difficulty | 15% | 替代料可用性 | 供应 |
| confidence_adjustment | 10% | 置信度调整系数 | 调整 |

## 评分拆分

- **fact_score**：供应紧张 + 政策合规
- **supply_score**：BOM 暴露度 + 替代难度
- **inference_score**：市场趋势 + 灾害区域（封顶 35 分）

## 信号来源判定

```python
has_fact_signal = fact_score > 0 or (
    market_facts.get("price_up_confirmed")
    or market_facts.get("shortage_confirmed")
    or body_signals.get("stock_down")
    or lifecycle in ("EOL", "NRND", "OBSOLETE")
)
has_inference_signal = inference_raw > 0

if has_fact_signal and has_inference_signal:
    signal_origin = "mixed"
elif has_fact_signal:
    signal_origin = "factual"
elif has_inference_signal:
    signal_origin = "inferred"
```

## IC 类材料传导弱约束

```python
ic_material_only = (
    category in {"mcu", "power_ic", "mosfet", "power_module", "discrete_passive"}
    and has_inference_signal
    and not has_fact_signal
)
if ic_material_only:
    inference_score = min(inference_score, 34.0)
    total_score = min(total_score, 34.0)
    reason += "；IC类不能仅凭材料上涨直接红色预警"
```

## 替代方案

- **双轨引擎**（已废弃）：`dual_track_risk_engine.py`，职责重叠，多因子更完善（7因子 vs 2轨）

## 实现位置

- `multi_factor_risk_engine.py`：核心评分逻辑
- `risk_context_builder.py`：调用入口

## 关联概念

- [[signal-origin]]：信号来源分类
- [[five-level-mpn-matching]]：五级 MPN 匹配
- [[risk-lifecycle]]：风险生命周期