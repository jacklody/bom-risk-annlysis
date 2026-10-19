"""行情情报引擎 —— 基于品类/品牌/物料匹配当前的行情风险，输出业务建议。

数据源：app.knowledge.market_intel 中的 MARKET_INTEL_ENTRIES / CATEGORY_MARKET_RISK / HIGH_RISK_BRANDS
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.knowledge.market_intel import (
    CATEGORY_FUZZY_MAP,
    CATEGORY_MARKET_RISK,
    HIGH_RISK_BRANDS,
    MARKET_INTEL_ENTRIES,
)


@dataclass
class MarketIntelResult:
    """行情情报匹配结果"""

    matched: bool = False
    category: str = ""
    brand: str = ""
    matched_intel_count: int = 0
    risk_level: str = "gray"  # red / yellow / green / gray
    lead_time_weeks: Optional[int] = None
    price_impact_pct: Optional[float] = None
    summary: str = ""
    business_advice: str = ""
    intel_sources: list[str] = field(default_factory=list)


class MarketIntelEngine:
    """行情情报引擎：匹配物料与市场情报"""

    def __init__(self):
        self._category_index: dict[str, list] = {}
        for entry in MARKET_INTEL_ENTRIES:
            cat = entry.category
            if cat not in self._category_index:
                self._category_index[cat] = []
            self._category_index[cat].append(entry)

    def match_item(
        self,
        raw_part_number: str = "",
        raw_brand: str = "",
        raw_category: str = "",
        raw_description: str = "",
    ) -> MarketIntelResult:
        """匹配单个物料与行情情报"""
        norm_category = self._normalize_category(raw_category, raw_description, raw_part_number)
        norm_brand = self._normalize_brand(raw_brand)

        result = MarketIntelResult(category=norm_category, brand=norm_brand or "")

        # Step 1: 品类级行情风险
        cat_risk = CATEGORY_MARKET_RISK.get(norm_category)
        if cat_risk:
            result.risk_level = cat_risk["risk_level"]
            result.lead_time_weeks = cat_risk["lead_time_weeks"]
            result.price_impact_pct = cat_risk["price_impact_pct"]
            result.business_advice = cat_risk["advice"]
            result.matched = True

        # Step 2: 品牌级风险叠加
        if norm_brand and norm_brand in HIGH_RISK_BRANDS:
            brand_info = HIGH_RISK_BRANDS[norm_brand]
            if brand_info["priority"] == "critical":
                result.risk_level = "red"
            elif brand_info["priority"] == "high" and result.risk_level != "red":
                result.risk_level = "yellow"
            if not result.summary:
                result.summary = brand_info["reason"]

        # Step 3: 精确匹配 MARKET_INTEL_ENTRIES
        cat_entries = self._category_index.get(norm_category, [])
        brand_entries = [
            e for e in cat_entries
            if not e.brand or (norm_brand and e.brand.lower() in norm_brand.lower())
        ]
        if not brand_entries:
            brand_entries = [e for e in cat_entries if not e.brand]

        result.matched_intel_count = len(brand_entries)

        if brand_entries:
            result.matched = True
            best = max(brand_entries, key=lambda e: e.confidence)
            result.summary = best.summary
            result.business_advice = best.business_advice
            result.intel_sources = best.sources

            if best.severity == "critical":
                result.risk_level = "red"
            elif best.severity == "high" and result.risk_level not in ("red",):
                result.risk_level = "yellow"

        return result

    def _normalize_category(self, raw_category: str, raw_description: str, raw_part_number: str) -> str:
        """从原始品类文本/描述/型号中提取标准化品类"""
        text = f"{raw_category or ''} {raw_description or ''} {raw_part_number or ''}".strip()
        if not text:
            return ""

        # 先精确匹配
        for keyword, norm_cat in CATEGORY_FUZZY_MAP.items():
            if keyword.lower() in text.lower():
                return norm_cat

        # 从型号中推断
        pn = raw_part_number.strip().upper() if raw_part_number else ""
        if any(t in pn for t in ["STM32F", "STM32G", "STM32H", "STM32L"]):
            return "mcu"
        if any(t in pn for t in ["GD32", "AT32", "MM32", "PY32", "HC32"]):
            return "mcu"
        if "DRAM" in pn or "SDRAM" in pn or "DDR" in pn:
            return "dram"
        if "NAND" in pn or "FLASH" in pn or "NOR" in pn:
            return "nand"
        if "IGBT" in pn or "IPM" in pn:
            return "power_module"
        if any(t in pn for t in ["IRF", "IRL", "FDS", "AON", "BSC", "CSD", "NCE", "SVG"]):
            # MOSFET 常见前缀
            return "mosfet"

        return ""

    def _normalize_brand(self, raw_brand: str) -> str:
        """标准化品牌名"""
        if not raw_brand:
            return ""
        b = raw_brand.strip()
        # 斜杠分割：取第一个
        for sep in ("/", "、", ","):
            if sep in b:
                b = b.split(sep)[0].strip()
                break
        # 去括号内容
        if "(" in b:
            b = b.split("(")[0].strip()
        return b
