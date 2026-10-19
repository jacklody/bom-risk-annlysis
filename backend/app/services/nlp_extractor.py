"""事件提取器：关键词快速匹配 + LLM深度提取 双路径"""

import re
from app.services.llm_client import LLMClient
from app.knowledge.brand_category_map import ALIAS_TO_BRAND
from app.knowledge.event_templates import EVENT_TEMPLATES


class NLPExtractor:
    """
    事件提取器：
    1. 快速层：关键词匹配 → 置信度>0.8直接返回
    2. 深入层：LLM提取 → 低置信/新类型事件
    """

    def __init__(self):
        self.llm = LLMClient()

    def extract(self, text: str, source_name: str, title: str = "") -> dict:
        """主提取方法"""
        fast_result = self._fast_keyword_match(text, title)
        if fast_result.get("confidence", 0) > 0.8:
            return {**fast_result, "method": "keyword"}

        if self.llm.available:
            llm_result = self.llm.extract_event(text, title)
            if "error" not in llm_result:
                return {**llm_result, "method": "llm"}
            return {**fast_result, "method": "keyword_fallback",
                    "llm_error": llm_result.get("error", "")}

        return {**fast_result, "method": "keyword_only"}

    def _fast_keyword_match(self, text: str, title: str = "") -> dict:
        """快速关键词匹配层"""
        combined = (title + " " + text)[:3000]
        combined_lower = combined.lower()

        result = {
            "brand": None,
            "category": None,
            "event_type": "other",
            "severity": "unknown",
            "confidence": 0.0,
            "estimated_lead_time_impact_weeks": None,
            "estimated_price_impact_pct": None,
            "source_name": "",
            "raw_text": text,
            "raw_title": title,
        }

        # 品牌匹配（短别名用词边界防止误匹配，如 "st" 误匹配 "last"）
        matched_brands = set()
        for alias, std_name in ALIAS_TO_BRAND.items():
            if self._search_alias(alias, combined_lower):
                matched_brands.add(std_name)
        if len(matched_brands) == 1:
            result["brand"] = list(matched_brands)[0]
            result["confidence"] = max(result["confidence"], 0.6)
        elif len(matched_brands) > 1:
            result["confidence"] = 0.3

        # 品类匹配（事件模板）
        for template in EVENT_TEMPLATES:
            kw_list = template.get("keywords", [])
            hits = sum(1 for kw in kw_list if kw.lower() in combined_lower)
            if hits >= 2:
                cats = template.get("affected_categories", [])
                if cats:
                    result["category"] = cats[0]
                severity = template.get("severity")
                if severity:
                    result["severity"] = severity
                result["confidence"] = max(
                    result["confidence"],
                    min(0.7 + hits * 0.1, 0.9),
                )
                result["template_id"] = template["id"]
                break

        # 事件类型推断
        type_rules = [
            ("停产" in combined or "EOL" in combined.upper() or "NRND" in combined.upper(), "eol", 0.8),
            ("缺货" in combined or "短缺" in combined or "紧缺" in combined or "供不应求" in combined, "shortage", 0.7),
            ("涨价" in combined or "价格上涨" in combined or "涨幅" in combined or "调价" in combined, "price_increase", 0.7),
            ("产能" in combined and ("不足" in combined or "紧张" in combined or "受限" in combined), "capacity_issue", 0.6),
            ("关税" in combined or "出口管制" in combined or "制裁" in combined, "policy", 0.6),
        ]
        for condition, etype, conf in type_rules:
            if condition and result["event_type"] in ("other", None):
                result["event_type"] = etype
                result["confidence"] = max(result["confidence"], conf)

        return result

    @staticmethod
    def _search_alias(alias: str, text_lower: str) -> bool:
        """搜索别名，短别名(<=3字符)使用词边界防止误匹配"""
        if len(alias) <= 3:
            if alias.isascii() and alias.isalpha():
                # ASCII短别名: 两侧需为 非字母 或 字符串边界
                pattern = r'(?<![a-z])' + re.escape(alias) + r'(?![a-z])'
                return bool(re.search(pattern, text_lower))
            # 中文或其他字符: 直接子串匹配（已在文本短语中出现即是有效匹配）
            return alias in text_lower
        return alias in text_lower
