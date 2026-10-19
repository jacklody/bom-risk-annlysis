"""事件链路推理服务 (T2-011)。

利用 DeepSeek API 实现事件→产业链→BOM影响的推理能力。

核心流程:
1. 接收结构化上下文（事件信息 + BOM命中物料）
2. 构造 prompt（system: 推理框架 + JSON格式要求; user: 具体事件数据）
3. 调用 LLM 获取推理结果
4. 解析输出为结构化 JSON
5. LLM 调用失败时降级为规则引擎输出

降级策略:
- chain_reasoning 降级为基于知识图谱的简单链路查询:
  使用 ChainQueryService 查询受影响品类的上下游关系，
  拼接为简化版传导路径，时间窗口使用固定规则估算。

依赖:
    - LLMServiceBase: LLM 服务基类
    - chain_reasoning prompts: Prompt 模板
    - ChainQueryService: 产业链知识图谱查询（降级时使用）
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from app.services.llm.base import LLMCallResult, LLMServiceBase
from app.services.llm.prompts.chain_reasoning import (
    CHAIN_REASONING_OUTPUT_SCHEMA,
    CHAIN_REASONING_REQUIRED_FIELDS,
    CHAIN_REASONING_SYSTEM_PROMPT,
    CHAIN_REASONING_USER_PROMPT_TEMPLATE,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 输入上下文构造
# ═══════════════════════════════════════════════════════════════════════════════

class ChainReasoningContext:
    """链路推理的结构化上下文。

    封装 LLM 推理所需的输入数据，确保传给 LLM 的是精炼的结构化信息
    而非全文新闻（控制 token 消耗 + 提高推理准确度）。

    Attributes:
        event: 事件描述（如"台湾台南发生M6.4地震"）
        source_level: 数据来源级别（S/A/B/C）
        affected_region: 受影响区域（如"台南科学园区"）
        nearby_factories: 附近工厂列表（如["台积电Fab14", "联电南科厂"]）
        affected_categories: 受影响品类列表（如["晶圆代工", "SoC"]）
        bom_hits: BOM命中物料列表，每项含 mpn/category/project
        additional_context: 额外上下文信息（如历史同类事件参考）
    """

    def __init__(
        self,
        event: str,
        source_level: str = "B",
        affected_region: str = "",
        nearby_factories: Optional[list[str]] = None,
        affected_categories: Optional[list[str]] = None,
        bom_hits: Optional[list[dict[str, Any]]] = None,
        additional_context: str = "",
    ):
        self.event = event
        self.source_level = source_level
        self.affected_region = affected_region
        self.nearby_factories = nearby_factories or []
        self.affected_categories = affected_categories or []
        self.bom_hits = bom_hits or []
        self.additional_context = additional_context

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典（用于 prompt 构造）。"""
        return {
            "event": self.event,
            "source_level": self.source_level,
            "affected_region": self.affected_region,
            "nearby_factories": self.nearby_factories,
            "affected_categories": self.affected_categories,
            "bom_hits": self.bom_hits,
            "additional_context": self.additional_context,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChainReasoningContext":
        """从字典构建上下文。"""
        return cls(
            event=data.get("event", ""),
            source_level=data.get("source_level", "B"),
            affected_region=data.get("affected_region", ""),
            nearby_factories=data.get("nearby_factories", []),
            affected_categories=data.get("affected_categories", []),
            bom_hits=data.get("bom_hits", []),
            additional_context=data.get("additional_context", ""),
        )

    def to_context_dict(self) -> dict[str, Any]:
        """构建传递给 LLM 服务 run() 方法的 context 字典。

        这是 LLMServiceBase.run(context) 的输入格式。
        """
        return self.to_dict()


# ═══════════════════════════════════════════════════════════════════════════════
# 降级: 规则引擎输出
# ═══════════════════════════════════════════════════════════════════════════════

# 事件类型 → 默认时间窗口映射（基于历史事件库统计）
EVENT_TYPE_TIME_WINDOWS: dict[str, str] = {
    "地震": "1-3个月",
    "earthquake": "1-3个月",
    "火灾": "2-6个月",
    "fire": "2-6个月",
    "爆炸": "3-6个月",
    "explosion": "3-6个月",
    "台风": "1-2个月",
    "typhoon": "1-2个月",
    "洪水": "1-3个月",
    "flood": "1-3个月",
    "疫情": "3-12个月",
    "pandemic": "3-12个月",
    "政策": "6-12个月",
    "policy": "6-12个月",
    "制裁": "6-24个月",
    "sanction": "6-24个月",
}

# 事件类型关键词检测顺序（优先级从高到低）
EVENT_TYPE_KEYWORDS = [
    ("地震", "earthquake"),
    ("火灾", "fire"),
    ("爆炸", "explosion"),
    ("台风", "typhoon"),
    ("洪水", "flood"),
    ("疫情", "pandemic"),
    ("制裁", "sanction"),
    ("政策", "policy"),
]


def _detect_event_type(event_text: str) -> str:
    """从事件文本中检测事件类型。"""
    text_lower = event_text.lower()
    for cn, en in EVENT_TYPE_KEYWORDS:
        if cn in text_lower or en in text_lower:
            return cn
    return "其他"


def _get_default_time_window(event_text: str) -> str:
    """根据事件类型返回默认时间窗口。"""
    event_type = _detect_event_type(event_text)
    return EVENT_TYPE_TIME_WINDOWS.get(event_type, "1-3个月")


def _build_rule_based_propagation(context: dict[str, Any]) -> dict[str, Any]:
    """规则引擎降级输出。

    基于事件文本和结构化信息，使用简单规则拼接传导链路和建议。
    不依赖知识图谱（避免额外依赖），直接从上下文数据构造合理输出。

    Args:
        context: ChainReasoningContext.to_dict() 的输出

    Returns:
        符合输出 schema 的字典
    """
    event = context.get("event", "未知事件")
    affected_region = context.get("affected_region", "")
    nearby_factories = context.get("nearby_factories", [])
    affected_categories = context.get("affected_categories", [])
    bom_hits = context.get("bom_hits", [])

    event_type = _detect_event_type(event)
    time_window = _get_default_time_window(event)

    # 构造传导链路
    chain_parts = [event]
    if affected_region:
        chain_parts.append(f"影响区域: {affected_region}")
    if nearby_factories:
        chain_parts.append(f"涉及工厂: {', '.join(nearby_factories[:3])}")
    if affected_categories:
        chain_parts.append(f"影响品类: {', '.join(affected_categories[:5])}")
    if bom_hits:
        mpns = [h.get("mpn", "") for h in bom_hits[:3] if h.get("mpn")]
        if mpns:
            chain_parts.append(f"BOM物料: {', '.join(mpns)}")
    chain_parts.append("供应交期延长/价格上行")

    propagation_chain = " → ".join(chain_parts)

    # 构造影响评估
    if bom_hits:
        hit_descriptions = []
        for hit in bom_hits[:5]:
            mpn = hit.get("mpn", "未知物料")
            category = hit.get("category", "未知品类")
            project = hit.get("project", "未知项目")
            hit_descriptions.append(
                f"{mpn}({category})可能交期延长4-8周，影响{project}"
            )
        impact_assessment = "；".join(hit_descriptions)
    else:
        impact_assessment = (
            f"事件影响{affected_region or '相关区域'}的"
            f"{', '.join(affected_categories[:3]) or '电子元器件'}供应，"
            f"预计交期延长2-4周"
        )

    # 严重程度估算
    severity = "medium"
    if bom_hits and len(bom_hits) >= 3:
        severity = "high"
    elif bom_hits:
        severity = "medium"
    elif affected_categories:
        severity = "low"

    # 采购建议
    if bom_hits:
        procurement_action = (
            f"建议对受影响物料锁定8周需求量的安全库存；"
            f"对{', '.join(set(h.get('category', '') for h in bom_hits[:3]))}品类启动替代供应商询价"
        )
    else:
        procurement_action = (
            f"建议提前备货{', '.join(affected_categories[:2]) or '相关'}品类物料，"
            f"锁定4-8周安全库存"
        )

    # 研发建议
    if bom_hits:
        categories_set = set(h.get("category", "") for h in bom_hits if h.get("category"))
        rd_action = (
            f"建议启动{', '.join(list(categories_set)[:2])}品类的Pin-to-Pin替代料验证，"
            f"预计验证周期4-8周"
        )
    else:
        rd_action = "暂无直接BOM物料影响，建议持续关注品类供应动态"

    # 项目管理建议
    pm_action = (
        f"建议在项目计划中增加{time_window}的交期缓冲；"
        f"关键里程碑后移2-4周；建议成本储备3-5%"
    )

    return {
        "propagation_chain": propagation_chain,
        "time_window": time_window,
        "impact_assessment": impact_assessment,
        "severity_estimate": severity,
        "procurement_action": procurement_action,
        "rd_action": rd_action,
        "pm_action": pm_action,
        "_degraded": True,
        "_degrade_method": "rule_engine",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 主服务类
# ═══════════════════════════════════════════════════════════════════════════════

class ChainReasoningService(LLMServiceBase):
    """事件链路推理服务 (T2-011)。

    利用 DeepSeek API 对供应链风险事件进行传导链路推理，
    输出结构化的传导路径、时间窗口、影响评估和多角色建议。

    Usage::

        from app.services.llm.chain_reasoning import (
            ChainReasoningService,
            ChainReasoningContext,
        )

        service = ChainReasoningService()
        context = ChainReasoningContext(
            event="台湾台南发生M6.4地震",
            source_level="S",
            affected_region="台南科学园区",
            nearby_factories=["台积电Fab14", "联电南科厂"],
            affected_categories=["晶圆代工", "SoC", "无线连接芯片"],
            bom_hits=[
                {"mpn": "MT6625", "category": "无线芯片", "project": "ProjectA"},
            ],
        )
        result = service.run(context.to_context_dict())
        # result.data 即为结构化推理结果
    """

    SERVICE_NAME = "ChainReasoning"
    DEFAULT_MAX_TOKENS = 2000

    # ────────────────────────────────────────────────────────
    # 子类实现: Prompt 构造
    # ────────────────────────────────────────────────────────

    def _build_system_prompt(self) -> str:
        """返回链路推理的 system prompt。

        强制要求 JSON 格式输出，包含完整的推理框架说明。
        """
        return CHAIN_REASONING_SYSTEM_PROMPT

    def _build_user_prompt(self, context: dict[str, Any]) -> str:
        """根据结构化上下文构造 user prompt。

        将事件信息、受影响品类、BOM命中物料格式化为可读文本，
        供 LLM 进行推理。

        Args:
            context: ChainReasoningContext.to_context_dict() 的输出

        Returns:
            格式化的 user prompt 字符串
        """
        # 格式化附近工厂
        nearby_factories = context.get("nearby_factories", [])
        factories_text = ", ".join(nearby_factories) if nearby_factories else "暂无数据"

        # 格式化受影响品类
        affected_categories = context.get("affected_categories", [])
        categories_text = (
            "\n".join(f"- {cat}" for cat in affected_categories)
            if affected_categories
            else "暂无数据"
        )

        # 格式化 BOM 命中物料
        bom_hits = context.get("bom_hits", [])
        if bom_hits:
            hits_lines = []
            for hit in bom_hits:
                mpn = hit.get("mpn", "N/A")
                category = hit.get("category", "N/A")
                project = hit.get("project", "N/A")
                hits_lines.append(f"- MPN: {mpn} | 品类: {category} | 项目: {project}")
            bom_hits_text = "\n".join(hits_lines)
        else:
            bom_hits_text = "暂无直接BOM命中物料"

        # 补充上下文
        additional_context = context.get("additional_context", "")
        if not additional_context:
            additional_context = "无额外上下文信息"

        return CHAIN_REASONING_USER_PROMPT_TEMPLATE.format(
            event=context.get("event", "未知事件"),
            source_level=context.get("source_level", "B"),
            affected_region=context.get("affected_region", "未指定"),
            nearby_factories=factories_text,
            affected_categories=categories_text,
            bom_hits=bom_hits_text,
            additional_context=additional_context,
        )

    # ────────────────────────────────────────────────────────
    # 子类实现: 输出验证
    # ────────────────────────────────────────────────────────

    def _validate_output(self, data: dict) -> bool:
        """验证 LLM 输出的 JSON 包含所有必要字段。

        必要字段:
        - propagation_chain: 传导链路
        - time_window: 时间窗口
        - impact_assessment: 影响评估
        - procurement_action: 采购建议
        - rd_action: 研发建议
        - pm_action: 项目管理建议

        Args:
            data: LLM 返回并解析后的字典

        Returns:
            是否通过验证
        """
        if not isinstance(data, dict):
            return False

        for field_name in CHAIN_REASONING_REQUIRED_FIELDS:
            if field_name not in data:
                logger.warning(
                    "[ChainReasoning] 输出缺少必要字段: %s", field_name
                )
                return False
            # 检查字段值非空
            value = data[field_name]
            if not value or (isinstance(value, str) and not value.strip()):
                logger.warning(
                    "[ChainReasoning] 字段值为空: %s", field_name
                )
                return False

        return True

    # ────────────────────────────────────────────────────────
    # 子类实现: 降级逻辑
    # ────────────────────────────────────────────────────────

    def _fallback(self, context: dict[str, Any]) -> dict:
        """降级输出：LLM 调用失败时使用规则引擎生成结果。

        基于事件文本类型匹配和结构化上下文数据，
        生成符合输出格式的规则推理结果。

        Args:
            context: 原始上下文数据

        Returns:
            降级结果字典
        """
        return _build_rule_based_propagation(context)

    # ────────────────────────────────────────────────────────
    # 便捷接口
    # ────────────────────────────────────────────────────────

    def reason(self, context: ChainReasoningContext) -> LLMCallResult:
        """便捷推理接口，接受 ChainReasoningContext 对象。

        Args:
            context: 链路推理上下文对象

        Returns:
            LLMCallResult: 推理结果
        """
        return self.run(context.to_context_dict())
