"""T2-011 事件链路推理服务 测试。

覆盖：
- 正常LLM调用（mock）
- 降级触发（API不可用/返回为空/JSON解析失败/输出结构不完整）
- Prompt构造
- JSON容错解析（策略1-4）
"""

import json
import sys
import unittest
from unittest.mock import MagicMock, patch

# 添加 backend 到 path
sys.path.insert(0, "/app/data/所有对话/主对话/BOM系统v4改造/backend")

from app.services.llm.chain_reasoning import ChainReasoningService
from app.services.llm.base import LLMCallResult


class TestChainReasoningService(unittest.TestCase):
    """T2-011 链路推理测试。"""

    def _make_service(self, mock_client=None):
        """创建测试用服务实例。"""
        if mock_client is None:
            mock_client = MagicMock()
            mock_client.available = True
        return ChainReasoningService(llm_client=mock_client), mock_client

    # ── 正常路径 ──

    def test_01_successful_llm_call(self):
        """LLM 调用成功，返回有效 JSON。"""
        svc, mock_client = self._make_service()
        valid_response = {
            "propagation_chain": "地震 → 晶圆厂停产 → MCU供应紧张 → BOM物料受影响",
            "time_window": "2-4个月",
            "impact_assessment": "MCU交期延长4-8周",
            "severity_estimate": "high",
            "procurement_action": "锁定8周需求量",
            "rd_action": "启动国产MCU替代验证",
            "pm_action": "项目增加14天缓冲",
        }
        mock_client._call.return_value = json.dumps(valid_response)

        context = {
            "event": "台湾地震",
            "source_level": "Red",
            "affected_region": "台湾南部",
            "nearby_factories": ["TSMC FAB14"],
            "affected_categories": ["MCU", "SoC"],
            "bom_hits": [{"mpn": "STM32F103", "category": "MCU", "project": "ProjectA"}],
            "additional_context": "当前库存3周",
        }

        result = svc.run(context)
        self.assertTrue(result.success)
        self.assertFalse(result.degraded)
        self.assertEqual(result.data["severity_estimate"], "high")
        self.assertGreater(result.latency_ms, 0)

    def test_02_prompt_construction(self):
        """验证 prompt 正确包含上下文信息。"""
        svc, mock_client = self._make_service()
        mock_client._call.return_value = json.dumps({
            "propagation_chain": "test",
            "time_window": "1-2个月",
            "impact_assessment": "test",
            "severity_estimate": "medium",
            "procurement_action": "test",
            "rd_action": "test",
            "pm_action": "test",
        })

        context = {
            "event": "火灾事件",
            "source_level": "Orange",
            "affected_region": "日本大阪",
            "nearby_factories": ["Murata工厂"],
            "affected_categories": ["MLCC"],
            "bom_hits": [{"mpn": "GRM155", "category": "MLCC"}],
            "additional_context": "",
        }

        svc.run(context)
        # 验证 _call 被调用，且 system_prompt 和 user_prompt 都包含关键信息
        call_args = mock_client._call.call_args
        system_prompt = call_args.kwargs.get("system_prompt", call_args.args[0] if call_args.args else "")
        user_prompt = call_args.kwargs.get("user_prompt", call_args.args[1] if len(call_args.args) > 1 else "")

        self.assertIn("JSON", system_prompt)
        self.assertIn("火灾事件", user_prompt)
        self.assertIn("日本大阪", user_prompt)

    # ── 降级路径 ──

    def test_10_degrade_no_api_key(self):
        """API Key 未配置时触发降级。"""
        mock_client = MagicMock()
        mock_client.available = False
        svc = ChainReasoningService(llm_client=mock_client)

        result = svc.run({"event": "测试事件", "source_level": "Red",
                         "affected_region": "", "nearby_factories": [],
                         "affected_categories": [], "bom_hits": [], "additional_context": ""})
        self.assertFalse(result.success)
        self.assertTrue(result.degraded)
        # 降级输出应包含基本字段
        self.assertIn("propagation_chain", result.data)

    def test_11_degrade_none_response(self):
        """LLM 返回 None 时触发降级。"""
        svc, mock_client = self._make_service()
        mock_client._call.return_value = None

        result = svc.run({"event": "测试", "source_level": "Red",
                         "affected_region": "", "nearby_factories": [],
                         "affected_categories": [], "bom_hits": [], "additional_context": ""})
        self.assertTrue(result.degraded)

    def test_12_degrade_invalid_json(self):
        """LLM 返回非 JSON 时触发降级。"""
        svc, mock_client = self._make_service()
        mock_client._call.return_value = "这不是JSON格式的内容"

        result = svc.run({"event": "测试", "source_level": "Red",
                         "affected_region": "", "nearby_factories": [],
                         "affected_categories": [], "bom_hits": [], "additional_context": ""})
        self.assertTrue(result.degraded)

    def test_13_degrade_missing_fields(self):
        """LLM JSON 缺少必要字段时触发降级。"""
        svc, mock_client = self._make_service()
        mock_client._call.return_value = json.dumps({"only_one_field": "value"})

        result = svc.run({"event": "测试", "source_level": "Red",
                         "affected_region": "", "nearby_factories": [],
                         "affected_categories": [], "bom_hits": [], "additional_context": ""})
        self.assertTrue(result.degraded)

    def test_14_degrade_exception(self):
        """LLM 调用抛异常时触发降级。"""
        svc, mock_client = self._make_service()
        mock_client._call.side_effect = Exception("Connection timeout")

        result = svc.run({"event": "测试", "source_level": "Red",
                         "affected_region": "", "nearby_factories": [],
                         "affected_categories": [], "bom_hits": [], "additional_context": ""})
        self.assertTrue(result.degraded)
        self.assertIn("Connection timeout", result.error)

    # ── JSON 容错解析 ──

    def test_20_json_with_markdown_fences(self):
        """LLM 返回包含 ```json``` 标记的响应。"""
        svc, mock_client = self._make_service()
        raw = '```json\n{"propagation_chain": "test", "time_window": "1月", "impact_assessment": "t", "severity_estimate": "low", "procurement_action": "t", "rd_action": "t", "pm_action": "t"}\n```'
        mock_client._call.return_value = raw

        result = svc.run({"event": "测试", "source_level": "Green",
                         "affected_region": "", "nearby_factories": [],
                         "affected_categories": [], "bom_hits": [], "additional_context": ""})
        self.assertTrue(result.success)

    def test_21_json_with_single_quotes(self):
        """LLM 返回使用单引号的 JSON（容错策略3）。"""
        svc, mock_client = self._make_service()
        raw = "{'propagation_chain': 'test', 'time_window': '1月', 'impact_assessment': 't', 'severity_estimate': 'low', 'procurement_action': 't', 'rd_action': 't', 'pm_action': 't'}"
        mock_client._call.return_value = raw

        result = svc.run({"event": "测试", "source_level": "Green",
                         "affected_region": "", "nearby_factories": [],
                         "affected_categories": [], "bom_hits": [], "additional_context": ""})
        self.assertTrue(result.success)

    def test_22_json_with_trailing_comma(self):
        """LLM 返回含尾部逗号的 JSON（容错策略3）。"""
        svc, mock_client = self._make_service()
        raw = '{"propagation_chain": "test", "time_window": "1月", "impact_assessment": "t", "severity_estimate": "low", "procurement_action": "t", "rd_action": "t", "pm_action": "t",}'
        mock_client._call.return_value = raw

        result = svc.run({"event": "测试", "source_level": "Green",
                         "affected_region": "", "nearby_factories": [],
                         "affected_categories": [], "bom_hits": [], "additional_context": ""})
        self.assertTrue(result.success)

    # ── 便捷接口 ──

    def test_30_reason_convenience_method(self):
        """reason() 便捷接口正确构造 context。"""
        svc, mock_client = self._make_service()
        mock_client._call.return_value = json.dumps({
            "propagation_chain": "test", "time_window": "1月",
            "impact_assessment": "t", "severity_estimate": "low",
            "procurement_action": "t", "rd_action": "t", "pm_action": "t",
        })

        # reason() 接受 ChainReasoningContext 对象
        from app.services.llm.chain_reasoning import ChainReasoningContext
        ctx = ChainReasoningContext(
            event="地震事件",
            source_level="Orange",
            affected_region="台湾",
            nearby_factories=["TSMC"],
            affected_categories=["MCU"],
            bom_hits=[{"mpn": "STM32F103", "category": "MCU"}],
        )
        result = svc.reason(ctx)
        self.assertTrue(result.success)


if __name__ == "__main__":
    unittest.main()
