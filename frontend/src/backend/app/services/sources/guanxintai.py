"""观芯台 (guanxintai.com) 数据源 — 免登录 HTML 解析。

搜索 URL: https://www.guanxintai.com/index?keyword=型号
数据：聚合立创商城、华秋商城、圣禾堂等多渠道价格库存
频率限制: 3s 请求间隔
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Optional

import httpx
from app.config import settings

from .base import BaseSource, SourceResult

logger = logging.getLogger(__name__)

GUANXINTAI_SEARCH_URL = "https://www.guanxintai.com/index"


class GuanxintaiSource(BaseSource):
    """观芯台 — 国内元器件聚合比价"""

    source_name = "guanxintai"

    def __init__(self):
        self._last_request_time = 0.0
        self._client: Optional[httpx.AsyncClient] = None
        self._client_loop: Optional[asyncio.AbstractEventLoop] = None

    @property
    def is_configured(self) -> bool:
        return bool(settings.guanxintai_enabled)  # 免认证，但仍受开关控制

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
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            self._client_loop = current_loop
        return self._client

    async def _rate_limit(self):
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < 3.0:
            await asyncio.sleep(3.0 - elapsed)
        self._last_request_time = time.monotonic()

    async def health_check(self) -> bool:
        try:
            result = await self.query_by_mpn("STM32F103C8T6")
            return result is not None and result.match_status == "hit"
        except Exception:
            return False

    async def query_by_mpn(self, mpn: str) -> SourceResult:
        clean = self.clean_mpn(mpn)
        if not clean:
            return SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                match_status="missing_mpn",
                error_reason="物料型号为空，无法查询观芯台",
            )

        await self._rate_limit()
        client = await self._get_client()

        try:
            response = await client.get(
                GUANXINTAI_SEARCH_URL,
                params={"keyword": clean},
            )
            response.raise_for_status()
            html = response.text
        except httpx.TimeoutException as exc:
            return SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                match_status="timeout",
                error_reason=str(exc) or "观芯台 查询超时",
            )
        except Exception as exc:
            return SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                match_status="request_failed",
                error_reason=str(exc) or "观芯台 请求失败",
            )

        if not html or len(html) < 200:
            return SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                is_available=False,
                match_status="not_found",
                error_reason="观芯台 返回空页面",
            )

        return self._parse_html_to_result(html, clean)

    def _parse_html_to_result(self, html: str, mpn: str) -> SourceResult:
        """解析观芯台 HTML 中的价格表格行。

        页面结构: 多个 <table> 中每行 <tr> 包含
        型号 | 厂牌 | 封装 | 价格(含税) | 库存 | 批次 | 交期 | 渠道
        解析所有行的价格和库存，取最优值。
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.warning("beautifulsoup4 not installed, guanxintai parse skipped")
            return SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                match_status="parse_failed",
                error_reason="beautifulsoup4 未安装",
            )

        soup = BeautifulSoup(html, "html.parser")
        tables = soup.find_all("table")
        if not tables:
            return SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                is_available=False,
                match_status="not_found",
                error_reason="观芯台 未找到价格表格",
            )

        total_stock = 0
        unit_price = None
        lead_time_display = ""
        channels = []

        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                if len(cells) < 4:
                    continue
                text_content = [c.get_text(strip=True) for c in cells]

                # 查找含 "¥" 或数字价格模式的列（必须含货币符号避免误匹配型号中的数字）
                price_val = None
                for text in text_content:
                    if '¥' in text or '￥' in text:
                        price_match = re.search(r'[¥￥]\s*([\d.]+)', text)
                        if price_match:
                            try:
                                p = float(price_match.group(1))
                                if 0.001 < p < 100000:
                                    price_val = p
                                    break
                            except ValueError:
                                continue

                # 查找库存列（纯数字，靠后位置）
                stock_val = 0
                for text in reversed(text_content[-4:]):
                    cleaned = text.replace(",", "").replace(" ", "")
                    if cleaned.isdigit():
                        stock_val = int(cleaned)
                        if stock_val > 0:
                            break

                # 查找交期列 — 取第一个有效值，避免被后续行覆盖
                if not lead_time_display:
                    for text in text_content[-3:]:
                        if any(w in text for w in ["发货", "现货", "交期"]):
                            lead_time_display = text
                            break

                if stock_val > 0:
                    total_stock = max(total_stock, stock_val)
                if price_val and (unit_price is None or price_val < unit_price):
                    unit_price = price_val

                if stock_val > 0 or price_val:
                    channels.append(text_content[-1] if text_content else "?")

        if total_stock == 0 and unit_price is None:
            return SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                is_available=False,
                match_status="not_found",
                error_reason="观芯台 未解析到有效价格/库存",
            )

        raw_summary = f"观芯台 命中，库存{total_stock}，渠道{len(channels)}家"
        return SourceResult(
            source=self.source_name,
            mpn_queried=mpn,
            total_stock=total_stock,
            supplier_count=len(set(channels)),
            unit_price=unit_price,
            currency="CNY",
            lead_time_display=lead_time_display,
            match_status="hit",
            raw_summary=raw_summary,
            is_available=True,
        )

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
            self._client_loop = None
