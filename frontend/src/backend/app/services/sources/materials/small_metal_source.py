"""小金属/稀散金属数据源 — 亚洲金属网 + 百川盈孚 HTML 解析。

数据来源:
- 亚洲金属网 https://www.asianmetal.cn — 钽粉/钽丝/碳酸钡/小金属报价
- 百川盈孚 https://www.baiinfo.com — 碳酸钡/化工原料报价

覆盖材料 (rare_earth 域 + 备源):
- tantalum_powder  钽粉 (元/公斤) — 主源 asian_metal
- tantalum_wire    钽丝 (元/公斤) — 主源 asian_metal
- barium_carbonate 碳酸钡 BaCO₃ (元/吨) — 主源 baiinfo, 备源 asian_metal

参考价格区间 (2025Q3 基准):
- 钽粉: 3500~6000 元/公斤
- 钽丝: 2500~4500 元/公斤
- 碳酸钡: 2500~4500 元/吨
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

import httpx

from app.config import settings
from app.services.sources.materials.base import MaterialPriceSource

logger = logging.getLogger(__name__)

# ── 小金属材料 → 网页中文名称映射 ──────────────────────
_SM_MATERIAL_KEYWORDS: Dict[str, str] = {
    "tantalum_powder": "钽粉|金属钽|钽Ta",
    "tantalum_wire": "钽丝",
    "barium_carbonate": "碳酸钡|BaCO3",
}

# ── 价格合理性区间 ─────────────────────────────────────
_SM_PRICE_RANGES: Dict[str, tuple[float, float]] = {
    "tantalum_powder": (2000, 8000),     # 钽粉 元/公斤
    "tantalum_wire": (1500, 6000),       # 钽丝 元/公斤
    "barium_carbonate": (1500, 6000),    # 碳酸钡 元/吨
}

_SM_SUPPORTED_KEYS = frozenset(_SM_MATERIAL_KEYWORDS.keys())

# ── 参考价格 (降级用) ──────────────────────────────────
_SM_FALLBACK_PRICES: Dict[str, float] = {
    "tantalum_powder": 4500.0,
    "tantalum_wire": 3200.0,
    "barium_carbonate": 3200.0,
}


class AsianMetalSource(MaterialPriceSource):
    """亚洲金属网 (asianmetal.cn) 价格数据源。

    抓取钽、碳酸钡等小金属/稀散金属报价。
    同时可作为稀土材料的备源。
    """

    source_name = "asian_metal"

    URLS = [
        "https://www.asianmetal.cn",
        "https://www.asianmetal.cn/market/price/",
    ]

    _PRICE_NUM_RE = re.compile(
        r'(\d{1,5}(?:,\d{3})*(?:\.\d{1,2})?)\s*(?:元|CNY|RMB)',
        re.IGNORECASE,
    )
    _PURE_NUM_RE = re.compile(r'(\d{3,5}(?:\.\d{1,2})?)')

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
        supported = [k for k in material_keys if k in _SM_SUPPORTED_KEYS]
        result: Dict[str, Optional[float]] = {k: None for k in material_keys}

        if not supported:
            return result

        html = await self._fetch_html()
        if html is None:
            logger.warning("asian_metal: all URLs failed, using fallback prices")
            for mk in supported:
                result[mk] = _SM_FALLBACK_PRICES.get(mk)
            return result

        prices = self._parse_html(html)

        for mk in material_keys:
            if mk in supported:
                raw_price = prices.get(mk)
                if raw_price is not None and self._validate_price(mk, raw_price):
                    result[mk] = raw_price
                else:
                    result[mk] = _SM_FALLBACK_PRICES.get(mk)

        logger.info(
            f"asian_metal: fetched {sum(1 for v in result.values() if v is not None)}"
            f"/{len(supported)} small metal prices"
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
                logger.debug(f"asian_metal: error fetching {url}: {e}")

        return None

    def _parse_html(self, html: str) -> Dict[str, Optional[float]]:
        clean = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r'<[^>]+>', ' ', clean)
        clean = re.sub(r'\s+', ' ', clean).strip()

        result: Dict[str, Optional[float]] = {}
        for mk in _SM_SUPPORTED_KEYS:
            keyword_pattern = _SM_MATERIAL_KEYWORDS[mk]
            price = self._extract_price(clean, keyword_pattern)
            if price is not None:
                result[mk] = price

        return result

    def _extract_price(self, text: str, keyword_pattern: str) -> Optional[float]:
        kw_match = re.search(keyword_pattern, text, re.IGNORECASE)
        if not kw_match:
            return None

        # 只从关键词之后取 200 字符
        after_keyword = text[kw_match.end():kw_match.end() + 200]

        # 尝试匹配 "X元/公斤" 或 "X CNY" 格式
        price_match = self._PRICE_NUM_RE.search(after_keyword)
        if price_match:
            try:
                val_str = price_match.group(1).replace(",", "")
                return float(val_str)
            except ValueError:
                pass

        # 尝试匹配纯数字
        num_match = self._PURE_NUM_RE.search(after_keyword)
        if num_match:
            try:
                val = float(num_match.group(1))
                if 1000 <= val <= 10000:
                    return val
            except ValueError:
                pass

        return None

    def _validate_price(self, material_key: str, price: float) -> bool:
        rng = _SM_PRICE_RANGES.get(material_key)
        if rng is None:
            return True
        lo, hi = rng
        if not (lo <= price <= hi):
            logger.warning(
                f"asian_metal: {material_key} price {price} "
                f"outside range [{lo}, {hi}], using fallback"
            )
            return False
        return True

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None


class BaiinfoSource(MaterialPriceSource):
    """百川盈孚 (baiinfo.com) 化工/小金属数据源。

    覆盖: 碳酸钡、电解液等化工原料报价。
    """

    source_name = "baiinfo"

    URLS = [
        "https://www.baiinfo.com",
        "https://www.baiinfo.com/market/price/",
    ]

    _PRICE_NUM_RE = re.compile(
        r'(\d{1,5}(?:\.\d{1,2})?)\s*(?:元|CNY)',
        re.IGNORECASE,
    )
    _PURE_NUM_RE = re.compile(r'(\d{3,5}(?:\.\d{1,2})?)')

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
        """百川盈孚当前支持: barium_carbonate。"""
        supported = {"barium_carbonate"}
        mine = [k for k in material_keys if k in supported]
        result: Dict[str, Optional[float]] = {k: None for k in material_keys}

        if not mine:
            return result

        html = await self._fetch_html()
        if html is None:
            for mk in mine:
                result[mk] = _SM_FALLBACK_PRICES.get(mk)
            return result

        prices = self._parse_html(html)
        for mk in material_keys:
            if mk in mine:
                raw_price = prices.get(mk)
                if raw_price is not None and self._validate_price(mk, raw_price):
                    result[mk] = raw_price
                else:
                    result[mk] = _SM_FALLBACK_PRICES.get(mk)

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
                logger.debug(f"baiinfo: error fetching {url}: {e}")

        return None

    def _parse_html(self, html: str) -> Dict[str, Optional[float]]:
        clean = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r'<[^>]+>', ' ', clean)
        clean = re.sub(r'\s+', ' ', clean).strip()

        result: Dict[str, Optional[float]] = {}
        # 碳酸钡
        kw_match = re.search(r'碳酸钡|BaCO3', clean, re.IGNORECASE)
        if kw_match:
            after = clean[kw_match.end():kw_match.end() + 100]
            num_match = self._PURE_NUM_RE.search(after)
            if num_match:
                try:
                    val = float(num_match.group(1))
                    if 1500 <= val <= 6000:
                        result["barium_carbonate"] = val
                except ValueError:
                    pass

        return result

    def _validate_price(self, material_key: str, price: float) -> bool:
        rng = _SM_PRICE_RANGES.get(material_key)
        if rng is None:
            return True
        lo, hi = rng
        if not (lo <= price <= hi):
            logger.warning(f"baiinfo: {material_key} price {price} outside range [{lo}, {hi}]")
            return False
        return True

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
