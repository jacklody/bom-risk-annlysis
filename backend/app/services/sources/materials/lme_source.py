"""LME（伦敦金属交易所）数据源 — 网页数据解析骨架。

覆盖: Cu(铜)/Al(铝)/Ni(镍)/Sn(锡)/Zn(锌)/Pb(铅)/Co(钴)
数据源: https://www.lme.com/en/prices/reports-and-data

骨架策略:
- 启用时通过网页解析获取 LME 官方价格
- 未启用时 is_available 返回 False，fetch_prices 返回全 None（不报错）
- LME 数据免费但需网页解析，稳定性低于 API 源
- 作为补充源与 metals_api/SMM 配合使用
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

import httpx

from app.config import settings
from app.services.sources.materials.base import MaterialPriceSource

logger = logging.getLogger(__name__)

# LME 品种 → 内部 material_key 映射
_LME_SYMBOL_MAP: Dict[str, str] = {
    "copper": "cu_cathode",
    "aluminium": "al_ingot",
    "nickel": "nickel_powder",
    "tin": "tin",
    "zinc": "zinc",
    "lead": "zinc",  # LME铅价可作为锌价参考（无独立铅 material_key 时）
}

_MATERIAL_KEY_TO_LME: Dict[str, str] = {
    v: k for k, v in _LME_SYMBOL_MAP.items()
}

# LME 价格页面中用于解析的正则（骨架占位，待真实页面结构确认）
_LME_PRICE_PATTERN = re.compile(
    r'(?P<metal>\w+)\s*.*?\$\s*(?P<price>[\d,]+(?:\.\d+)?)',
    re.IGNORECASE,
)


class LMESource(MaterialPriceSource):
    """LME 伦敦金属交易所数据源（骨架实现 — 网页解析）。

    当 lme_enabled=False 时：
    - is_available() 返回 False
    - fetch_prices() 返回全 None
    不会抛出异常，确保系统平稳降级。
    """

    source_name = "lme"

    def __init__(self, enabled: bool | None = None, data_url: str | None = None):
        self._enabled = enabled if enabled is not None else settings.lme_enabled
        self._data_url = data_url or settings.lme_data_url
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def is_configured(self) -> bool:
        """检查是否已启用。"""
        return self._enabled

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(settings.api_query_timeout),
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; BOM-RiskBot/1.0)",
                    "Accept": "text/html,application/xhtml+xml",
                },
            )
        return self._client

    async def is_available(self) -> bool:
        """检查数据源是否可用。未启用时返回 False。"""
        return self.is_configured

    async def fetch_prices(self, material_keys: List[str]) -> Dict[str, Optional[float]]:
        """获取 LME 官方价格（通过网页解析）。

        未启用时返回全 None，不抛异常。
        """
        if not self.is_configured:
            logger.debug("LME: 未启用，跳过查询")
            return {k: None for k in material_keys}

        # 筛选出 LME 覆盖的品种
        lme_symbols: set[str] = set()
        for mk in material_keys:
            if mk in _MATERIAL_KEY_TO_LME:
                lme_symbols.add(_MATERIAL_KEY_TO_LME[mk])

        if not lme_symbols:
            return {k: None for k in material_keys}

        try:
            client = await self._get_client()
            # ── 骨架：以下为网页解析的占位结构 ──
            # TODO: 接入 LME 真实网页后实现具体解析逻辑
            #
            # 预期流程:
            # 1. GET self._data_url 获取 HTML
            # 2. 用 BeautifulSoup / 正则 提取各金属的现货/期货价格
            # 3. 将 USD/tonne 转换为 CNY/tonne (如需)
            # 4. 构建返回字典

            resp = await client.get(self._data_url)
            resp.raise_for_status()
            html_content = resp.text

            # 骨架解析逻辑（占位）
            parsed_prices: Dict[str, float] = {}
            for match in _LME_PRICE_PATTERN.finditer(html_content):
                metal = match.group("metal").lower()
                price_str = match.group("price").replace(",", "")
                try:
                    parsed_prices[metal] = float(price_str)
                except (ValueError, TypeError):
                    continue

            # 构建返回结果
            result: Dict[str, Optional[float]] = {}
            for mk in material_keys:
                if mk in _MATERIAL_KEY_TO_LME:
                    symbol = _MATERIAL_KEY_TO_LME[mk]
                    price = parsed_prices.get(symbol)
                    result[mk] = round(price, 2) if price is not None else None
                else:
                    result[mk] = None

            logger.info(
                f"LME: fetched {sum(1 for v in result.values() if v is not None)}/{len(result)} prices"
            )
            return result

        except httpx.HTTPStatusError as e:
            logger.error(f"LME HTTP error: {e.response.status_code}")
            return {k: None for k in material_keys}
        except httpx.RequestError as e:
            logger.error(f"LME request error: {e}")
            return {k: None for k in material_keys}
        except Exception as e:
            logger.error(f"LME unexpected error: {e}")
            return {k: None for k in material_keys}

    async def close(self):
        """关闭 HTTP 客户端连接。"""
        if self._client:
            await self._client.aclose()
            self._client = None
