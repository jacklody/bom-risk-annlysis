"""Mouser API 数据源 — 免费注册获取 API Key 后使用。

注册地址: https://www.mouser.com/api-search/
频率限制: 30次/分钟

返回：实时库存、工厂交期(天)、阶梯价格、生命周期状态
"""

from __future__ import annotations

import asyncio
import logging
import re as _re
from typing import Optional

import httpx
from app.config import settings

from .base import BaseSource, SourceResult

logger = logging.getLogger(__name__)

MOUSER_API_BASE = "https://api.mouser.com/api/v1"


class MouserSource(BaseSource):
    """Mouser 数据源 — 实时库存 + 工厂交期(天) + 生命周期"""

    source_name = "mouser"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or settings.mouser_api_key
        self._client: Optional[httpx.AsyncClient] = None
        self._client_loop: Optional[asyncio.AbstractEventLoop] = None

    @property
    def is_configured(self) -> bool:
        return bool(settings.mouser_enabled and self.api_key)

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
                error_reason="Mouser API Key 未配置",
            )

        clean = self.clean_mpn(mpn)
        if not clean:
            return SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                match_status="missing_mpn",
                error_reason="物料型号为空，无法查询 Mouser",
            )

        client = await self._get_client()

        try:
            response = await client.post(
                f"{MOUSER_API_BASE}/search/keyword",
                params={"apiKey": self.api_key},
                headers={"Content-Type": "application/json"},
                json={"SearchByKeywordRequest": {"keyword": clean, "records": 3, "startingRecord": 0}},
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            logger.warning(f"Mouser query timeout for '{clean}': {exc}")
            return SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                match_status="timeout",
                error_reason=str(exc) or "Mouser 查询超时",
            )
        except Exception as exc:
            logger.warning(f"Mouser query failed for '{clean}': {exc}")
            return SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                match_status="request_failed",
                error_reason=str(exc) or "Mouser 请求失败",
            )

        try:
            data = response.json()
            parts = data.get("SearchResults", {}).get("Parts", [])
        except Exception as exc:
            return SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                match_status="parse_failed",
                error_reason=str(exc) or "Mouser 响应解析失败",
            )

        if not parts:
            return SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                is_available=False,
                match_status="not_found",
                error_reason="Mouser 暂未命中该型号",
            )

        try:
            best = parts[0]

            availability = best.get("Availability", "") or ""
            total_stock = self._parse_stock(availability)

            lead_time_days = None
            lead_time_display = availability
            if "factory lead time" in availability.lower():
                m = _re.search(r'(\d+)\s*Days?\s*[Ff]actory\s*[Ll]ead\s*[Tt]ime', availability)
                if m:
                    lead_time_days = int(m.group(1))

            price_breaks_data = best.get("PriceBreaks", [])
            price_breaks = []
            unit_price = None
            for pb in price_breaks_data:
                qty = pb.get("Quantity", 0)
                price_str = str(pb.get("Price", ""))
                try:
                    price = float(price_str.replace("¥", "").replace("$", "").replace(",", "").strip())
                except (ValueError, TypeError):
                    price = 0.0
                price_breaks.append({"qty": qty, "price": price, "currency": "USD"})
                if unit_price is None and qty >= 1:
                    unit_price = price

            moq = best.get("Min", 1) or 1
            manufacturer_part = best.get("ManufacturerPartNumber", "")
            lifecycle = best.get("LifecycleStatus", "") or ""
            raw_summary = f"Mouser 命中 {manufacturer_part or clean}，库存{total_stock}"

            return SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                mpn_matched=str(manufacturer_part),
                manufacturer=str(best.get("Manufacturer", "")),
                total_stock=total_stock,
                lead_time_days=lead_time_days,
                lead_time_display=lead_time_display,
                unit_price=unit_price,
                price_breaks=price_breaks,
                moq=moq,
                currency="USD",
                lifecycle_status=lifecycle,
                category=str(best.get("Category", "")),
                product_url=str(best.get("ProductDetailUrl", "")),
                datasheet_url=str(best.get("DataSheetUrl", "")),
                match_status="hit",
                raw_summary=raw_summary,
                is_available=True,
                raw_response=best,
            )
        except Exception as exc:
            logger.warning(f"Mouser response parse failed for '{clean}': {exc}")
            return SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                match_status="parse_failed",
                error_reason=str(exc) or "Mouser 响应字段解析失败",
            )

    @staticmethod
    def _parse_stock(availability: str) -> int:
        if not availability:
            return 0
        m = _re.match(r'([\d,]+)', availability.strip())
        if m:
            return int(m.group(1).replace(",", ""))
        return 0

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
            self._client_loop = None
