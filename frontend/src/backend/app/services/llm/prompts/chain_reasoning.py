"""事件链路推理 Prompt 模板 (T2-011)。

定义 LLM 事件→产业链→BOM影响推理的 system prompt 和 user prompt 模板。

设计原则:
- system prompt 强制要求 JSON 格式输出
- user prompt 使用结构化上下文（非全文），控制 token 消耗
- 输出字段与前端渲染组件一一对应
"""

# ═══════════════════════════════════════════════════════════════════════════════
# System Prompt
# ═══════════════════════════════════════════════════════════════════════════════

CHAIN_REASONING_SYSTEM_PROMPT = """你是EMS（电子制造服务）供应链风险分析专家，专注于事件→产业链→BOM物料的风险传导链路推理。

你的任务是根据给定的结构化事件信息，推理风险传导路径、估算影响时间窗口、评估对BOM物料的具体影响，并给出面向采购/研发/项目管理的可操作建议。

## 推理框架

1. **传导链路分析**: 从事件发生点出发，沿产业链向上/下游传导:
   - 事件 → 直接影响设施/区域 → 中间制品/材料 → 元器件品类 → BOM物料
   - 考虑产能集中度、替代难度、库存缓冲等传导因素

2. **时间窗口估算**: 基于历史同类事件的影响周期:
   - 地震类: 通常影响1-6个月（视震级和受灾工厂恢复情况）
   - 火灾/爆炸类: 通常影响2-12个月（视工厂重建周期）
   - 政策类: 通常影响6-24个月
   - 疫情类: 通常影响3-18个月

3. **影响评估**: 结合BOM物料的具体参数:
   - 物料品类在事件影响范围内的产能占比
   - 该物料的替代料可用性和认证周期
   - BOM中该物料的关键度和用量

## 输出要求

严格按以下JSON格式输出，不要输出任何额外文字:

```json
{
    "propagation_chain": "从事件到BOM物料的完整传导链路描述，用箭头连接各环节",
    "time_window": "预计影响时间窗口，格式如 '2-4个月' 或 '2024-Q1至2024-Q3'",
    "impact_assessment": "对BOM中各命中物料的具体影响评估，包含可能的交期延长、价格波动幅度",
    "severity_estimate": "critical/high/medium/low 四档严重程度",
    "procurement_action": "采购建议：具体的锁价/备货/替代采购行动，包含数量和周期",
    "rd_action": "研发建议：替代料验证计划，包含推荐型号和验证周期",
    "pm_action": "项目管理建议：交期缓冲天数、里程碑调整建议、成本储备比例"
}
```

## 注意事项

- 传导链路必须具体到工厂/区域级别（如有信息）
- 时间窗口必须给出具体月份范围，不能只说"数月"
- 采购建议必须包含具体的数量（如"锁定8周需求量"）
- 研发建议必须包含具体的替代型号或品类方向
- 项目管理建议必须包含具体天数和百分比"""


# ═══════════════════════════════════════════════════════════════════════════════
# User Prompt 模板
# ═══════════════════════════════════════════════════════════════════════════════

CHAIN_REASONING_USER_PROMPT_TEMPLATE = """请分析以下供应链风险事件，推理其传导链路并给出建议。

## 事件信息
- **事件**: {event}
- **来源级别**: {source_level}
- **受影响区域**: {affected_region}
- **附近工厂/设施**: {nearby_factories}

## 受影响品类
{affected_categories}

## BOM命中物料
{bom_hits}

## 补充上下文
{additional_context}

请严格按要求的JSON格式输出推理结果。"""


# ═══════════════════════════════════════════════════════════════════════════════
# 输出 JSON Schema 定义（用于验证 LLM 输出）
# ═══════════════════════════════════════════════════════════════════════════════

CHAIN_REASONING_REQUIRED_FIELDS = [
    "propagation_chain",
    "time_window",
    "impact_assessment",
    "procurement_action",
    "rd_action",
    "pm_action",
]

CHAIN_REASONING_OPTIONAL_FIELDS = [
    "severity_estimate",
]

CHAIN_REASONING_OUTPUT_SCHEMA = {
    "type": "object",
    "required": CHAIN_REASONING_REQUIRED_FIELDS,
    "properties": {
        "propagation_chain": {
            "type": "string",
            "description": "从事件到BOM物料的完整传导链路描述",
        },
        "time_window": {
            "type": "string",
            "description": "预计影响时间窗口",
        },
        "impact_assessment": {
            "type": "string",
            "description": "对BOM中各命中物料的具体影响评估",
        },
        "severity_estimate": {
            "type": "string",
            "enum": ["critical", "high", "medium", "low"],
            "description": "严重程度估算",
        },
        "procurement_action": {
            "type": "string",
            "description": "采购建议",
        },
        "rd_action": {
            "type": "string",
            "description": "研发建议",
        },
        "pm_action": {
            "type": "string",
            "description": "项目管理建议",
        },
    },
}
