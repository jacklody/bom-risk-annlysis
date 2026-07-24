---
title: "信号来源分类"
confidence: 0.95
last_ingested: 2026-07-24
sources:
  - raw/articles/EXPERT-DIAGNOSIS.md
stale: false
---

## 定义

信号来源分类是将风险信号分为事实通道和推断通道的机制，用于区分风险的可信度和来源类型。

## 分类规则

| 类型 | 说明 | 置信度 | 风险等级上限 |
|------|------|--------|-------------|
| **factual** | 事实信号，有直接事件/数据支撑 | 高 | 无上限（可触发 RED） |
| **inferred** | 推断信号，仅原材料传导推断 | 低→中 | 黄色（35分） |
| **mixed** | 混合信号，两者都有 | 综合 | 取事实通道等级 |

## 事实通道信号来源

- 原厂涨价函 / PCN / EOL / LTB
- 分销商数据：库存=0 / 交期>12周 / 生命周期=EOL
- 授权代理商缺货通知
- 人工确认事件

## 推断通道信号来源

- 原材料价格异动（铜+8% / 镍+15% / 银+12%）
- 灾害事件（台湾地震→TSMC 工厂受影响）
- 行业供需情报（"被动元件整体供需紧张"）

## 核心约束

- **推断风险封顶黄色**：推断通道信号最高不超过黄色（35分）
- **IC 类材料传导弱约束**：MCU/Power IC/MOSFET 等品类仅靠材料上涨时，风险最高限制为黄色
- **事实优先**：两者同时存在时，事实通道等级优先

## 评分拆分

```
fact_score       事实风险分（供应紧张 + 政策合规）
supply_score     实时供应分（BOM暴露度 + 替代难度）
inference_score  推断传导分（行情趋势 + 灾害区域，封顶35分）

final_level = max(fact_level, supply_level, capped_inference_level)
```

## 实现位置

- `multi_factor_risk_engine.py`：计算三个评分通道
- `risk_match.py`：`signal_origin` 字段持久化
- `risk_analysis.py`：API 层信号分类和封顶

## 关联概念

- [[five-level-mpn-matching]]：五级 MPN 匹配
- [[multi-factor-risk-engine]]：多因子风险引擎
- [[risk-event-bom-matches]]：命中持久化表