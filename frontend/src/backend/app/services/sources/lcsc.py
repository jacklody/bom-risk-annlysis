"""LCSC / JLCPCB 数据源 — 通过 jlcsearch API（免费、无需认证）。

API文档: https://github.com/tscircuit/jlcsearch
实际返回格式: {"components": [{"lcsc": 8734, "mfr": "...", "stock": 214596, "price": 1.03, ...}]}

频率限制建议: 0.5s 请求间隔
支持字段: 库存、阶梯价格、数据手册直链、基础物料标记
不支持: 交期、生命周期状态
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

LCSC_API_BASE = "https://jlcsearch.tscircuit.com/api"


class LCSCSource(BaseSource):
    """LCSC 数据源 — 实时库存 + 阶梯价格"""

    source_name = "lcsc"

    def __init__(self, request_delay: float = 0.55):
        self.request_delay = request_delay
        self._last_request_time = 0.0
        self._client: Optional[httpx.AsyncClient] = None
        self._client_loop: Optional[asyncio.AbstractEventLoop] = None

    @property
    def is_configured(self) -> bool:
        return bool(settings.lcsc_enabled)  # 免费 API，无需 API key，但仍受开关控制

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
                timeout=httpx.Timeout(10.0),
                follow_redirects=True,
            )
            self._client_loop = current_loop
        return self._client

    async def _rate_limit(self):
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < self.request_delay:
            await asyncio.sleep(self.request_delay - elapsed)
        self._last_request_time = time.monotonic()

    async def health_check(self) -> bool:
        try:
            result = await self.query_by_mpn("STM32F103C8T6")
            return result is not None and result.is_available
        except Exception:
            return False

    async def query_by_mpn(self, mpn: str) -> SourceResult:
        clean = self.clean_mpn(mpn)
        if not clean:
            return SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                match_status="missing_mpn",
                error_reason="物料型号为空，无法查询 LCSC",
            )

        await self._rate_limit()
        client = await self._get_client()

        try:
            response = await client.get(
                f"{LCSC_API_BASE}/search",
                params={"q": clean, "limit": 5, "full": "true"},
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            logger.warning(f"LCSC query timeout for '{clean}': {exc}")
            return SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                match_status="timeout",
                error_reason=str(exc) or "LCSC 查询超时",
            )
        except Exception as exc:
            logger.warning(f"LCSC query failed for '{clean}': {exc}")
            return SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                match_status="request_failed",
                error_reason=str(exc) or "LCSC 请求失败",
            )

        try:
            data = response.json()
            # API 实际返回字段名是 "components"，不是 "results"
            components = data.get("components", [])
        except Exception as exc:
            return SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                match_status="parse_failed",
                error_reason=str(exc) or "LCSC 响应解析失败",
            )

        if not components:
            return SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                is_available=False,
                match_status="not_found",
                error_reason="LCSC 暂未命中该型号",
            )

        try:
            best = components[0]

            # 实际字段名: stock, mfr, price, lcsc, package, is_basic, is_preferred
            total_stock = int(best.get("stock", 0) or 0)
            supplier_count = 1 if total_stock > 0 else 0

            raw_price = best.get("price")
            unit_price = float(raw_price) if raw_price not in (None, "", 0) else None
            currency = "CNY"

            price_breaks = []
            if unit_price is not None:
                price_breaks = [
                    {"qty_min": 1, "qty_max": 0, "price": unit_price, "currency": currency}
                ]

            moq = int(best.get("moq", 1) or 1)
            is_basic = bool(best.get("is_basic", False))
            manufacturer = best.get("mfr", "")
            lcsc_code = best.get("lcsc", "")

            raw_summary = (
                f"LCSC 命中 {manufacturer} {clean}"
                f"（编号{lcsc_code}），库存{total_stock}，币种{currency}"
            )

            return SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                mpn_matched=str(lcsc_code) if lcsc_code else clean,
                manufacturer=manufacturer,
                total_stock=total_stock,
                supplier_count=supplier_count,
                stock_location="",
                lead_time_days=None,
                lead_time_display="现货" if total_stock > 0 else "需要订货",
                unit_price=unit_price,
                price_breaks=price_breaks,
                moq=moq,
                currency=currency,
                lifecycle_status="Unknown",
                category=best.get("package", ""),
                product_url=f"https://www.lcsc.com/product-detail/{lcsc_code}" if lcsc_code else "",
                datasheet_url="",
                match_status="hit",
                raw_summary=raw_summary,
                is_available=True,
                raw_response={"total_stock": total_stock, "is_basic": is_basic, **best},
            )
        except Exception as exc:
            logger.warning(f"LCSC response parse failed for '{clean}': {exc}")
            return SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                match_status="parse_failed",
                error_reason=str(exc) or "LCSC 响应字段解析失败",
            )

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
            self._client_loop = None
