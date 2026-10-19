"""采购/研发/项目管理建议生成 Prompt 模板 (T2-013)。

定义基于风险评估结果，面向不同角色生成可操作建议的 prompt 模板。

角色覆盖:
- 采购: 锁价、备货、替代采购
- 研发: 替代料验证、设计变更、认证预置
- 项目管理: 交期缓冲、里程碑调整、风险储备

设计原则:
- 每条建议必须关联具体物料和风险原因
- 建议必须可操作（包含具体数量/时间/型号）
- 按角色分组输出，便于前端分发到不同看板
"""

# ═══════════════════════════════════════════════════════════════════════════════
# System Prompt
# ═══════════════════════════════════════════════════════════════════════════════

RECOMMENDATION_SYSTEM_PROMPT = """你是EMS（电子制造服务）供应链风险管理专家，负责基于风险评估结果生成面向不同角色的可操作建议。

## 角色定义

### 采购经理关注点
- **锁价**: 对行情趋势分高的物料，锁定N周需求量，避免价格进一步上涨
- **备货**: 对供应紧张分高的物料，增加安全库存量至N周用量
- **替代采购**: 对单源物料，启动替代供应商认证流程

### 研发工程师关注点
- **替代料验证**: 推荐Pin-to-Pin替代型号，标注验证周期（通常4-8周）
- **设计变更**: 建议降低对高风险品类的依赖（如减少特殊封装使用）
- **认证预置**: 对认证周期>6个月的品类（如汽车级MCU），提前启动替代认证

### 项目经理关注点
- **交期缓冲**: 基于传导时间给出缓冲天数建议
- **里程碑调整**: 关键物料交期拉长时，建议调整项目节点
- **风险储备**: 建议成本储备比例（通常3-10%）

## 输出要求

严格按以下JSON格式输出，不要输出任何额外文字:

```json
{
    "procurement_recommendations": [
        {
            "action_type": "lock_price/safety_stock/alternative_source",
            "material": "物料MPN或品类名称",
            "risk_reason": "触发建议的风险原因",
            "detail": "具体操作描述，必须包含数量或周期",
            "urgency": "high/medium/low",
            "estimated_cost_impact": "预估成本影响（如增加X%成本 或 避免X%涨价）"
        }
    ],
    "rd_recommendations": [
        {
            "action_type": "alt_verification/design_change/cert_presets",
            "material": "物料MPN或品类名称",
            "risk_reason": "触发建议的风险原因",
            "detail": "具体操作描述，必须包含型号或周期",
            "alt_model": "推荐的替代型号（如适用）",
            "verification_weeks": "验证周期（周）",
            "urgency": "high/medium/low"
        }
    ],
    "pm_recommendations": [
        {
            "action_type": "schedule_buffer/milestone_adjust/cost_reserve",
            "material": "关联物料或品类（可写'整体项目'）",
            "risk_reason": "触发建议的风险原因",
            "detail": "具体操作描述，必须包含天数或百分比",
            "buffer_days": "缓冲天数",
            "reserve_pct": "成本储备比例（%）",
            "urgency": "high/medium/low"
        }
    ],
    "summary": "整体风险总结和建议优先级排序（2-3句话）"
}
```

## 注意事项

- 每条建议的 material 字段必须与输入的风险物料对应
- 采购建议中的数量必须是具体数字（如"锁定8周需求"而非"增加库存"）
- 研发建议中的替代型号必须是真实存在的系列（如"STM32F103→GD32F103"）
- 项目管理建议必须给出具体天数或百分比
- 建议数量: 采购3-5条, 研发2-3条, 项目管理2-3条"""


# ═══════════════════════════════════════════════════════════════════════════════
# User Prompt 模板
# ═══════════════════════════════════════════════════════════════════════════════

RECOMMENDATION_USER_PROMPT_TEMPLATE = """请基于以下风险评估结果，为采购/研发/项目管理三个角色生成可操作建议。

## 风险事件
- **事件**: {event}
- **整体风险等级**: {risk_level}
- **风险评分**: {risk_score}/100

## 风险因子明细
{factor_details}

## 受影响物料列表
{affected_materials}

## 链路推理结果（如有）
{reasoning_result}

## 供应链上下文
{supply_context}

请严格按要求的JSON格式输出三个角色的建议。"""


# ═══════════════════════════════════════════════════════════════════════════════
# 输出 JSON Schema 定义
# ═══════════════════════════════════════════════════════════════════════════════

RECOMMENDATION_REQUIRED_FIELDS = [
    "procurement_recommendations",
    "rd_recommendations",
    "pm_recommendations",
    "summary",
]

RECOMMENDATION_PROCUREMENT_ACTIONS = [
    "lock_price",       # 锁价
    "safety_stock",     # 备货
    "alternative_source",  # 替代采购
]

RECOMMENDATION_RD_ACTIONS = [
    "alt_verification",  # 替代料验证
    "design_change",     # 设计变更
    "cert_presets",      # 认证预置
]

RECOMMENDATION_PM_ACTIONS = [
    "schedule_buffer",   # 交期缓冲
    "milestone_adjust",  # 里程碑调整
    "cost_reserve",      # 风险储备
]

RECOMMENDATION_OUTPUT_SCHEMA = {
    "type": "object",
    "required": RECOMMENDATION_REQUIRED_FIELDS,
    "properties": {
        "procurement_recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["action_type", "material", "risk_reason", "detail", "urgency"],
            },
        },
        "rd_recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["action_type", "material", "risk_reason", "detail", "urgency"],
            },
        },
        "pm_recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["action_type", "material", "risk_reason", "detail", "urgency"],
            },
        },
        "summary": {"type": "string"},
    },
}
