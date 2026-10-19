"""SMM（上海有色网）数据源 — 付费API接口骨架。

覆盖: Cu(铜)/Al(铝)/Sn(锡)/Ni(镍)/Ag(银)/稀土/锂电材料
API文档: https://www.smm.cn/ (付费账号后获取)

骨架策略:
- 已配置 API Key + enabled=True 时，可调用 fetch_prices
- 未配置时 is_available 返回 False，fetch_prices 返回全 None（不报错）
- 风险引擎检测到该数据源不可用时自动降权，由 metals_api 等源兜底
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import httpx

from app.config import settings
from app.services.sources.materials.base import MaterialPriceSource

logger = logging.getLogger(__name__)

# SMM 品种代码 → 内部 material_key 映射
# 待接入真实API后根据实际接口文档扩展
_SMM_SYMBOL_MAP: Dict[str, str] = {
    "SMM-CU": "cu_cathode",
    "SMM-AL": "al_ingot",
    "SMM-SN": "tin",
    "SMM-NI": "nickel_powder",
    "SMM-AG": "ag_ingot",
    # 稀土/锂电品种待扩展
}

_MATERIAL_KEY_TO_SMM: Dict[str, str] = {
    v: k for k, v in _SMM_SYMBOL_MAP.items()
}


class SMMSource(MaterialPriceSource):
    """SMM 上海有色网数据源（骨架实现）。

    当 smm_api_key 为空或 smm_enabled=False 时：
    - is_available() 返回 False
    - fetch_prices() 返回全 None
    不会抛出异常，确保系统平稳降级。
    """

    source_name = "smm"

    # SMM API 基础地址（待接入后调整）
    BASE_URL = "https://api.smm.cn/v1"

    def __init__(self, api_key: str | None = None, enabled: bool | None = None):
        self._api_key = api_key if api_key is not None else settings.smm_api_key
        self._enabled = enabled if enabled is not None else settings.smm_enabled
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def is_configured(self) -> bool:
        """检查是否已配置 API Key 且已启用。"""
        return bool(self._api_key) and self._enabled

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(settings.api_query_timeout),
                headers={"Authorization": f"Bearer {self._api_key}"} if self._api_key else {},
            )
        return self._client

    async def is_available(self) -> bool:
        """检查数据源是否可用。未配置时返回 False。"""
        return self.is_configured

    async def fetch_prices(self, material_keys: List[str]) -> Dict[str, Optional[float]]:
        """获取指定材料的最新价格。

        未配置时返回全 None，不抛异常。
        """
        if not self.is_configured:
            logger.debug("SMM: 未配置 API Key 或未启用，跳过查询")
            return {k: None for k in material_keys}

        # 筛选出 SMM 覆盖的品种
        smm_symbols: set[str] = set()
        for mk in material_keys:
            if mk in _MATERIAL_KEY_TO_SMM:
                smm_symbols.add(_MATERIAL_KEY_TO_SMM[mk])

        if not smm_symbols:
            return {k: None for k in material_keys}

        try:
            client = await self._get_client()
            # ── 骨架：以下为真实 API 调用的占位结构 ──
            # TODO: 接入 SMM 真实 API 后实现具体请求逻辑
            symbols_str = ",".join(sorted(smm_symbols))
            resp = await client.get(
                f"{self.BASE_URL}/prices",
                params={"symbols": symbols_str, "currency": "CNY"},
            )
            resp.raise_for_status()
            data = resp.json()

            # 解析响应（骨架逻辑，待真实接口对接后调整）
            rates = data.get("data", {})
            result: Dict[str, Optional[float]] = {}
            for mk in material_keys:
                if mk in _MATERIAL_KEY_TO_SMM:
                    symbol = _MATERIAL_KEY_TO_SMM[mk]
                    price = rates.get(symbol)
                    result[mk] = round(float(price), 2) if price is not None else None
                else:
                    result[mk] = None

            logger.info(
                f"SMM: fetched {sum(1 for v in result.values() if v is not None)}/{len(result)} prices"
            )
            return result

        except httpx.HTTPStatusError as e:
            logger.error(f"SMM HTTP error: {e.response.status_code}")
            return {k: None for k in material_keys}
        except httpx.RequestError as e:
            logger.error(f"SMM request error: {e}")
            return {k: None for k in material_keys}
        except Exception as e:
            logger.error(f"SMM unexpected error: {e}")
            return {k: None for k in material_keys}

    async def close(self):
        """关闭 HTTP 客户端连接。"""
        if self._client:
            await self._client.aclose()
            self._client = None
