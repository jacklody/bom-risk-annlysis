"""LLM 服务基类 — 封装 DeepSeek API 调用、JSON 解析、错误处理与降级逻辑。

所有 LLM 服务（chain_reasoning, recommendation_generator）继承此基类，
复用统一的调用、解析、降级基础设施。

依赖:
    - app.services.llm_client.LLMClient: 已有的 DeepSeek 客户端
    - app.config.settings: 配置（llm_api_key, llm_base_url, llm_model 等）
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class LLMCallResult:
    """LLM 调用统一结果。

    Attributes:
        success: 调用是否成功（LLM返回了可解析的JSON）
        data: 解析后的结构化数据字典
        raw_text: LLM 原始返回文本（用于调试）
        error: 错误信息（调用失败时）
        degraded: 是否触发了降级逻辑
        degrade_reason: 降级原因说明
        latency_ms: 调用耗时（毫秒）
    """
    success: bool = False
    data: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""
    error: str = ""
    degraded: bool = False
    degrade_reason: str = ""
    latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        return {
            "success": self.success,
            "data": self.data,
            "raw_text": self.raw_text[:500] if self.raw_text else "",
            "error": self.error,
            "degraded": self.degraded,
            "degrade_reason": self.degrade_reason,
            "latency_ms": round(self.latency_ms, 1),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# 基类
# ═══════════════════════════════════════════════════════════════════════════════

class LLMServiceBase:
    """LLM 服务基类。

    封装:
    1. DeepSeek API 调用（复用现有 LLMClient）
    2. JSON 输出解析（system prompt 强制 JSON + json.loads 容错）
    3. 超时控制（30秒）
    4. 错误处理与降级框架

    子类需实现:
    - _build_system_prompt() -> str
    - _build_user_prompt(context: dict) -> str
    - _validate_output(data: dict) -> bool
    - _fallback(context: dict) -> dict  （降级逻辑）

    Usage::

        class MyService(LLMServiceBase):
            def _build_system_prompt(self) -> str:
                return "你是xxx专家，请输出JSON..."
            def _build_user_prompt(self, context: dict) -> str:
                return f"事件：{context['event']}"
            def _validate_output(self, data: dict) -> bool:
                return "key_field" in data
            def _fallback(self, context: dict) -> dict:
                return {"key_field": "default_value", "degraded": True}

        service = MyService()
        result = service.run(context)
    """

    # 子类可覆盖的默认参数
    DEFAULT_TEMPERATURE: float = 0.3
    DEFAULT_MAX_TOKENS: int = 2000
    DEFAULT_TIMEOUT: float = 30.0
    SERVICE_NAME: str = "LLMServiceBase"

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """初始化 LLM 服务。

        Args:
            llm_client: 可选的 LLM 客户端实例。
                        为 None 时自动创建（读取 config 中的配置）。
        """
        self._client = llm_client or LLMClient()

    # ────────────────────────────────────────────────────────
    # 公开接口: 统一调用入口
    # ────────────────────────────────────────────────────────

    def run(self, context: dict[str, Any]) -> LLMCallResult:
        """执行 LLM 推理，包含完整的调用→解析→降级流程。

        Args:
            context: 结构化上下文（由调用方构造）

        Returns:
            LLMCallResult: 统一结果
        """
        start_time = time.monotonic()

        # Step 0: 检查 LLM 可用性
        if not self._client.available:
            return self._build_degraded_result(
                "LLM API key 未配置，使用降级输出",
                context,
                start_time,
            )

        # Step 1: 构造 prompt
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(context)

        # Step 2: 调用 LLM
        try:
            raw_text = self._client._call(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=self.DEFAULT_MAX_TOKENS,
            )
        except Exception as e:
            logger.error(
                "[%s] LLM 调用异常: %s", self.SERVICE_NAME, str(e)
            )
            return self._build_degraded_result(
                f"LLM 调用异常: {str(e)}", context, start_time
            )

        if raw_text is None:
            return self._build_degraded_result(
                "LLM 返回为空（API不可用或超时）", context, start_time
            )

        # Step 3: 解析 JSON
        parsed = self._parse_json(raw_text)
        if parsed is None:
            return self._build_degraded_result(
                "LLM 返回内容无法解析为有效 JSON", context, start_time,
                raw_text=raw_text,
            )

        # Step 4: 验证输出结构
        if not self._validate_output(parsed):
            return self._build_degraded_result(
                "LLM 输出结构不符合预期（缺少必要字段）",
                context, start_time, raw_text=raw_text,
            )

        # Step 5: 成功
        latency_ms = (time.monotonic() - start_time) * 1000
        logger.info(
            "[%s] LLM 调用成功, 耗时 %.1f ms",
            self.SERVICE_NAME, latency_ms,
        )
        return LLMCallResult(
            success=True,
            data=parsed,
            raw_text=raw_text,
            latency_ms=latency_ms,
        )

    # ────────────────────────────────────────────────────────
    # 子类必须实现的方法
    # ────────────────────────────────────────────────────────

    def _build_system_prompt(self) -> str:
        """构造 system prompt。必须强制要求 JSON 输出格式。"""
        raise NotImplementedError

    def _build_user_prompt(self, context: dict[str, Any]) -> str:
        """根据上下文构造 user prompt。"""
        raise NotImplementedError

    def _validate_output(self, data: dict) -> bool:
        """验证 LLM 输出的 JSON 是否包含必要字段。"""
        raise NotImplementedError

    def _fallback(self, context: dict[str, Any]) -> dict:
        """降级逻辑：LLM 调用失败时的规则引擎/模板输出。"""
        raise NotImplementedError

    # ────────────────────────────────────────────────────────
    # 内部方法
    # ────────────────────────────────────────────────────────

    def _parse_json(self, text: str) -> Optional[dict]:
        """从 LLM 响应文本中解析 JSON 对象。

        解析策略:
        1. 直接 json.loads（最理想情况）
        2. 提取 { ... } 块后 json.loads
        3. 修复常见问题（单引号→双引号、尾部逗号等）后重试
        4. 复用 LLMClient._extract_json 的容错逻辑

        Args:
            text: LLM 原始返回文本

        Returns:
            解析后的字典，失败返回 None
        """
        if not text:
            return None

        # 策略 1: 直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 策略 2: 提取 { ... } 块
        json_start = text.find("{")
        json_end = text.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            snippet = text[json_start:json_end]
            try:
                return json.loads(snippet)
            except json.JSONDecodeError:
                pass

            # 策略 3: 修复常见问题
            fixed = snippet.replace("'", '"')
            # 移除尾部逗号（JSON 不合法但 LLM 常犯）
            import re
            fixed = re.sub(r",\s*([}\]])", r"\1", fixed)
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass

        # 策略 4: 复用 LLMClient 的提取逻辑
        return self._client._extract_json(text)

    def _build_degraded_result(
        self,
        reason: str,
        context: dict[str, Any],
        start_time: float,
        raw_text: str = "",
    ) -> LLMCallResult:
        """构建降级结果。

        调用子类的 _fallback 方法生成降级输出。

        Args:
            reason: 降级原因
            context: 原始上下文
            start_time: 调用开始时间
            raw_text: LLM 原始返回（如有）

        Returns:
            LLMCallResult（降级标记）
        """
        latency_ms = (time.monotonic() - start_time) * 1000
        logger.warning(
            "[%s] 降级触发: %s", self.SERVICE_NAME, reason
        )

        try:
            fallback_data = self._fallback(context)
        except Exception as e:
            logger.error(
                "[%s] 降级逻辑也失败: %s", self.SERVICE_NAME, str(e)
            )
            fallback_data = {"error": "fallback_failed", "detail": str(e)}

        return LLMCallResult(
            success=False,
            data=fallback_data,
            raw_text=raw_text,
            error=reason,
            degraded=True,
            degrade_reason=reason,
            latency_ms=latency_ms,
        )
