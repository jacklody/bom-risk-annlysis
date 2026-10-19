"""原材料价格编排服务 — 统一调度 + 缓存 + 降级 + 限流。

职责:
- 按数据域分组调度三个数据源组
- 缓存管理: 以 material_key 为粒度，TTL 按域区分
- 降级策略: 主源超时/失败 → 备源 → stale 缓存
- 配额保护: metals-api 60次/月，按日分配预算
- 并发控制: 三域并行请求

对外接口:
    get_prices(material_keys) -> dict[str, dict]
    refresh_all() -> dict
    get_cache_stats() -> dict
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from app.knowledge.material_mapping import (
    MATERIAL_REGISTRY,
    DOMAIN_MATERIALS,
    get_material_entry,
    get_material_keys_for_domain,
)
from app.services.sources.materials.base import MaterialPriceSource
from app.services.sources.materials.metals_api_source import MetalsAPISource
from app.services.sources.materials.rare_earth_source import RareEarthAssociationSource
from app.services.sources.materials.small_metal_source import AsianMetalSource, BaiinfoSource
from app.services.sources.materials.chemical_source import Chemical100ppiSource, Sci99Source

logger = logging.getLogger(__name__)

# 各域缓存 TTL (秒)
DOMAIN_CACHE_TTL = {
    "metals": 12 * 3600,       # 12 小时
    "rare_earth": 24 * 3600,   # 24 小时
    "chemical": 24 * 3600,     # 24 小时
}

# metals-api 免费层配额: 60次/月
METALS_API_MONTHLY_QUOTA = 60


class MaterialPriceService:
    """原材料价格编排服务。

    Usage:
        service = MaterialPriceService(metals_source)
        prices = await service.get_prices(["cu_cathode", "al_ingot"])
        # { "cu_cathode": {"price": 78200.0, "unit": "元/吨", ...}, ... }
    """

    def __init__(
        self,
        metals_source: MaterialPriceSource | None = None,
        rare_earth_sources: list[MaterialPriceSource] | None = None,
        chemical_sources: list[MaterialPriceSource] | None = None,
    ):
        # ── 数据源实例 (每域支持主源+备源列表) ──
        self._metals_source = metals_source or MetalsAPISource()

        # 稀土域多源: [主源, 备源1, 备源2, ...]
        if rare_earth_sources is None:
            rare_earth_sources = [
                RareEarthAssociationSource(),   # 稀土氧化物主源
                AsianMetalSource(),             # 钽粉/钽丝主源 + 稀土备源
                BaiinfoSource(),                # 碳酸钡主源
            ]
        self._rare_earth_sources: list[MaterialPriceSource] = rare_earth_sources

        # 化工域多源: [主源, 备源]
        if chemical_sources is None:
            chemical_sources = [
                Chemical100ppiSource(),         # 生意社 — 化工主源
                Sci99Source(),                  # 卓创资讯 — 钛白粉备源
            ]
        self._chemical_sources: list[MaterialPriceSource] = chemical_sources

        # 缓存: {material_key: {price, unit, source, timestamp, stale}}
        self._cache: Dict[str, Dict[str, Any]] = {}

        # 配额追踪
        self._metals_api_calls: list[float] = []  # 本月 API 调用时间戳列表
        self._quota_reset_day = datetime.now(timezone.utc).day

    # ── 公开接口 ──────────────────────────────────────────

    async def get_prices(
        self, material_keys: List[str], force_refresh: bool = False
    ) -> Dict[str, Optional[float]]:
        """获取原材料最新价格。

        Args:
            material_keys: 要查询的材料 key 列表
            force_refresh: 是否强制刷新（忽略缓存）

        Returns:
            {material_key: price_value} 字典
        """
        result: Dict[str, Optional[float]] = {}

        if force_refresh:
            await self._refresh_all_domains(material_keys)
            for mk in material_keys:
                cached = self._cache.get(mk)
                result[mk] = cached["price"] if cached else None
            return result

        # 检查缓存
        to_fetch: Set[str] = set()
        for mk in material_keys:
            cached = self._cache.get(mk)
            if cached and self._is_cache_fresh(mk):
                result[mk] = cached["price"]
            else:
                to_fetch.add(mk)

        if to_fetch:
            fetched = await self._fetch_by_domain(list(to_fetch))
            for mk, price in fetched.items():
                result[mk] = price

        return result

    async def refresh_all(self) -> Dict[str, Any]:
        """强制刷新全部材料价格。返回统计摘要。"""
        all_keys = list(MATERIAL_REGISTRY.keys())
        start = time.monotonic()

        await self._refresh_all_domains(all_keys)

        elapsed = time.monotonic() - start
        valid = sum(1 for v in self._cache.values() if v.get("price") is not None)
        return {
            "total_materials": len(all_keys),
            "prices_valid": valid,
            "elapsed_seconds": round(elapsed, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_cache_stats(self) -> Dict[str, Any]:
        """返回缓存统计信息。"""
        now = time.time()
        fresh = 0
        stale = 0
        degraded = 0
        by_domain: Dict[str, int] = {}

        for mk, entry in self._cache.items():
            mat = get_material_entry(mk)
            domain = mat.domain if mat else "unknown"
            by_domain[domain] = by_domain.get(domain, 0) + 1

            if entry.get("degraded"):
                degraded += 1
            elif entry.get("timestamp", 0) + DOMAIN_CACHE_TTL.get(domain, 86400) > now:
                fresh += 1
            else:
                stale += 1

        return {
            "total_cached": len(self._cache),
            "fresh": fresh,
            "stale": stale,
            "degraded": degraded,
            "by_domain": by_domain,
            "metals_api_calls_this_month": len(self._metals_api_calls),
            "metals_api_quota": METALS_API_MONTHLY_QUOTA,
        }

    def get_cached_prices(self) -> Dict[str, Dict[str, Any]]:
        """返回全部缓存的价格快照（供 WebSocket 轮询使用）。

        Returns:
            {material_key: {price, unit, source, timestamp, degraded}}
        """
        return dict(self._cache)  # 浅拷贝，避免并发修改

    # ── 内部方法 ──────────────────────────────────────────

    async def _refresh_all_domains(self, material_keys: List[str]):
        """按域分组刷新。"""
        # 分组
        domain_groups: Dict[str, List[str]] = {}
        for mk in material_keys:
            entry = get_material_entry(mk)
            if entry:
                domain_groups.setdefault(entry.domain, []).append(mk)

        # 三域并行
        tasks = []
        for domain, keys in domain_groups.items():
            tasks.append(self._fetch_domain(domain, keys))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _fetch_by_domain(self, material_keys: List[str]) -> Dict[str, Optional[float]]:
        """按域分组获取价格（便捷版，用于增量查询）。"""
        result: Dict[str, Optional[float]] = {}

        domain_groups: Dict[str, List[str]] = {}
        for mk in material_keys:
            entry = get_material_entry(mk)
            if entry:
                domain_groups.setdefault(entry.domain, []).append(mk)
            else:
                result[mk] = None

        if not domain_groups:
            return result

        tasks = [
            self._fetch_domain(domain, keys)
            for domain, keys in domain_groups.items()
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

        # 从缓存回读
        for mk in material_keys:
            if mk not in result:
                cached = self._cache.get(mk)
                result[mk] = cached["price"] if cached else None

        return result

    async def _fetch_domain(self, domain: str, material_keys: List[str]):
        """获取单个域的材料价格。支持多源逐级降级。"""
        sources = self._get_sources_for_domain(domain)
        if not sources:
            logger.warning(f"No source available for domain '{domain}'")
            self._mark_all_degraded(material_keys)
            return

        # 配额检查 (仅 metals 域)
        if domain == "metals":
            self._check_quota_reset()
            if len(self._metals_api_calls) >= METALS_API_MONTHLY_QUOTA:
                logger.warning("metals_api monthly quota exhausted, using stale cache")
                self._mark_stale_cache(material_keys)
                return
            self._metals_api_calls.append(time.time())

        # 跟踪哪些 key 已成功获取
        remaining_keys: set[str] = set(material_keys)

        for source in sources:
            if not remaining_keys:
                break

            try:
                available = await source.is_available()
                if not available:
                    continue

                prices = await asyncio.wait_for(
                    source.fetch_prices(list(remaining_keys)),
                    timeout=30.0,
                )

                # 检查返回并更新缓存
                newly_resolved: set[str] = set()
                for mk in list(remaining_keys):
                    price = prices.get(mk)
                    if price is not None:
                        entry = get_material_entry(mk)
                        self._cache[mk] = {
                            "price": price,
                            "unit": entry.unit if entry else "元/吨",
                            "source": source.source_name,
                            "timestamp": time.time(),
                            "degraded": False,
                        }
                        newly_resolved.add(mk)

                remaining_keys -= newly_resolved

                if remaining_keys:
                    logger.debug(
                        f"Domain '{domain}': {source.source_name} resolved "
                        f"{len(newly_resolved)}, {len(remaining_keys)} remaining → next source"
                    )

            except asyncio.TimeoutError:
                logger.warning(f"Source '{source.source_name}' timed out for domain '{domain}'")
                continue
            except Exception as e:
                logger.warning(f"Source '{source.source_name}' failed for domain '{domain}': {e}")
                continue

        # 仍未获取到的 key 降级为 stale 缓存
        for mk in remaining_keys:
            self._mark_stale_for_key(mk)

    def _get_sources_for_domain(self, domain: str) -> list[MaterialPriceSource]:
        """返回指定域的全部数据源列表（主源在前，备源在后）。"""
        if domain == "metals":
            return [self._metals_source]
        elif domain == "rare_earth":
            return self._rare_earth_sources
        elif domain == "chemical":
            return self._chemical_sources
        return []

    def _is_cache_fresh(self, material_key: str) -> bool:
        cached = self._cache.get(material_key)
        if not cached:
            return False
        entry = get_material_entry(material_key)
        domain = entry.domain if entry else "metals"
        ttl = DOMAIN_CACHE_TTL.get(domain, 86400)
        return (time.time() - cached.get("timestamp", 0)) < ttl

    def _mark_stale_cache(self, material_keys: List[str]):
        for mk in material_keys:
            self._mark_stale_for_key(mk)

    def _mark_stale_for_key(self, mk: str):
        cached = self._cache.get(mk)
        if cached and cached.get("price") is not None:
            cached["degraded"] = True
        else:
            self._cache[mk] = {
                "price": None,
                "unit": "元/吨",
                "source": "failed",
                "timestamp": time.time(),
                "degraded": True,
            }

    def _mark_all_degraded(self, material_keys: List[str]):
        for mk in material_keys:
            self._mark_stale_for_key(mk)

    def _check_quota_reset(self):
        """每月 1 号重置配额计数。"""
        today = datetime.now(timezone.utc)
        if today.day == 1 and self._quota_reset_day != 1:
            self._metals_api_calls.clear()
            self._quota_reset_day = 1
        elif today.day != self._quota_reset_day:
            self._quota_reset_day = today.day

    async def shutdown(self):
        """关闭所有数据源连接。"""
        all_sources = [self._metals_source]
        all_sources.extend(self._rare_earth_sources)
        all_sources.extend(self._chemical_sources)
        for src in all_sources:
            if src and hasattr(src, "close"):
                await src.close()


# ── 模块级单例 ────────────────────────────────────────────
_price_service: Optional[MaterialPriceService] = None


def get_material_price_service() -> MaterialPriceService:
    global _price_service
    if _price_service is None:
        _price_service = MaterialPriceService()
    return _price_service


async def shutdown_material_price_service():
    global _price_service
    if _price_service:
        await _price_service.shutdown()
        _price_service = None
