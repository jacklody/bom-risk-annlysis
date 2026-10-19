"""metals-api.com 免费 API 数据源。

免费层: 60 次/月请求配额，单次 GET 可查多种金属。
覆盖: Cu(铜), Al(铝), Ag(银), Sn(锡), Ni(镍), Zn(锌)
API 文档: https://metals-api.com/documentation
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import httpx

from app.config import settings
from app.services.sources.materials.base import MaterialPriceSource

logger = logging.getLogger(__name__)

# metals-api 符号 → 内部 material_key 映射
_METALS_API_SYMBOL_MAP: Dict[str, str] = {
    "XCU": "cu_cathode",
    "XAL": "al_ingot",
    "XAG": "ag_ingot",
    "XSN": "tin",
    "XNI": "nickel_powder",
    "XZN": "zinc",
}

# 反向映射
_MATERIAL_KEY_TO_SYMBOL: Dict[str, str] = {
    v: k for k, v in _METALS_API_SYMBOL_MAP.items()
}

# 铜的衍生品 (cu_foil/cu_ball/cu_terminal 均从 XCU 铜价派生)
_CU_DERIVATIVES = {"cu_foil", "cu_ball", "cu_terminal"}

# 铝的衍生品 (al_foil_anode/al_foil_cathode/al_metallization 从 XAL 铝价派生)
_AL_DERIVATIVES = {"al_foil_anode", "al_foil_cathode", "al_metallization"}

# 银的衍生品 (ag_paste 从 XAG 银价派生，乘以加工系数)
_AG_DERIVATIVES = {"ag_paste"}

# 镍的衍生品 (ni_plating 从 XNI 镍价派生)
_NI_DERIVATIVES = {"ni_plating"}


class MetalsAPISource(MaterialPriceSource):
    """metals-api.com 免费层数据源。"""

    source_name = "metals_api"

    BASE_URL = "https://metals-api.com/api/latest"

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or settings.metals_api_key
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=settings.api_query_timeout)
        return self._client

    async def is_available(self) -> bool:
        return bool(self._api_key)

    async def fetch_prices(self, material_keys: List[str]) -> Dict[str, Optional[float]]:
        if not self._api_key:
            logger.warning("metals_api key not configured, skipping fetch")
            return {k: None for k in material_keys}

        # 归类：哪些是 API 原生符号，哪些是衍生品
        api_symbols: set[str] = set()
        derivative_keys: Dict[str, str] = {}  # material_key → 基础 material_key

        for mk in material_keys:
            if mk in _MATERIAL_KEY_TO_SYMBOL:
                api_symbols.add(_MATERIAL_KEY_TO_SYMBOL[mk])
            elif mk in _CU_DERIVATIVES:
                api_symbols.add("XCU")
                derivative_keys[mk] = "cu_cathode"
            elif mk in _AL_DERIVATIVES:
                api_symbols.add("XAL")
                derivative_keys[mk] = "al_ingot"
            elif mk in _AG_DERIVATIVES:
                api_symbols.add("XAG")
                derivative_keys[mk] = "ag_ingot"
            elif mk in _NI_DERIVATIVES:
                api_symbols.add("XNI")
                derivative_keys[mk] = "nickel_powder"

        if not api_symbols:
            return {k: None for k in material_keys}

        try:
            client = await self._get_client()
            symbols_str = ",".join(sorted(api_symbols))
            resp = await client.get(
                self.BASE_URL,
                params={
                    "access_key": self._api_key,
                    "base": "CNY",  # 人民币计价
                    "symbols": symbols_str,
                },
            )
            resp.raise_for_status()
            data = resp.json()

            if not data.get("success"):
                logger.error(f"metals-api returned error: {data.get('error', {}).get('info', 'unknown')}")
                return {k: None for k in material_keys}

            rates = data.get("rates", {})

            # 构建基础价格映射
            base_prices: Dict[str, Optional[float]] = {}
            for symbol, mk in _METALS_API_SYMBOL_MAP.items():
                price = rates.get(symbol)
                if price is not None:
                    # metals-api 按 CNY/oz 返回贵金属 (Ag)，按 CNY/tonne 返回基础金属
                    if symbol == "XAG":
                        # 1 troy ounce ≈ 31.1035 克, 转换为 元/克
                        base_prices[mk] = round(float(price) / 31.1035, 2)
                    else:
                        base_prices[mk] = round(float(price), 2)
                else:
                    base_prices[mk] = None

            # 构建最终结果
            result: Dict[str, Optional[float]] = {}
            for mk in material_keys:
                if mk in base_prices:
                    result[mk] = base_prices[mk]
                elif mk in derivative_keys:
                    base_mk = derivative_keys[mk]
                    base_price = base_prices.get(base_mk)
                    result[mk] = base_price  # 衍生品价格 = 基础价格（加工系数在 material_mapping 中处理）
                else:
                    result[mk] = None

            logger.info(
                f"metals_api: fetched {sum(1 for v in result.values() if v is not None)}/{len(result)} prices"
            )
            return result

        except httpx.HTTPStatusError as e:
            logger.error(f"metals_api HTTP error: {e.response.status_code}")
            return {k: None for k in material_keys}
        except httpx.RequestError as e:
            logger.error(f"metals_api request error: {e}")
            return {k: None for k in material_keys}
        except Exception as e:
            logger.error(f"metals_api unexpected error: {e}")
            return {k: None for k in material_keys}

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None


# ── 配置兼容 ──
# 确保 settings 上有 metals_api_key 属性
if not hasattr(settings, "metals_api_key"):
    setattr(settings, "metals_api_key", "")
