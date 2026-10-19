"""T2-013 建议生成服务 测试。

覆盖：
- 正常LLM调用（mock）
- 降级触发（API不可用/JSON解析失败/输出不完整）
- 模板降级（各风险等级的参数映射）
- 输出验证（三组建议列表+总结）
"""

import json
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, "/app/data/所有对话/主对话/BOM系统v4改造/backend")

from app.services.llm.recommendation_generator import (
    RecommendationGenerator,
    _generate_template_recommendations,
    _get_alt_model_suggestion,
)
from app.services.llm.base import LLMCallResult


class TestRecommendationGenerator(unittest.TestCase):
    """T2-013 建议生成测试。"""

    def _make_generator(self, mock_client=None):
        if mock_client is None:
            mock_client = MagicMock()
            mock_client.available = True
        return RecommendationGenerator(llm_client=mock_client), mock_client

    def _valid_llm_response(self):
        return {
            "procurement_recommendations": [
                {"action_type": "lock_price", "material": "STM32", "risk_reason": "test", "detail": "lock 8w", "urgency": "high"}
            ],
            "rd_recommendations": [
                {"action_type": "alt_verification", "material": "STM32", "risk_reason": "test", "detail": "verify GD32", "urgency": "high"}
            ],
            "pm_recommendations": [
                {"action_type": "schedule_buffer", "material": "项目", "risk_reason": "test", "detail": "+14d", "urgency": "high"}
            ],
            "summary": "建议立即执行锁价备货并启动替代验证。",
        }

    # ── 正常路径 ──

    def test_01_successful_generation(self):
        """LLM 正常返回建议。"""
        gen, mock_client = self._make_generator()
        mock_client._call.return_value = json.dumps(self._valid_llm_response())

        result = gen.generate(
            event="地震",
            risk_level="red",
            risk_score=85.0,
            affected_materials=[{"mpn": "STM32", "category": "MCU"}],
        )
        self.assertTrue(result.success)
        self.assertFalse(result.degraded)
        self.assertEqual(len(result.data["procurement_recommendations"]), 1)

    # ── 降级路径 ──

    def test_10_degrade_no_api(self):
        """API 不可用时降级为模板。"""
        mock_client = MagicMock()
        mock_client.available = False
        gen = RecommendationGenerator(llm_client=mock_client)

        result = gen.generate(
            event="地震",
            risk_level="red",
            risk_score=85.0,
            affected_materials=[{"mpn": "STM32", "category": "MCU"}],
        )
        self.assertFalse(result.success)
        self.assertTrue(result.degraded)
        # 模板降级应包含三组建议
        self.assertIn("procurement_recommendations", result.data)
        self.assertTrue(len(result.data["procurement_recommendations"]) > 0)

    def test_11_degrade_invalid_json(self):
        """JSON 解析失败时降级。"""
        gen, mock_client = self._make_generator()
        mock_client._call.return_value = "not json at all"

        result = gen.generate("火灾", "orange", 60.0, [])
        self.assertTrue(result.degraded)

    def test_12_degrade_missing_fields(self):
        """输出缺少必要字段时降级。"""
        gen, mock_client = self._make_generator()
        mock_client._call.return_value = json.dumps({"procurement_recommendations": []})

        result = gen.generate("火灾", "orange", 60.0, [])
        self.assertTrue(result.degraded)

    def test_13_degrade_exception(self):
        """API 抛异常时降级。"""
        gen, mock_client = self._make_generator()
        mock_client._call.side_effect = Exception("timeout")

        result = gen.generate("地震", "yellow", 40.0, [])
        self.assertTrue(result.degraded)

    # ── 模板降级参数验证 ──

    def test_20_template_red_level(self):
        """红色风险等级模板参数：lock_weeks=12, buffer_days=30。"""
        ctx = {"event": "大地震", "risk_level": "red",
               "affected_materials": [{"mpn": "MLCC"}]}
        result = _generate_template_recommendations(ctx)

        self.assertTrue(result["_degraded"])
        # 采购建议：锁12周
        lock_rec = result["procurement_recommendations"][0]
        self.assertIn("12", lock_rec["detail"])
        # 项目建议：30天缓冲
        buffer_rec = result["pm_recommendations"][0]
        self.assertEqual(buffer_rec["buffer_days"], 30)

    def test_21_template_yellow_level(self):
        """黄色风险等级模板参数：lock_weeks=4, buffer_days=14。"""
        ctx = {"event": "供应紧张", "risk_level": "yellow",
               "affected_materials": [{"mpn": "电阻"}]}
        result = _generate_template_recommendations(ctx)

        lock_rec = result["procurement_recommendations"][0]
        self.assertIn("4", lock_rec["detail"])

    def test_22_template_single_source_material(self):
        """单源物料触发替代采购建议。"""
        ctx = {"event": "测试", "risk_level": "orange",
               "affected_materials": [
                   {"mpn": "专用IC", "is_single_source": True}
               ]}
        result = _generate_template_recommendations(ctx)

        # 应有3条采购建议（锁价+备货+替代）
        self.assertEqual(len(result["procurement_recommendations"]), 3)
        alt_rec = result["procurement_recommendations"][2]
        self.assertEqual(alt_rec["action_type"], "alternative_source")

    def test_23_template_red_has_cert_presets(self):
        """红色/橙色等级触发认证预置建议。"""
        for level in ["red", "orange"]:
            ctx = {"event": "测试", "risk_level": level,
                   "affected_materials": [{"mpn": "MCU"}]}
            result = _generate_template_recommendations(ctx)
            rd_types = [r["action_type"] for r in result["rd_recommendations"]]
            self.assertIn("cert_presets", rd_types, f"{level} 级别应包含 cert_presets")

    def test_24_template_green_no_cert_presets(self):
        """绿色等级不触发认证预置。"""
        ctx = {"event": "测试", "risk_level": "green",
               "affected_materials": [{"mpn": "电阻"}]}
        result = _generate_template_recommendations(ctx)
        rd_types = [r["action_type"] for r in result["rd_recommendations"]]
        self.assertNotIn("cert_presets", rd_types)

    # ── 国产替代推荐 ──

    def test_30_alt_model_stm32(self):
        """STM32 → 兆易GD32。"""
        suggestion = _get_alt_model_suggestion("STM32F103")
        self.assertIn("GD32", suggestion)

    def test_31_alt_model_mlcc(self):
        """MLCC → 三环/风华。"""
        suggestion = _get_alt_model_suggestion("MLCC 0402")
        self.assertIn("三环", suggestion)

    def test_32_alt_model_unknown(self):
        """未知物料 → 通用建议。"""
        suggestion = _get_alt_model_suggestion("XYZ-12345")
        self.assertIn("国产替代", suggestion)

    # ── 输出验证 ──

    def test_40_validate_output_valid(self):
        """有效输出通过验证。"""
        gen, _ = self._make_generator()
        self.assertTrue(gen._validate_output(self._valid_llm_response()))

    def test_41_validate_output_empty_list(self):
        """空建议列表不通过验证。"""
        gen, _ = self._make_generator()
        data = self._valid_llm_response()
        data["procurement_recommendations"] = []
        self.assertFalse(gen._validate_output(data))

    def test_42_validate_output_not_dict(self):
        """非字典输入不通过验证。"""
        gen, _ = self._make_generator()
        self.assertFalse(gen._validate_output("string"))

    def test_43_validate_output_empty_summary(self):
        """空 summary 不通过验证。"""
        gen, _ = self._make_generator()
        data = self._valid_llm_response()
        data["summary"] = ""
        self.assertFalse(gen._validate_output(data))


if __name__ == "__main__":
    unittest.main()
