"""DigiKey API 数据源 — OAuth2 Client Credentials 认证。

注册地址: https://developer.digikey.com/
认证方式: OAuth2 Client Credentials (client_id + client_secret)

返回：实时库存、价格、工厂交期(周→天)、生命周期状态(在售/停产等)、PCN 变更通知
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

import httpx
from app.config import settings

from .base import BaseSource, SourceResult

logger = logging.getLogger(__name__)

DIGIKEY_OAUTH_URL = "https://api.digikey.com/v1/oauth2/token"
DIGIKEY_SEARCH_URL = "https://api.digikey.com/products/v4/search/keyword"


class DigiKeySource(BaseSource):
    """DigiKey 数据源 — OAuth2 + Product Information V4"""

    source_name = "digikey"

    def __init__(self, client_id: str = "", client_secret: str = ""):
        self.client_id = client_id or settings.digikey_client_id
        self.client_secret = client_secret or settings.digikey_client_secret
        self._token: Optional[str] = None
        self._token_expiry: float = 0.0
        self._client: Optional[httpx.AsyncClient] = None
        self._client_loop: Optional[asyncio.AbstractEventLoop] = None

    @property
    def is_configured(self) -> bool:
        return bool(settings.digikey_enabled and self.client_id and self.client_secret)

    async def _get_client(self) -> httpx.AsyncClient:
        current_loop = asyncio.get_running_loop()
        if self._client is not None and self._client_loop is None and not self._client.is_closed:
            self._client_loop = current_loop
            return self._client
        if (
            self._client is None
            or self._client_loop is not current_loop
            or self._client.is_closed
        ):
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(15.0),
                follow_redirects=True,
            )
            self._client_loop = current_loop
        return self._client

    async def _get_token(self) -> Optional[str]:
        now = time.monotonic()
        if self._token and now < self._token_expiry - 30:
            return self._token

        client = await self._get_client()
        try:
            response = await client.post(
                DIGIKEY_OAUTH_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials",
                },
            )
            response.raise_for_status()
            data = response.json()
            self._token = data.get("access_token", "")
            self._token_expiry = now + data.get("expires_in", 600)
            return self._token
        except Exception as exc:
            logger.warning(f"DigiKey OAuth failed: {exc}")
            return None

    async def health_check(self) -> bool:
        if not self.is_configured:
            return False
        try:
            result = await self.query_by_mpn("STM32F103C8T6")
            return result is not None and result.match_status == "hit"
        except Exception:
            return False

    async def query_by_mpn(self, mpn: str) -> SourceResult:
        if not self.is_configured:
            return SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                match_status="not_configured",
                error_reason="DigiKey ClientId/ClientSecret 未配置",
            )

        clean = self.clean_mpn(mpn)
        if not clean:
            return SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                match_status="missing_mpn",
                error_reason="物料型号为空，无法查询 DigiKey",
            )

        token = await self._get_token()
        if not token:
            return SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                match_status="auth_failed",
                error_reason="DigiKey OAuth Token 获取失败",
            )

        client = await self._get_client()

        try:
            response = await client.post(
                DIGIKEY_SEARCH_URL,
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-DIGIKEY-Client-Id": self.client_id,
                    "X-DIGIKEY-Locale-Site": "CN",
                    "X-DIGIKEY-Locale-Language": "zh",
                    "X-DIGIKEY-Locale-Currency": "CNY",
                    "Content-Type": "application/json",
                },
                json={"Keywords": clean, "Limit": 3},
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            return SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                match_status="timeout",
                error_reason=str(exc) or "DigiKey 查询超时",
            )
        except Exception as exc:
            return SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                match_status="request_failed",
                error_reason=str(exc) or "DigiKey 请求失败",
            )

        try:
            data = response.json()
            products = data.get("Products", [])
        except Exception as exc:
            return SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                match_status="parse_failed",
                error_reason=str(exc) or "DigiKey 响应解析失败",
            )

        if not products:
            return SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                is_available=False,
                match_status="not_found",
                error_reason="DigiKey 暂未命中该型号",
            )

        try:
            p = products[0]
            qty = p.get("QuantityAvailable", 0) or 0
            price = p.get("UnitPrice", None)
            lead_weeks_str = str(p.get("ManufacturerLeadWeeks", "") or "")
            lead_days = None
            try:
                lead_days = int(lead_weeks_str) * 7
            except (ValueError, TypeError):
                pass
            lifecycle = p.get("ProductStatus", {}).get("Status", "") or ""
            mfr = p.get("Manufacturer", {}).get("Name", "") or ""
            mpn_matched = p.get("ManufacturerProductNumber", "") or ""
            raw_summary = f"DigiKey 命中 {mpn_matched or clean}，库存{qty}，状态{lifecycle}"

            return SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                mpn_matched=mpn_matched,
                manufacturer=mfr,
                total_stock=qty,
                lead_time_days=lead_days,
                unit_price=price,
                currency="CNY",
                lifecycle_status=lifecycle,
                match_status="hit",
                raw_summary=raw_summary,
                is_available=True,
                raw_response=p,
            )
        except Exception as exc:
            logger.warning(f"DigiKey response parse failed for '{clean}': {exc}")
            return SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                match_status="parse_failed",
                error_reason=str(exc) or "DigiKey 响应字段解析失败",
            )

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
            self._client_loop = None
