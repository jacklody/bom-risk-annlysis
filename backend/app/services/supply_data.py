"""多源供应数据编排服务 — 并行查询 DigiKey/Mouser/观芯台/LCSC，最优合并。"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from app.models.bom import BomItem
from app.services.supply_risk import evaluate_supply_risk
from .sources.base import SourceResult
from .sources.digikey import DigiKeySource
from .sources.guanxintai import GuanxintaiSource
from .sources.lcsc import LCSCSource
from .sources.mouser import MouserSource

logger = logging.getLogger(__name__)

LIFECYCLE_PRIORITY = {
    "digikey": 3,
    "mouser": 2,
}


@dataclass
class AggregatedResult:
    """供应数据聚合后的统一结果 (v3.3: 含 worst-case 视图)。"""

    mpn_queried: str = ""
    source_name: str = "多源聚合"
    match_status: str = "not_found"
    error_reason: str = ""
    raw_summary: str = ""
    total_stock: int = 0
    supplier_count: int = 0
    lead_time_days: Optional[int] = None
    unit_price: Optional[float] = None
    currency: str = "CNY"
    lifecycle_status: str = "Unknown"
    sources: list[SourceResult] = field(default_factory=list)
    is_available: bool = False
    # v3.3: worst-case 视图
    worst_case_stock: int = 0
    worst_case_lead_time_days: Optional[int] = None
    worst_case_unit_price: Optional[float] = None
    worst_case_source: str = ""


class SupplyDataService:
    """多源供应链实时数据编排服务 (v3.3: 懒加载数据源)。"""

    # 注册的数据源类
    _SOURCE_CLASSES = [LCSCSource, MouserSource, DigiKeySource, GuanxintaiSource]

    def __init__(self):
        # v3.3: 懒加载 — __init__ 不再创建数据源实例，统一在 initialize() 创建
        self._lcsc = None
        self._mouser = None
        self._digikey = None
        self._guanxintai = None
        self._all_sources: list = []
        self._enabled_sources: list = []
        self._initialized = False

    async def initialize(self):
        """v3.3: 按需创建已启用的数据源实例（懒加载）。"""
        if self._initialized:
            return
        for cls in self._SOURCE_CLASSES:
            instance = cls()
            if instance.is_configured:
                ok = await instance.health_check()
                if ok:
                    self._enabled_sources.append(instance)
                else:
                    logger.warning(f"SupplyDataService: {instance.source_name} health check failed, skipped")
            else:
                logger.info(f"SupplyDataService: {instance.source_name} not configured, skipped")
            self._all_sources.append(instance)
        # 保留引用以兼容旧代码
        for src in self._all_sources:
            name = src.source_name.lower()
            if "lcsc" in name:
                self._lcsc = src
            elif "mouser" in name:
                self._mouser = src
            elif "digikey" in name or "digi" in name:
                self._digikey = src
            elif "guanxin" in name:
                self._guanxintai = src
        logger.info(f"SupplyDataService initialized: {len(self._enabled_sources)}/{len(self._all_sources)} sources enabled")
        self._initialized = True

    async def shutdown(self):
        for s in self._all_sources:
            await s.close()

    async def query_one(self, mpn: str) -> AggregatedResult:
        if not mpn:
            return AggregatedResult(
                mpn_queried=mpn,
                match_status="missing_mpn",
                error_reason="物料型号为空，无法查询供应数据",
            )
        sources = self._enabled_sources if self._enabled_sources else ([self._lcsc] if self._lcsc else [])
        if not sources:
            return AggregatedResult(
                mpn_queried=mpn,
                match_status="no_source",
                error_reason="未配置任何有效供应数据源，请先调用 initialize()",
            )
        tasks = [s.query_by_mpn(mpn) for s in sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        source_results: list[SourceResult] = []
        for source, result in zip(sources, results):
            if isinstance(result, SourceResult):
                source_results.append(result)
            elif isinstance(result, Exception):
                logger.error(f"Supply query exception from {source.source_name}: {result}")
                source_results.append(SourceResult(
                    source=source.source_name,
                    mpn_queried=mpn,
                    match_status="request_failed",
                    is_available=False,
                    error_reason=str(result),
                ))
        return self._merge_best(mpn, source_results)

    def _merge_best(self, mpn: str, source_results: list[SourceResult]) -> AggregatedResult:
        hits = [r for r in source_results if r.is_available]

        merged = AggregatedResult(mpn_queried=mpn)
        merged.sources = source_results

        if not hits:
            merged.is_available = False
            statuses = [r.match_status for r in source_results]
            merged.match_status = statuses[0] if statuses else "not_found"
            merged.error_reason = "; ".join(r.error_reason for r in source_results if r.error_reason)
            return merged

        merged.is_available = True
        merged.match_status = "hit"
        merged.total_stock = max((r.total_stock for r in hits), default=0)
        merged.supplier_count = sum(1 for r in hits if r.total_stock > 0)

        valid_prices = [r.unit_price for r in hits if r.unit_price is not None]
        if valid_prices:
            merged.unit_price = min(valid_prices)

        valid_leads = [r.lead_time_days for r in hits if r.lead_time_days is not None]
        if valid_leads:
            merged.lead_time_days = min(valid_leads)

        # v3.3: worst-case 视图（最长交期、最高价格、最少库存）
        merged.worst_case_stock = min((r.total_stock for r in hits if r.total_stock > 0), default=0)
        if valid_leads:
            merged.worst_case_lead_time_days = max(valid_leads)
        if valid_prices:
            merged.worst_case_unit_price = max(valid_prices)
        # worst-case 来源：交期最长的来源
        if merged.worst_case_lead_time_days:
            for r in hits:
                if r.lead_time_days == merged.worst_case_lead_time_days:
                    merged.worst_case_source = r.source
                    break

        merged.lifecycle_status = self._best_lifecycle(hits)
        merged.currency = self._resolve_currency(hits, merged.unit_price)
        merged.raw_summary = " ".join(
            f"{r.source}:{r.raw_summary or r.match_status}" for r in hits
        )
        return merged

    def _best_lifecycle(self, hits: list[SourceResult]) -> str:
        best = "Unknown"
        best_priority = -1
        for r in hits:
            if r.lifecycle_status and r.lifecycle_status != "Unknown":
                pri = LIFECYCLE_PRIORITY.get(r.source, 0)
                if pri > best_priority:
                    best = r.lifecycle_status
                    best_priority = pri
        return best

    def _resolve_currency(self, hits: list[SourceResult], min_price: Optional[float]) -> str:
        if min_price is not None:
            for r in hits:
                if r.unit_price == min_price:
                    return r.currency or "CNY"
        return "CNY"

    async def query_batch(self, mpns: list[str], concurrency: int = 3) -> dict[str, AggregatedResult]:
        semaphore = asyncio.Semaphore(max(1, min(concurrency, 5)))
        async def _query_one(mpn: str) -> AggregatedResult:
            async with semaphore:
                return await self.query_one(mpn)
        valid_mpns = [mpn for mpn in mpns if mpn]
        tasks = [_query_one(mpn) for mpn in valid_mpns]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        output = {}
        for mpn, result in zip(valid_mpns, results):
            if isinstance(result, Exception):
                logger.error(f"Batch query failed for '{mpn}': {result}")
                output[mpn] = AggregatedResult(
                    mpn_queried=mpn,
                    match_status="request_failed",
                    error_reason=str(result),
                )
            else:
                output[mpn] = result
        return output

    def apply_to_bom_item(self, item: BomItem, aggregated: AggregatedResult, db: Session, save: bool = True) -> bool:
        if not aggregated.is_available:
            return False
        item.total_stock = aggregated.total_stock
        item.supplier_count = aggregated.supplier_count
        item.lead_time_days = aggregated.lead_time_days
        item.unit_price = aggregated.unit_price
        item.lifecycle_status = aggregated.lifecycle_status
        item.supply_sources_summary = aggregated.raw_summary
        realtime_data = {
            "total_stock": aggregated.total_stock,
            "supplier_count": aggregated.supplier_count,
            "lead_time_days": aggregated.lead_time_days,
            "unit_price": aggregated.unit_price,
            "lifecycle_status": aggregated.lifecycle_status,
        }
        commonality_data = {
            "has_multi_source": aggregated.supplier_count >= 2,
            "is_major_brand": bool(item.normalized_brand or item.raw_brand),
            "is_standard_package": bool(
                item.raw_spec
                and any(pkg in item.raw_spec.lower() for pkg in ["0402", "0603", "0805", "1206", "sot-23", "soic", "qfn"])
            ),
        }
        supply = evaluate_supply_risk(item, [], realtime_data, commonality_data)
        item.production_risk_level = supply.production_risk_level
        item.production_risk_score = supply.production_risk_score
        item.lead_time_risk_weeks = supply.lead_time_risk_weeks
        item.eol_status = supply.eol_status
        item.supply_risk_tags = supply.supply_risk_tags
        item.supply_risk_reason = supply.supply_risk_reason
        item.procurement_suggestion = supply.procurement_suggestion
        item.commonality_score = supply.commonality_score
        if save:
            db.commit()
        return True
