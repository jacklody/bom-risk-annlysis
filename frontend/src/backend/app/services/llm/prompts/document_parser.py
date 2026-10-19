"""文档解析 Prompt 模板 (T2-012)。

定义 LLM 从非结构化文档（供应商涨价函、缺货通知、行业报告PDF）中
提取结构化风险事件的 system prompt 和 user prompt 模板。

设计原则:
- system prompt 强制要求 JSON 格式输出，并给出完整的输出 schema
- user prompt 包含文档文本和可选的文档类型提示
- 输出字段与前端事件卡片渲染一一对应
"""

# ═══════════════════════════════════════════════════════════════════════════════
# System Prompt
# ═══════════════════════════════════════════════════════════════════════════════

DOCUMENT_PARSER_SYSTEM_PROMPT = """你是EMS（电子制造服务）供应链风险情报分析专家，专注于从非结构化文档中提取结构化的供应链风险事件。

你可以处理以下类型的文档：
- 供应商涨价函：供应商发布的产品调价通知
- 缺货通知：供应商发出的交期延长或暂停供货通知
- 行业报告：第三方机构发布的供应链分析/预警报告
- 其他：其他可能包含供应链风险信息的文档

## 事件类型定义

- price_increase: 涨价事件，包含涨价幅度、生效日期、受影响品类
- shortage: 缺货/供应紧张事件，交期延长或配额限制
- supply_disruption: 供应中断事件，工厂停产/产线故障等
- natural_disaster: 自然灾害事件，地震/台风/洪水等影响供应链
- policy_change: 政策法规变化，出口管制/关税调整/环保政策等

## 影响等级定义

- high: 高影响，供应严重受限或涨幅超过10%，可能影响多条产品线
- medium: 中等影响，部分品类交期延长或涨幅3-10%
- low: 低影响，小幅波动或影响范围有限

## 输出要求

严格按以下JSON格式输出，不要输出任何额外文字：

```json
{
    "events": [
        {
            "event_type": "price_increase|shortage|supply_disruption|natural_disaster|policy_change",
            "title": "事件标题（简洁概括事件）",
            "description": "事件详细描述（包含背景、原因、影响范围）",
            "affected_categories": ["受影响的产品品类列表"],
            "affected_manufacturers": ["受影响的厂商/品牌列表"],
            "effective_date": "生效日期，格式YYYY-MM-DD，无法确定则为null",
            "impact_level": "high|medium|low",
            "price_change_pct": 涨价幅度百分比（数字），非涨价事件为null,
            "confidence": 0.0到1.0的置信度,
            "evidence_text": "原文中支撑该事件的关键段落摘录"
        }
    ],
    "doc_summary": "文档整体内容摘要（2-3句话）",
    "doc_type_classified": "auto识别出的文档类型：price_increase|shortage|report|other"
}
```

## 注意事项

- 每个独立事件单独列出，一份文档可能包含多个事件
- affected_categories 必须具体到品类（如"MLCC"、"MCU"），不能笼统写"电子元器件"
- price_change_pct 仅对涨价事件填写，其他类型为null
- confidence 根据文本明确程度评估：明确声明>0.8，推断得出0.5-0.8，模糊提及<0.5
- evidence_text 必须是文档原文的直接摘录，不能改写或概括
- 如果文档不包含任何供应链风险事件，events 返回空数组，仍需填写 doc_summary 和 doc_type_classified
- doc_type_classified 自动识别文档类型，即使指定了文档类型提示"""


# ═══════════════════════════════════════════════════════════════════════════════
# User Prompt 模板
# ═══════════════════════════════════════════════════════════════════════════════

DOCUMENT_PARSER_USER_PROMPT_TEMPLATE = """请分析以下文档内容，提取其中包含的供应链风险事件。

## 文档类型提示
{doc_type_hint}

## 文档内容
{doc_content}

请严格按要求的JSON格式输出分析结果。如果文档不包含供应链风险事件，events返回空数组。"""


# ═══════════════════════════════════════════════════════════════════════════════
# 输出 JSON Schema 定义（用于验证 LLM 输出）
# ═══════════════════════════════════════════════════════════════════════════════

DOCUMENT_PARSER_REQUIRED_FIELDS = [
    "events",
    "doc_summary",
    "doc_type_classified",
]

DOCUMENT_PARSER_EVENT_FIELDS = [
    "event_type",
    "title",
    "description",
    "affected_categories",
    "affected_manufacturers",
    "impact_level",
    "confidence",
    "evidence_text",
]

DOCUMENT_PARSER_VALID_EVENT_TYPES = [
    "price_increase",
    "shortage",
    "supply_disruption",
    "natural_disaster",
    "policy_change",
]

DOCUMENT_PARSER_VALID_IMPACT_LEVELS = [
    "high",
    "medium",
    "low",
]

DOCUMENT_PARSER_VALID_DOC_TYPES = [
    "price_increase",
    "shortage",
    "report",
    "other",
]

DOCUMENT_PARSER_OUTPUT_SCHEMA = {
    "type": "object",
    "required": DOCUMENT_PARSER_REQUIRED_FIELDS,
    "properties": {
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "required": DOCUMENT_PARSER_EVENT_FIELDS,
                "properties": {
                    "event_type": {
                        "type": "string",
                        "enum": DOCUMENT_PARSER_VALID_EVENT_TYPES,
                    },
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "affected_categories": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "affected_manufacturers": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "effective_date": {"type": ["string", "null"]},
                    "impact_level": {
                        "type": "string",
                        "enum": DOCUMENT_PARSER_VALID_IMPACT_LEVELS,
                    },
                    "price_change_pct": {"type": ["number", "null"]},
                    "confidence": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                    },
                    "evidence_text": {"type": "string"},
                },
            },
        },
        "doc_summary": {"type": "string"},
        "doc_type_classified": {
            "type": "string",
            "enum": DOCUMENT_PARSER_VALID_DOC_TYPES,
        },
    },
}
