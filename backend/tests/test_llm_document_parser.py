"""T2-012 文档解析服务 测试。

覆盖：
- 正常LLM调用（mock）
- 降级触发（API不可用/返回为空/JSON解析失败/输出结构不完整）
- Prompt构造
- 正则降级提取（涨价幅度/日期/物料/厂商提取）
- 输出验证（各文档类型）
- JSON容错解析
- 各文档类型处理
"""

import json
import sys
import unittest
from unittest.mock import MagicMock, patch

# 添加 backend 到 path
sys.path.insert(0, "/app/data/所有对话/主对话/BOM系统v4改造/backend")

from app.services.llm.document_parser import (
    DocumentParser,
    _extract_date,
    _extract_manufacturers,
    _extract_materials,
    _extract_price_change,
    _detect_doc_type,
    _regex_fallback_parse,
    _validate_event_structure,
)
from app.services.llm.base import LLMCallResult


# ═══════════════════════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════════════════════

def _make_valid_llm_response(events=None):
    """构造有效的 LLM 响应。"""
    if events is None:
        events = [{
            "event_type": "price_increase",
            "title": "MLCC涨价通知",
            "description": "村田宣布MLCC产品涨价15%",
            "affected_categories": ["MLCC"],
            "affected_manufacturers": ["村田"],
            "effective_date": "2024-07-01",
            "impact_level": "high",
            "price_change_pct": 15.0,
            "confidence": 0.9,
            "evidence_text": "自2024年7月1日起，MLCC产品价格上调15%"
        }]
    return {
        "events": events,
        "doc_summary": "本文档为供应商涨价通知",
        "doc_type_classified": "price_increase",
    }


class TestDocumentParser(unittest.TestCase):
    """T2-012 文档解析服务测试。"""

    def _make_service(self, mock_client=None):
        """创建测试用服务实例。"""
        if mock_client is None:
            mock_client = MagicMock()
            mock_client.available = True
        return DocumentParser(llm_client=mock_client), mock_client

    # ══════════════════════════════════════════════════════
    # 正常路径测试
    # ══════════════════════════════════════════════════════

    def test_01_successful_parse_price_increase(self):
        """LLM 调用成功，解析涨价函文档。"""
        svc, mock_client = self._make_service()
        mock_client._call.return_value = json.dumps(_make_valid_llm_response())

        result = svc.parse(
            text_content="关于MLCC产品调价通知，自2024年7月1日起涨价15%",
            doc_type="price_increase",
        )

        self.assertTrue(result.success)
        self.assertFalse(result.degraded)
        self.assertEqual(len(result.data["events"]), 1)
        self.assertEqual(result.data["events"][0]["event_type"], "price_increase")
        self.assertEqual(result.data["events"][0]["price_change_pct"], 15.0)
        self.assertGreater(result.latency_ms, 0)

    def test_02_successful_parse_shortage(self):
        """LLM 调用成功，解析缺货通知。"""
        svc, mock_client = self._make_service()
        response = _make_valid_llm_response(events=[{
            "event_type": "shortage",
            "title": "MCU供应紧张",
            "description": "ST MCU交期延长至20周",
            "affected_categories": ["MCU"],
            "affected_manufacturers": ["ST"],
            "effective_date": "2024-08-01",
            "impact_level": "medium",
            "price_change_pct": None,
            "confidence": 0.85,
            "evidence_text": "ST MCU交期延长至20周以上",
        }])
        mock_client._call.return_value = json.dumps(response)

        result = svc.parse(
            text_content="ST MCU交期延长通知，预计交期延长至20周",
            doc_type="shortage",
        )

        self.assertTrue(result.success)
        self.assertEqual(result.data["events"][0]["event_type"], "shortage")

    def test_03_successful_parse_report(self):
        """LLM 调用成功，解析行业报告（包含多个事件）。"""
        svc, mock_client = self._make_service()
        response = _make_valid_llm_response(events=[
            {
                "event_type": "price_increase",
                "title": "被动元件全面涨价",
                "description": "MLCC和电阻涨价",
                "affected_categories": ["MLCC", "电阻"],
                "affected_manufacturers": ["村田", "TDK"],
                "effective_date": "2024-07-01",
                "impact_level": "high",
                "price_change_pct": 10.0,
                "confidence": 0.88,
                "evidence_text": "被动元件全面涨价10%",
            },
            {
                "event_type": "shortage",
                "title": "车规MCU持续紧缺",
                "description": "车规MCU供不应求",
                "affected_categories": ["MCU"],
                "affected_manufacturers": ["英飞凌", "瑞萨"],
                "effective_date": "2024-06-01",
                "impact_level": "high",
                "price_change_pct": None,
                "confidence": 0.82,
                "evidence_text": "车规MCU持续紧缺",
            },
        ])
        mock_client._call.return_value = json.dumps(response)

        result = svc.parse(
            text_content="2024年Q2电子元器件行业报告...",
            doc_type="report",
        )

        self.assertTrue(result.success)
        self.assertEqual(len(result.data["events"]), 2)

    def test_04_empty_events_valid(self):
        """LLM 返回空事件列表但仍通过验证。"""
        svc, mock_client = self._make_service()
        response = {
            "events": [],
            "doc_summary": "本文档为一般性公司介绍，不含风险信息",
            "doc_type_classified": "other",
        }
        mock_client._call.return_value = json.dumps(response)

        result = svc.parse(text_content="公司简介文档", doc_type="auto")

        self.assertTrue(result.success)
        self.assertEqual(len(result.data["events"]), 0)

    def test_05_parse_interface_convenience(self):
        """parse() 便捷接口正确传递参数。"""
        svc, mock_client = self._make_service()
        mock_client._call.return_value = json.dumps(_make_valid_llm_response())

        result = svc.parse("测试文本", "price_increase")

        # 验证 _call 被调用
        call_args = mock_client._call.call_args
        system_prompt = call_args.kwargs.get("system_prompt", "")
        user_prompt = call_args.kwargs.get("user_prompt", "")

        self.assertIn("JSON", system_prompt)
        self.assertIn("测试文本", user_prompt)
        self.assertIn("price_increase", user_prompt)

    def test_06_doc_type_auto_hint(self):
        """doc_type=auto 时 prompt 包含自动识别提示。"""
        svc, mock_client = self._make_service()
        mock_client._call.return_value = json.dumps(_make_valid_llm_response())

        svc.parse("文本内容", "auto")

        call_args = mock_client._call.call_args
        user_prompt = call_args.kwargs.get("user_prompt", "")
        self.assertIn("自动识别", user_prompt)

    # ══════════════════════════════════════════════════════
    # 降级路径测试
    # ══════════════════════════════════════════════════════

    def test_10_degrade_no_api_key(self):
        """API Key 未配置时触发降级（正则提取）。"""
        mock_client = MagicMock()
        mock_client.available = False
        svc = DocumentParser(llm_client=mock_client)

        result = svc.parse(
            text_content="村田MLCC产品涨价15%，自2024-07-01起生效",
            doc_type="price_increase",
        )

        self.assertFalse(result.success)
        self.assertTrue(result.degraded)
        self.assertIn("API key", result.degrade_reason)
        # 降级时应仍能提取基本信息
        self.assertIn("events", result.data)

    def test_11_degrade_none_response(self):
        """LLM 返回 None 时触发降级。"""
        svc, mock_client = self._make_service()
        mock_client._call.return_value = None

        result = svc.parse("涨价通知：MLCC涨幅10%", doc_type="auto")

        self.assertTrue(result.degraded)
        self.assertFalse(result.success)

    def test_12_degrade_invalid_json(self):
        """LLM 返回非 JSON 时触发降级。"""
        svc, mock_client = self._make_service()
        mock_client._call.return_value = "这不是JSON格式的响应"

        result = svc.parse("一些文档内容", doc_type="auto")

        self.assertTrue(result.degraded)

    def test_13_degrade_missing_fields(self):
        """LLM JSON 缺少必要字段时触发降级。"""
        svc, mock_client = self._make_service()
        mock_client._call.return_value = json.dumps({"only_summary": "value"})

        result = svc.parse("一些文档", doc_type="auto")

        self.assertTrue(result.degraded)

    def test_14_degrade_exception(self):
        """LLM 调用抛异常时触发降级。"""
        svc, mock_client = self._make_service()
        mock_client._call.side_effect = Exception("Connection timeout")

        result = svc.parse("文档内容", doc_type="auto")

        self.assertTrue(result.degraded)
        self.assertIn("Connection timeout", result.error)

    def test_15_degrade_invalid_event_type(self):
        """LLM 返回无效事件类型时触发降级。"""
        svc, mock_client = self._make_service()
        response = {
            "events": [{
                "event_type": "invalid_type",  # 不在枚举中
                "title": "测试",
                "description": "测试",
                "affected_categories": [],
                "affected_manufacturers": [],
                "impact_level": "high",
                "confidence": 0.5,
                "evidence_text": "测试",
            }],
            "doc_summary": "测试摘要",
            "doc_type_classified": "price_increase",
        }
        mock_client._call.return_value = json.dumps(response)

        result = svc.parse("文档", doc_type="auto")

        self.assertTrue(result.degraded)

    # ══════════════════════════════════════════════════════
    # 正则提取测试
    # ══════════════════════════════════════════════════════

    def test_20_regex_extract_price_pct(self):
        """正则提取涨价幅度。"""
        self.assertAlmostEqual(_extract_price_change("MLCC产品涨价15%"), 15.0)
        self.assertAlmostEqual(_extract_price_change("价格上调约10%"), 10.0)
        self.assertAlmostEqual(_extract_price_change("涨幅为12.5%"), 12.5)
        self.assertAlmostEqual(_extract_price_change("提价8%"), 8.0)
        self.assertAlmostEqual(_extract_price_change("价格 上涨 5.5%"), 5.5)
        self.assertAlmostEqual(_extract_price_change("price increase by 20%"), 20.0)
        self.assertIsNone(_extract_price_change("没有提到涨幅"))

    def test_21_regex_extract_date(self):
        """正则提取日期。"""
        self.assertEqual(_extract_date("自2024年7月1日起"), "2024-07-01")
        self.assertEqual(_extract_date("生效日期2024-08-15"), "2024-08-15")
        self.assertEqual(_extract_date("2024/7/1执行"), "2024-07-01")
        self.assertEqual(_extract_date("2024-Q3开始"), "2024-07-01")
        self.assertIsNone(_extract_date("没有具体日期"))

    def test_22_regex_extract_materials(self):
        """正则提取物料品类。"""
        materials = _extract_materials("MLCC和MCU产品价格上涨")
        self.assertIn("MLCC", materials)
        self.assertIn("MCU", materials)

        materials = _extract_materials("电感、变压器、晶振缺货")
        self.assertIn("电感", materials)
        self.assertIn("变压器", materials)
        self.assertIn("晶振", materials)

        materials = _extract_materials("没有提到任何物料")
        self.assertEqual(materials, [])

    def test_23_regex_extract_manufacturers(self):
        """正则提取厂商名称。"""
        mfrs = _extract_manufacturers("村田和TDK宣布涨价")
        self.assertIn("村田", mfrs)
        self.assertIn("TDK", mfrs)

        mfrs = _extract_manufacturers("英飞凌和ST的MCU缺货")
        self.assertIn("英飞凌", mfrs)
        self.assertIn("ST", mfrs)

        mfrs = _extract_manufacturers("没有提到厂商")
        self.assertEqual(mfrs, [])

    def test_24_regex_detect_doc_type(self):
        """自动识别文档类型。"""
        self.assertEqual(_detect_doc_type("供应商涨价通知，MLCC涨价15%"), "price_increase")
        self.assertEqual(_detect_doc_type("缺货通知：MCU交期延长"), "shortage")
        self.assertEqual(_detect_doc_type("2024年电子元器件行业分析报告"), "report")
        self.assertEqual(_detect_doc_type("这是一份无关的文档"), "other")

    def test_25_regex_fallback_full(self):
        """完整正则降级路径验证。"""
        text = (
            "关于MLCC产品调价通知\n"
            "尊敬的客户，由于原材料成本上涨，我司决定自2024年7月1日起\n"
            "对MLCC产品价格上调15%。涉及村田、TDK等品牌。\n"
            "此调整影响范围包括0402/0603/0805等封装规格。"
        )

        result = _regex_fallback_parse(text, "auto")

        # 应提取出涨价事件
        self.assertIn("events", result)
        self.assertTrue(len(result["events"]) > 0)

        event = result["events"][0]
        self.assertEqual(event["event_type"], "price_increase")
        self.assertAlmostEqual(event["price_change_pct"], 15.0)
        self.assertAlmostEqual(event["confidence"], 0.3)  # 降级置信度
        self.assertEqual(event["effective_date"], "2024-07-01")
        self.assertIn("MLCC", event["affected_categories"])
        self.assertIn("村田", event["affected_manufacturers"])

        # 验证文档摘要
        self.assertIn("doc_summary", result)
        self.assertTrue(len(result["doc_summary"]) > 0)

        # 验证降级标记
        self.assertTrue(result.get("_degraded"))
        self.assertEqual(result.get("_degrade_method"), "regex")

    def test_26_regex_fallback_shortage_detection(self):
        """正则降级能检测缺货信息。"""
        text = "供应紧张通知：MCU产品交期延长至20周，缺货严重"
        result = _regex_fallback_parse(text, "auto")

        self.assertTrue(len(result["events"]) > 0)
        event = result["events"][0]
        self.assertEqual(event["event_type"], "shortage")
        self.assertAlmostEqual(event["confidence"], 0.3)

    def test_27_regex_fallback_empty_text(self):
        """空文本降级处理。"""
        result = _regex_fallback_parse("", "auto")
        self.assertEqual(result["events"], [])
        self.assertIn("doc_summary", result)

    # ══════════════════════════════════════════════════════
    # 输出验证测试
    # ══════════════════════════════════════════════════════

    def test_30_validate_event_structure_valid(self):
        """有效事件结构验证通过。"""
        event = {
            "event_type": "price_increase",
            "title": "测试",
            "description": "描述",
            "affected_categories": ["MLCC"],
            "affected_manufacturers": ["村田"],
            "impact_level": "high",
            "confidence": 0.9,
            "evidence_text": "原文",
        }
        self.assertTrue(_validate_event_structure(event))

    def test_31_validate_event_structure_missing_field(self):
        """缺少必要字段验证失败。"""
        event = {
            "event_type": "price_increase",
            "title": "测试",
            # 缺少 description 等字段
        }
        self.assertFalse(_validate_event_structure(event))

    def test_32_validate_output_method(self):
        """_validate_output 方法全面验证。"""
        svc, _ = self._make_service()

        # 有效输出
        valid = _make_valid_llm_response()
        self.assertTrue(svc._validate_output(valid))

        # 缺少 events
        invalid1 = {"doc_summary": "测试", "doc_type_classified": "other"}
        self.assertFalse(svc._validate_output(invalid1))

        # events 不是列表
        invalid2 = {"events": "not_a_list", "doc_summary": "测试", "doc_type_classified": "other"}
        self.assertFalse(svc._validate_output(invalid2))

        # doc_summary 为空
        invalid3 = {"events": [], "doc_summary": "", "doc_type_classified": "other"}
        self.assertFalse(svc._validate_output(invalid3))

        # 无效 doc_type_classified
        invalid4 = {"events": [], "doc_summary": "摘要", "doc_type_classified": "invalid"}
        self.assertFalse(svc._validate_output(invalid4))

    # ══════════════════════════════════════════════════════
    # JSON 容错解析测试
    # ══════════════════════════════════════════════════════

    def test_40_json_with_markdown_fences(self):
        """LLM 返回包含 ```json``` 标记的响应。"""
        svc, mock_client = self._make_service()
        raw = f'```json\n{json.dumps(_make_valid_llm_response())}\n```'
        mock_client._call.return_value = raw

        result = svc.parse("文档内容", "auto")
        self.assertTrue(result.success)

    def test_41_json_with_single_quotes(self):
        """LLM 返回使用单引号的 JSON（容错策略3）。"""
        svc, mock_client = self._make_service()
        raw = "{'events': [], 'doc_summary': '测试摘要内容', 'doc_type_classified': 'other'}"
        mock_client._call.return_value = raw

        result = svc.parse("文档内容", "auto")
        self.assertTrue(result.success)

    def test_42_json_with_trailing_comma(self):
        """LLM 返回含尾部逗号的 JSON（容错策略3）。"""
        svc, mock_client = self._make_service()
        raw = '{"events": [], "doc_summary": "测试摘要内容", "doc_type_classified": "other",}'
        mock_client._call.return_value = raw

        result = svc.parse("文档内容", "auto")
        self.assertTrue(result.success)

    # ══════════════════════════════════════════════════════
    # 服务属性验证
    # ══════════════════════════════════════════════════════

    def test_50_service_attributes(self):
        """验证服务类属性符合 PRD 规格。"""
        from app.services.llm.base import LLMServiceBase
        self.assertTrue(issubclass(DocumentParser, LLMServiceBase))
        self.assertEqual(DocumentParser.SERVICE_NAME, "DocumentParser")
        self.assertEqual(DocumentParser.DEFAULT_MAX_TOKENS, 3000)

    def test_51_parse_method_signature(self):
        """验证 parse() 方法签名。"""
        import inspect
        sig = inspect.signature(DocumentParser.parse)
        params = list(sig.parameters.keys())
        self.assertIn("text_content", params)
        self.assertIn("doc_type", params)
        # doc_type 默认值
        self.assertEqual(sig.parameters["doc_type"].default, "auto")

    def test_52_service_registered_in_init(self):
        """验证 DocumentParser 在 __init__.py 中注册。"""
        from app.services.llm import DocumentParser as ImportedParser
        self.assertIs(ImportedParser, DocumentParser)


if __name__ == "__main__":
    unittest.main()
