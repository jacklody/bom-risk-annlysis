"""化工&非金属数据源 — 生意社(100ppi) + 卓创资讯(sci99) HTML 解析。

数据来源:
- 生意社 https://www.100ppi.com — 化工原料价格(主源)
- 卓创资讯 https://www.sci99.com — 钛白粉等精细化工(备源)

覆盖材料 (chemical 域):
- ba_resin           双酚A树脂    (元/吨)
- epoxy_resin        环氧树脂      (元/吨)
- polypropylene      聚丙烯PP膜    (元/吨)
- polyester_pet      聚酯PET膜     (元/吨)
- titanium_dioxide   钛白粉TiO₂   (元/吨)
- manganese_dioxide  二氧化锰MnO₂ (元/吨)

参考价格区间 (2025Q3 基准):
- 双酚A树脂:     8000~18000 元/吨
- 环氧树脂:      10000~25000 元/吨
- 聚丙烯PP膜:    6000~12000 元/吨
- 聚酯PET膜:     6000~15000 元/吨
- 钛白粉TiO₂:    12000~22000 元/吨
- 二氧化锰MnO₂:  8000~18000 元/吨
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

import httpx

from app.config import settings
from app.services.sources.materials.base import MaterialPriceSource

logger = logging.getLogger(__name__)

# ── 化工材料 → 中文名称映射 ─────────────────────────────
_CHEM_MATERIAL_KEYWORDS: Dict[str, str] = {
    "ba_resin": "双酚A|双酚\\s*A|BPA",
    "epoxy_resin": "环氧树脂|EP树脂",
    "polypropylene": "聚丙烯|PP粒料|PP膜",
    "polyester_pet": "PET|聚酯|PET切片|PET膜|PET树脂",
    "titanium_dioxide": "钛白粉|二氧化钛|TiO2",
    "manganese_dioxide": "二氧化锰|MnO2|电解锰",
}

# ── 价格合理性区间 (元/吨) ──────────────────────────────
_CHEM_PRICE_RANGES: Dict[str, tuple[float, float]] = {
    "ba_resin": (5000, 25000),
    "epoxy_resin": (8000, 35000),
    "polypropylene": (4000, 18000),
    "polyester_pet": (4000, 20000),
    "titanium_dioxide": (8000, 30000),
    "manganese_dioxide": (5000, 25000),
}

_CHEM_SUPPORTED_KEYS = frozenset(_CHEM_MATERIAL_KEYWORDS.keys())

# ── 参考价格 (降级用) ──────────────────────────────────
_CHEM_FALLBACK_PRICES: Dict[str, float] = {
    "ba_resin": 13000.0,
    "epoxy_resin": 15000.0,
    "polypropylene": 8000.0,
    "polyester_pet": 9000.0,
    "titanium_dioxide": 16000.0,
    "manganese_dioxide": 12000.0,
}


class Chemical100ppiSource(MaterialPriceSource):
    """生意社 (100ppi.com) 化工原料价格数据源。

    覆盖 all 6 种 chemical 域材料。
    """

    source_name = "chem_100ppi"

    URLS = [
        "https://www.100ppi.com",
        "https://www.100ppi.com/price/",
        "https://www.100ppi.com/market/",
    ]

    # 价格数字: 匹配 "数字 元/吨" 或 "数字CNY" (距离不超过3字符)
    _PRICE_RE = re.compile(
        r'(\d{1,6}(?:,\d{3})*(?:\.\d{1,2})?)\s{0,3}(?:元/吨|元(?!/)|CNY|RMB)',
        re.IGNORECASE,
    )
    _PURE_NUM_RE = re.compile(r'(\d{4,6}(?:\.\d{1,2})?)')

    def __init__(self, timeout: float | None = None):
        self._timeout = timeout or getattr(settings, "api_query_timeout", 15.0)
        self._client: Optional[httpx.AsyncClient] = None
        self._last_success_url: Optional[str] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/125.0.0.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                },
                follow_redirects=True,
            )
        return self._client

    async def is_available(self) -> bool:
        try:
            client = await self._get_client()
            resp = await client.head(self.URLS[0], timeout=10.0)
            return resp.status_code < 500
        except Exception:
            return False

    async def fetch_prices(self, material_keys: List[str]) -> Dict[str, Optional[float]]:
        supported = [k for k in material_keys if k in _CHEM_SUPPORTED_KEYS]
        result: Dict[str, Optional[float]] = {k: None for k in material_keys}

        if not supported:
            return result

        html = await self._fetch_html()
        if html is None:
            logger.warning("chem_100ppi: all URLs failed, using fallback prices")
            for mk in supported:
                result[mk] = _CHEM_FALLBACK_PRICES.get(mk)
            return result

        prices = self._parse_html(html)

        for mk in material_keys:
            if mk in supported:
                raw_price = prices.get(mk)
                if raw_price is not None and self._validate_price(mk, raw_price):
                    result[mk] = raw_price
                else:
                    result[mk] = _CHEM_FALLBACK_PRICES.get(mk)

        # 不在 log 中比对 fallback (涉及复杂迭代)
        fetched = sum(
            1 for mk in material_keys
            if mk in supported
            and result.get(mk) is not None
            and result.get(mk) != _CHEM_FALLBACK_PRICES.get(mk)
        )
        logger.info(
            f"chem_100ppi: fetched {fetched}/{len(supported)} chemical prices"
        )
        return result

    async def _fetch_html(self) -> Optional[str]:
        urls = [self._last_success_url] + self.URLS if self._last_success_url else self.URLS
        urls = list(dict.fromkeys(urls))

        client = await self._get_client()
        for url in urls:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                html = resp.text
                if len(html) > 500:
                    self._last_success_url = url
                    return html
            except Exception as e:
                logger.debug(f"chem_100ppi: error fetching {url}: {e}")

        return None

    def _parse_html(self, html: str) -> Dict[str, Optional[float]]:
        clean = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r'<[^>]+>', ' ', clean)
        clean = re.sub(r'\s+', ' ', clean).strip()

        result: Dict[str, Optional[float]] = {}
        for mk in _CHEM_SUPPORTED_KEYS:
            keyword_pattern = _CHEM_MATERIAL_KEYWORDS[mk]
            price = self._extract_price(clean, keyword_pattern)
            if price is not None:
                result[mk] = price

        return result

    def _extract_price(self, text: str, keyword_pattern: str) -> Optional[float]:
        """从关键词后提取价格。优先取最近数字，再尝试带单位的价格。"""
        kw_match = re.search(keyword_pattern, text, re.IGNORECASE)
        if not kw_match:
            return None

        after_keyword = text[kw_match.end():kw_match.end() + 50]

        # 优先: 取关键词后最近的有效数字 (元/吨可能离当前关键词很远)
        num_match = self._PURE_NUM_RE.search(after_keyword)
        if num_match:
            try:
                val = float(num_match.group(1))
                if 4000 <= val <= 35000:
                    return val
            except ValueError:
                pass

        # 备选: 带"元/吨"等单位的显式价格标记
        price_match = self._PRICE_RE.search(after_keyword)
        if price_match:
            try:
                val_str = price_match.group(1).replace(",", "")
                return float(val_str)
            except ValueError:
                pass

        return None

    def _validate_price(self, material_key: str, price: float) -> bool:
        rng = _CHEM_PRICE_RANGES.get(material_key)
        if rng is None:
            return True
        lo, hi = rng
        if not (lo <= price <= hi):
            logger.warning(
                f"chem_100ppi: {material_key} price {price} "
                f"outside range [{lo}, {hi}], using fallback"
            )
            return False
        return True

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None


class Sci99Source(MaterialPriceSource):
    """卓创资讯 (sci99.com) 化工价格数据源 (备源)。

    当前作为钛白粉等精细化工材料的备源。
    """

    source_name = "sci99"

    URLS = [
        "https://www.sci99.com",
        "https://www.sci99.com/price/",
    ]

    _PRICE_RE = re.compile(
        r'(\d{1,6}(?:,\d{3})*(?:\.\d{1,2})?)\s*(?:元/吨|元|CNY)',
        re.IGNORECASE,
    )
    _PURE_NUM_RE = re.compile(r'(\d{4,6}(?:\.\d{1,2})?)')

    def __init__(self, timeout: float | None = None):
        self._timeout = timeout or getattr(settings, "api_query_timeout", 15.0)
        self._client: Optional[httpx.AsyncClient] = None
        self._last_success_url: Optional[str] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/125.0.0.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                },
                follow_redirects=True,
            )
        return self._client

    async def is_available(self) -> bool:
        try:
            client = await self._get_client()
            resp = await client.head(self.URLS[0], timeout=10.0)
            return resp.status_code < 500
        except Exception:
            return False

    async def fetch_prices(self, material_keys: List[str]) -> Dict[str, Optional[float]]:
        supported = {"titanium_dioxide"} & set(material_keys)
        mine = list(supported)
        result: Dict[str, Optional[float]] = {k: None for k in material_keys}

        if not mine:
            return result

        html = await self._fetch_html()
        if html is None:
            for mk in mine:
                result[mk] = _CHEM_FALLBACK_PRICES.get(mk)
            return result

        prices = self._parse_html(html)
        for mk in material_keys:
            if mk in mine:
                raw_price = prices.get(mk)
                if raw_price is not None and self._validate_price(mk, raw_price):
                    result[mk] = raw_price
                else:
                    result[mk] = _CHEM_FALLBACK_PRICES.get(mk)

        return result

    async def _fetch_html(self) -> Optional[str]:
        urls = [self._last_success_url] + self.URLS if self._last_success_url else self.URLS
        urls = list(dict.fromkeys(urls))

        client = await self._get_client()
        for url in urls:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                html = resp.text
                if len(html) > 500:
                    self._last_success_url = url
                    return html
            except Exception as e:
                logger.debug(f"sci99: error fetching {url}: {e}")

        return None

    def _parse_html(self, html: str) -> Dict[str, Optional[float]]:
        clean = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r'<[^>]+>', ' ', clean)
        clean = re.sub(r'\s+', ' ', clean).strip()

        result: Dict[str, Optional[float]] = {}
        # 钛白粉
        kw_match = re.search(r'钛白粉|二氧化钛|TiO2', clean, re.IGNORECASE)
        if kw_match:
            after = clean[kw_match.end():kw_match.end() + 50]
            num_match = self._PURE_NUM_RE.search(after)
            if num_match:
                try:
                    val = float(num_match.group(1))
                    if 8000 <= val <= 30000:
                        result["titanium_dioxide"] = val
                except ValueError:
                    pass

        return result

    def _validate_price(self, material_key: str, price: float) -> bool:
        rng = _CHEM_PRICE_RANGES.get(material_key)
        if rng is None:
            return True
        lo, hi = rng
        if not (lo <= price <= hi):
            logger.warning(f"sci99: {material_key} price {price} outside range [{lo}, {hi}]")
            return False
        return True

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
