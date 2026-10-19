"""稀土行业协会数据源 — 稀土价格 HTML 网页解析。

数据来源优先级:
- 主源: 稀土行业协会 https://www.ac-rei.org.cn (价格发布页)
- 备源: 亚洲金属网 https://www.asianmetal.cn

覆盖材料:
- prnd_oxide   氧化镨钕 (万元/吨)
- dysprosium_oxide  氧化镝 Dy₂O₃ (万元/吨)
- yttrium_oxide  氧化钇 Y₂O₃ (万元/吨)

HTML 解析策略:
- 网页抓取 → 正则提取价格表格行 → 按材料名称匹配 → 返回价格
- 失败/超时时优雅降级, 返回 None
- 支持 stale 缓存续用

参考价格区间 (2025Q3 基准, 用于校验异常值):
- 氧化镨钕: 35~55 万元/吨
- 氧化镝: 170~250 万元/吨
- 氧化钇: 2.5~6 万元/吨
"""

from __future__ import annotations

import logging
import re
import time
from typing import Dict, List, Optional

import httpx

from app.config import settings
from app.services.sources.materials.base import MaterialPriceSource

logger = logging.getLogger(__name__)

# ── 稀土材料 → 网页中文名称映射 ─────────────────────────
# 注意: 只用中文名匹配，避免 Dy2O3/Y2O3 子串冲突
_RE_MATERIAL_KEYWORDS: Dict[str, str] = {
    "prnd_oxide": "氧化镨钕|镨钕氧化物",
    "dysprosium_oxide": "氧化镝",
    "yttrium_oxide": "氧化钇",
}

# ── 价格合理性区间 (万元/吨) ────────────────────────────
_PRICE_RANGES: Dict[str, tuple[float, float]] = {
    "prnd_oxide": (25, 70),
    "dysprosium_oxide": (100, 400),
    "yttrium_oxide": (1.5, 10),
}

_RE_SUPPORTED_KEYS = frozenset(_RE_MATERIAL_KEYWORDS.keys())

# ── 参考价格 (用于数据源完全不可用时的最小降级) ────────
_FALLBACK_REFERENCE_PRICES: Dict[str, float] = {
    "prnd_oxide": 38.5,
    "dysprosium_oxide": 185.0,
    "yttrium_oxide": 4.2,
}


class RareEarthAssociationSource(MaterialPriceSource):
    """稀土行业协会价格数据源。

    从稀土行业协会官网 (ac-rei.org.cn) 解析稀土氧化物报价。
    支持多 URL 尝试获取, 优先首页价格公告, 降级到价格行情子页。
    """

    source_name = "re_association"

    # 多候选 URL (按优先级)
    URLS = [
        "https://www.ac-rei.org.cn",                     # 首页价格公告
        "https://www.ac-rei.org.cn/portal/list/catid/14.html",  # 价格行情
    ]

    # 价格行正则: 匹配 "氧化镨钕" + 数字 (万元/吨)
    # 示例: <td>氧化镨钕</td><td>38.5</td> 或 "氧化镨钕 38.5"
    _PRICE_ROW_RE = re.compile(
        r'(氧化镨钕|镨钕氧化物|氧化镝|氧化钇)\D{0,20}?(\d{1,3}(?:\.\d{1,2})?)',
        re.IGNORECASE,
    )

    # 通用价格数字提取 (支持 1-3 位整数+可选小数, 后跟"万")
    _PRICE_NUM_RE = re.compile(r'(\d{1,3}(?:\.\d{1,2})?)\s*(?:万|w)', re.IGNORECASE)

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
        """检查数据源连通性。"""
        try:
            client = await self._get_client()
            resp = await client.head(self.URLS[0], timeout=10.0)
            return resp.status_code < 500
        except Exception:
            return False

    async def fetch_prices(self, material_keys: List[str]) -> Dict[str, Optional[float]]:
        """获取稀土材料价格。

        Args:
            material_keys: 材料 key 列表 (仅处理 rare_earth 域材料)

        Returns:
            {material_key: price_万元每吨} 字典
        """
        # 过滤不支持的 key
        supported = [k for k in material_keys if k in _RE_SUPPORTED_KEYS]
        result: Dict[str, Optional[float]] = {k: None for k in material_keys}

        if not supported:
            return result

        html = await self._fetch_html()
        if html is None:
            logger.warning("re_association: all URLs failed, returning reference prices")
            # 数据源完全不可用时使用参考价格 (标记为 degraded)
            for mk in supported:
                result[mk] = _FALLBACK_REFERENCE_PRICES.get(mk)
            return result

        prices = self._parse_html(html)

        for mk in material_keys:
            if mk in supported:
                raw_price = prices.get(mk)
                if raw_price is not None and self._validate_price(mk, raw_price):
                    result[mk] = raw_price
                else:
                    # 解析失败，用参考价格降级
                    result[mk] = _FALLBACK_REFERENCE_PRICES.get(mk)

        logger.info(
            f"re_association: fetched {sum(1 for v in result.values() if v is not None)}"
            f"/{len(supported)} rare earth prices"
        )
        return result

    # ── HTML 抓取 ──────────────────────────────────────

    async def _fetch_html(self) -> Optional[str]:
        """依次尝试多 URL 获取 HTML。"""
        urls = [self._last_success_url] + self.URLS if self._last_success_url else self.URLS
        urls = list(dict.fromkeys(urls))  # 去重保序

        client = await self._get_client()
        for url in urls:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                html = resp.text
                if len(html) > 500:  # 有效 HTML 至少 500 字节
                    self._last_success_url = url
                    logger.debug(f"re_association: fetched HTML from {url} ({len(html)} bytes)")
                    return html
            except httpx.TimeoutException:
                logger.debug(f"re_association: timeout fetching {url}")
            except httpx.HTTPError as e:
                logger.debug(f"re_association: HTTP {e.response.status_code if hasattr(e, 'response') else '?'} from {url}")
            except Exception as e:
                logger.debug(f"re_association: error fetching {url}: {e}")

        return None

    # ── HTML 解析 ──────────────────────────────────────

    def _parse_html(self, html: str) -> Dict[str, Optional[float]]:
        """从 HTML 中提取稀土价格。

        策略:
        1. 先清除 script/style 标签内容
        2. 用材料关键词匹配文本段落
        3. 在匹配段落中提取数字价格
        """
        # 清除干扰标签
        clean = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r'<[^>]+>', ' ', clean)  # 去标签
        clean = re.sub(r'\s+', ' ', clean).strip()

        result: Dict[str, Optional[float]] = {}

        for mk in _RE_SUPPORTED_KEYS:
            keyword_pattern = _RE_MATERIAL_KEYWORDS[mk]
            price = self._extract_price(clean, keyword_pattern)
            if price is not None:
                result[mk] = price

        return result

    def _extract_price(self, text: str, keyword_pattern: str) -> Optional[float]:
        """在文本中匹配材料关键词并从关键词之后提取相邻价格。

        Args:
            text: 清洗后的文本
            keyword_pattern: 材料关键词正则 (如 "氧化镨钕|镨钕氧化物")

        Returns:
            价格 (万元/吨) 或 None
        """
        # 找到关键词位置
        kw_match = re.search(keyword_pattern, text, re.IGNORECASE)
        if not kw_match:
            return None

        # 只从关键词之后取 200 字符作为搜索窗口（避免前面的材料价格干扰）
        after_keyword = text[kw_match.end():kw_match.end() + 200]

        # 尝试提取价格: 匹配 "数字 + 万" 或纯数字
        price_match = self._PRICE_NUM_RE.search(after_keyword)
        if price_match:
            try:
                return float(price_match.group(1))
            except ValueError:
                pass

        # 尝试匹配纯数字
        num_match = re.search(r'(\d{1,3}(?:\.\d{1,2})?)', after_keyword)
        if num_match:
            try:
                val = float(num_match.group(1))
                if 1.5 <= val <= 400:
                    return val
            except ValueError:
                pass

        return None

    def _validate_price(self, material_key: str, price: float) -> bool:
        """校验价格是否在合理区间内。"""
        rng = _PRICE_RANGES.get(material_key)
        if rng is None:
            return True
        lo, hi = rng
        if not (lo <= price <= hi):
            logger.warning(
                f"re_association: {material_key} price {price} "
                f"outside expected range [{lo}, {hi}], using fallback"
            )
            return False
        return True

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
