"""Octopart/Nexar 生命周期数据源 — GraphQL API 接入。

实现 BaseSource 接口，提供：
- lifecycle_status: Active / NRND / EOL / Unknown
- factoryLeadDays: 工厂交期
- rohsStatus / reachStatus: 合规状态

认证: OAuth2 Client Credentials → Nexar GraphQL API
配额: 免费层 100 零件/月，本地缓存 24h TTL
降级: API 不可用时 fallback 到 DigiKey/Mouser 生命周期数据

T2-004: Octopart/Nexar 生命周期数据接入
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

import httpx
from app.config import settings

from .base import BaseSource, SourceResult

logger = logging.getLogger(__name__)

NEXAR_GRAPHQL_URL = "https://api.nexar.com/graphql"
NEXAR_OAUTH_URL = "https://identity.nexar.com/connect/token"
NEXAR_MONTHLY_QUOTA = 100  # 免费层配额

# 生命周期状态常量
LIFECYCLE_ACTIVE = "Active"
LIFECYCLE_NRND = "NRND"
LIFECYCLE_EOL = "EOL"
LIFECYCLE_UNKNOWN = "Unknown"

# 合法的生命周期值集合
VALID_LIFECYCLE_STATUSES = {LIFECYCLE_ACTIVE, LIFECYCLE_NRND, LIFECYCLE_EOL, LIFECYCLE_UNKNOWN}


class OctopartSource(BaseSource):
    """Octopart/Nexar 数据源 — 生命周期状态 + 合规信息 + 工厂交期"""

    source_name = "octopart"

    def __init__(
        self,
        client_id: str = "",
        client_secret: str = "",
        monthly_quota: int = NEXAR_MONTHLY_QUOTA,
    ):
        self.client_id = client_id or settings.nexar_client_id
        self.client_secret = client_secret or settings.nexar_client_secret
        self._token: Optional[str] = None
        self._token_expiry: float = 0.0
        self._client: Optional[httpx.AsyncClient] = None
        self._client_loop: Optional[asyncio.AbstractEventLoop] = None

        # 配额管理
        self._monthly_quota = monthly_quota
        self._queries_used = 0

        # 本地缓存: {mpn: {"result": SourceResult_dict, "timestamp": float}}
        self._cache: dict[str, dict] = {}
        self._cache_ttl = settings.cache_ttl_seconds  # 24h = 86400s

    # ================================================================
    # 配置 & 属性
    # ================================================================

    @property
    def is_configured(self) -> bool:
        """检查 Nexar 数据源是否已配置"""
        return bool(
            settings.nexar_enabled
            and self.client_id
            and self.client_secret
        )

    @property
    def quota_remaining(self) -> int:
        """剩余可查询配额"""
        return max(0, self._monthly_quota - self._queries_used)

    @property
    def quota_used(self) -> int:
        """已使用的查询配额"""
        return self._queries_used

    @property
    def quota_percentage(self) -> float:
        """配额使用百分比 (0-100)"""
        if self._monthly_quota <= 0:
            return 100.0
        return (self._queries_used / self._monthly_quota) * 100.0

    @property
    def cache_size(self) -> int:
        """缓存条目数"""
        return len(self._cache)

    # ================================================================
    # HTTP 客户端管理
    # ================================================================

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

    # ================================================================
    # OAuth2 认证
    # ================================================================

    async def _get_token(self) -> Optional[str]:
        """获取/刷新 OAuth2 access_token (Client Credentials)"""
        now = time.monotonic()
        if self._token and now < self._token_expiry - 30:
            return self._token

        client = await self._get_client()
        try:
            response = await client.post(
                NEXAR_OAUTH_URL,
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
            logger.warning(f"Nexar OAuth failed: {exc}")
            self._token = None
            return None

    # ================================================================
    # 缓存管理 (24h TTL)
    # ================================================================

    def _cache_get(self, mpn: str) -> Optional[SourceResult]:
        """从缓存获取，过期返回 None"""
        entry = self._cache.get(mpn)
        if entry is None:
            return None
        if time.time() - entry["timestamp"] > self._cache_ttl:
            del self._cache[mpn]
            return None
        # 重建 SourceResult
        return self._dict_to_source_result(entry["result"])

    def _cache_put(self, mpn: str, result: SourceResult) -> None:
        """写入缓存"""
        self._cache[mpn] = {
            "result": self._source_result_to_dict(result),
            "timestamp": time.time(),
        }

    def _cache_has(self, mpn: str) -> bool:
        """缓存是否存在且未过期"""
        entry = self._cache.get(mpn)
        if entry is None:
            return False
        if time.time() - entry["timestamp"] > self._cache_ttl:
            del self._cache[mpn]
            return False
        return True

    def clear_cache(self) -> None:
        """清空缓存"""
        self._cache.clear()

    @staticmethod
    def _source_result_to_dict(r: SourceResult) -> dict:
        """SourceResult -> dict (用于缓存序列化)"""
        return {
            "source": r.source,
            "mpn_queried": r.mpn_queried,
            "mpn_matched": r.mpn_matched,
            "manufacturer": r.manufacturer,
            "total_stock": r.total_stock,
            "supplier_count": r.supplier_count,
            "stock_location": r.stock_location,
            "lead_time_days": r.lead_time_days,
            "lead_time_display": r.lead_time_display,
            "unit_price": r.unit_price,
            "price_breaks": r.price_breaks,
            "moq": r.moq,
            "currency": r.currency,
            "lifecycle_status": r.lifecycle_status,
            "category": r.category,
            "product_url": r.product_url,
            "datasheet_url": r.datasheet_url,
            "match_status": r.match_status,
            "error_reason": r.error_reason,
            "raw_summary": r.raw_summary,
            "is_available": r.is_available,
        }

    @staticmethod
    def _dict_to_source_result(d: dict) -> SourceResult:
        """dict -> SourceResult (缓存反序列化)"""
        return SourceResult(**d)

    # ================================================================
    # 配额控制
    # ================================================================

    def _should_query(self, risk_level: str = "unknown") -> bool:
        """判断是否应该发起 API 查询

        Args:
            risk_level: 物料当前风险等级 (red/orange/yellow/green/gray/unknown)

        降级策略:
            - 配额 >= 80% (剩余 < 20%) 时仅查询 red/orange 物料
        """
        if self._queries_used >= self._monthly_quota:
            return False  # 配额耗尽

        remaining_pct = 100.0 - self.quota_percentage
        if remaining_pct < 20.0:
            # 降级：仅查高风险
            return risk_level in ("red", "orange")

        return True

    # ================================================================
    # GraphQL 查询
    # ================================================================

    # Nexar GraphQL 查询模板
    _COMPONENT_QUERY = """
    query ($mpn: String!) {
      supSearchMpn(q: $mpn) {
        results {
          part {
            mpn
            manufacturer {
              name
            }
            category {
              parentId
              name
              path
            }
            shortDescription
            lifecycleStatus
            factoryLeadDays
            rohsStatus
            reachStatus
            url
          }
        }
      }
    }
    """

    async def _execute_graphql(self, mpn: str) -> Optional[dict]:
        """执行 GraphQL 查询，返回 part 数据或 None"""
        token = await self._get_token()
        if not token:
            logger.warning("Nexar: OAuth token 不可用")
            return None

        client = await self._get_client()
        try:
            response = await client.post(
                NEXAR_GRAPHQL_URL,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={
                    "query": self._COMPONENT_QUERY,
                    "variables": {"mpn": mpn},
                },
            )
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException as exc:
            logger.warning(f"Nexar GraphQL timeout for '{mpn}': {exc}")
            return None
        except Exception as exc:
            logger.warning(f"Nexar GraphQL failed for '{mpn}': {exc}")
            return None

        # 解析 GraphQL 响应
        try:
            results = data.get("data", {}).get("supSearchMpn", {}).get("results", [])
            if not results:
                return None
            return results[0].get("part")
        except Exception as exc:
            logger.warning(f"Nexar response parse failed for '{mpn}': {exc}")
            return None

    # ================================================================
    # 生命周期状态归一化
    # ================================================================

    @staticmethod
    def normalize_lifecycle_status(raw_status: str) -> str:
        """将各种生命周期原始值归一化为标准状态

        Args:
            raw_status: 原始生命周期字符串

        Returns:
            Active / NRND / EOL / Unknown
        """
        if not raw_status:
            return LIFECYCLE_UNKNOWN

        s = raw_status.strip().lower()

        # Active 相关
        if s in ("active", "in production", "production", "mass production",
                  "active & marketing", "nrnd - active", "active (rohs)"):
            return LIFECYCLE_ACTIVE

        # NRND
        if s in ("nrnd", "not recommended for new designs",
                  "not recommended", "not recommended for new design"):
            return LIFECYCLE_NRND

        # EOL / Obsolete
        if s in ("eol", "end of life", "obsolete", "discontinued",
                  "last time buy", "last time ship", "end of service",
                  "lifecycle - end of life", "ltb"):
            return LIFECYCLE_EOL

        # Unknown
        return LIFECYCLE_UNKNOWN

    # ================================================================
    # BaseSource 接口实现
    # ================================================================

    async def query_by_mpn(
        self,
        mpn: str,
        risk_level: str = "unknown",
    ) -> SourceResult:
        """根据 MPN 查询 Octopart/Nexar 生命周期数据

        Args:
            mpn: 物料型号
            risk_level: 当前风险等级，用于配额降级决策

        Returns:
            SourceResult (含 lifecycle_status, lead_time_days 等)
        """
        # 1. 配置检查
        if not self.is_configured:
            return SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                match_status="not_configured",
                error_reason="Nexar/Octopart 未配置 (需启用并设置 ClientId/Secret)",
            )

        clean = self.clean_mpn(mpn)
        if not clean:
            return SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                match_status="missing_mpn",
                error_reason="物料型号为空，无法查询 Octopart",
            )

        # 2. 缓存命中检查 (命中时不消耗配额)
        cached = self._cache_get(clean)
        if cached is not None:
            logger.debug(f"Octopart cache hit for '{clean}'")
            return cached

        # 3. 配额检查 (含降级策略)
        if not self._should_query(risk_level):
            reason = "quota_exhausted" if self._queries_used >= self._monthly_quota else "quota_degraded"
            return SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                match_status=reason,
                error_reason=(
                    "Nexar 月度配额已耗尽" if reason == "quota_exhausted"
                    else "Nexar 配额 <20%，仅查询红/橙风险物料"
                ),
            )

        # 4. 执行 GraphQL 查询
        part_data = await self._execute_graphql(clean)
        self._queries_used += 1

        if part_data is None:
            result = SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                is_available=False,
                match_status="not_found",
                error_reason="Octopart 暂未命中该型号",
            )
            # 即使未命中也缓存结果，避免重复消耗配额
            self._cache_put(clean, result)
            return result

        # 5. 解析结果
        try:
            lifecycle_raw = part_data.get("lifecycleStatus", "") or ""
            lifecycle_status = self.normalize_lifecycle_status(lifecycle_raw)

            factory_lead_days = part_data.get("factoryLeadDays")
            lead_time_days = None
            if factory_lead_days is not None:
                try:
                    lead_time_days = int(factory_lead_days)
                except (ValueError, TypeError):
                    lead_time_days = None

            mfr_name = ""
            mfr_obj = part_data.get("manufacturer")
            if mfr_obj:
                mfr_name = mfr_obj.get("name", "") or ""

            mpn_matched = part_data.get("mpn", "") or ""
            category_info = part_data.get("category") or {}
            category_name = category_info.get("name", "") or ""
            product_url = part_data.get("url", "") or ""
            rohs = part_data.get("rohsStatus", "") or ""
            reach = part_data.get("reachStatus", "") or ""
            short_desc = part_data.get("shortDescription", "") or ""

            compliance_parts = []
            if rohs:
                compliance_parts.append(f"RoHS:{rohs}")
            if reach:
                compliance_parts.append(f"REACH:{reach}")
            compliance_str = ", ".join(compliance_parts)

            raw_summary = (
                f"Octopart 命中 {mpn_matched or clean}，"
                f"生命周期: {lifecycle_status}"
            )
            if lead_time_days:
                raw_summary += f"，交期: {lead_time_days}天"
            if compliance_str:
                raw_summary += f"，合规: {compliance_str}"

            result = SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                mpn_matched=mpn_matched,
                manufacturer=mfr_name,
                lead_time_days=lead_time_days,
                lead_time_display=f"{lead_time_days}天" if lead_time_days else "",
                lifecycle_status=lifecycle_status,
                category=category_name,
                product_url=product_url,
                match_status="hit",
                raw_summary=raw_summary,
                is_available=True,
                raw_response=part_data,
            )

            # 写入缓存
            self._cache_put(clean, result)
            return result

        except Exception as exc:
            logger.warning(f"Octopart result parse failed for '{clean}': {exc}")
            return SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                match_status="parse_failed",
                error_reason=str(exc) or "Octopart 响应字段解析失败",
            )

    async def health_check(self) -> bool:
        """检查 Octopart 数据源是否可用"""
        if not self.is_configured:
            return False
        try:
            result = await self.query_by_mpn("STM32F103C8T6")
            return result.match_status in ("hit", "not_found")
        except Exception:
            return False

    # ================================================================
    # 配额查询接口
    # ================================================================

    def get_quota_info(self) -> dict:
        """获取配额使用情况

        Returns:
            {
                "monthly_quota": 100,
                "queries_used": N,
                "queries_remaining": M,
                "usage_percentage": X.X,
                "cache_size": C,
            }
        """
        return {
            "monthly_quota": self._monthly_quota,
            "queries_used": self._queries_used,
            "queries_remaining": self.quota_remaining,
            "usage_percentage": round(self.quota_percentage, 1),
            "cache_size": self.cache_size,
        }

    # ================================================================
    # 降级辅助
    # ================================================================

    def should_degrade_to_existing_sources(self) -> bool:
        """判断是否应降级到 DigiKey/Mouser 现有生命周期数据

        降级条件：
        1. 本数据源未配置
        2. API 不可用 (health_check 失败)
        3. 配额耗尽
        """
        if not self.is_configured:
            return True
        if self._queries_used >= self._monthly_quota:
            return True
        return False

    async def close(self):
        """关闭 HTTP 客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None
            self._client_loop = None
