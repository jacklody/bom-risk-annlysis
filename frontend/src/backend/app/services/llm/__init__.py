"""LLM 服务模块 — BOM风险预警系统。

提供基于 DeepSeek API 的 LLM 推理能力:
- chain_reasoning: 事件链路推理 (T2-011)
- document_parser: 非结构化文档风险事件提取 (T2-012)
- recommendation_generator: 采购/研发/项目建议生成 (T2-013)

所有 LLM 服务共享 base.py 中的基础设施:
- DeepSeek API 调用封装
- JSON 输出解析与容错
- 超时/重试/降级处理
"""

from app.services.llm.base import LLMServiceBase, LLMCallResult
from app.services.llm.chain_reasoning import ChainReasoningService
from app.services.llm.document_parser import DocumentParser
from app.services.llm.recommendation_generator import RecommendationGenerator

__all__ = [
    "LLMServiceBase",
    "LLMCallResult",
    "ChainReasoningService",
    "DocumentParser",
    "RecommendationGenerator",
]
