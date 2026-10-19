from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.bom import BomItem, BomProject
from app.services.supply_data import AggregatedResult, SupplyDataService

router = APIRouter()
_service: SupplyDataService | None = None


def get_supply_service() -> SupplyDataService:
    global _service
    if _service is None:
        _service = SupplyDataService()
    return _service


async def ensure_supply_service_initialized(service: SupplyDataService) -> None:
    """Initialize real supply service while keeping test/dummy dependency overrides compatible."""
    initialize = getattr(service, "initialize", None)
    if initialize is not None and not getattr(service, "_initialized", False):
        await initialize()


def _result_payload(result: AggregatedResult) -> dict:
    sources_payload = []
    for s in result.sources:
        sources_payload.append({
            "name": s.source,
            "match_status": s.match_status,
            "is_available": s.is_available,
            "total_stock": s.total_stock,
            "lead_time_days": s.lead_time_days,
            "unit_price": s.unit_price,
            "lifecycle_status": s.lifecycle_status,
            "raw_summary": s.raw_summary,
            "error_reason": s.error_reason,
        })
    return {
        "mpn_queried": result.mpn_queried,
        "source_name": result.source_name,
        "is_available": result.is_available,
        "match_status": result.match_status,
        "total_stock": result.total_stock,
        "supplier_count": result.supplier_count,
        "lead_time_days": result.lead_time_days,
        "unit_price": result.unit_price,
        "currency": result.currency,
        "lifecycle_status": result.lifecycle_status,
        "raw_summary": result.raw_summary,
        "error_reason": result.error_reason,
        "sources": sources_payload,
    }


def _item_supply_payload(item: BomItem) -> dict:
    return {
        "id": item.id,
        "row_number": item.row_number,
        "raw_part_number": item.raw_part_number,
        "total_stock": item.total_stock,
        "supplier_count": item.supplier_count,
        "lead_time_days": item.lead_time_days,
        "unit_price": item.unit_price,
        "lifecycle_status": item.lifecycle_status,
        "production_risk_level": item.production_risk_level,
        "production_risk_score": item.production_risk_score,
        "lead_time_risk_weeks": item.lead_time_risk_weeks,
        "eol_status": item.eol_status,
        "supply_risk_tags": item.supply_risk_tags,
        "supply_risk_reason": item.supply_risk_reason,
        "procurement_suggestion": item.procurement_suggestion,
        "commonality_score": item.commonality_score,
    }


def _all_supply_sources(service: SupplyDataService) -> list:
    return list(getattr(service, "_all_sources", None) or getattr(service, "_enabled_sources", None) or [])


def _source_status_from_result(configured: bool, result) -> str:
    if not configured:
        return "not_configured"
    if result is None:
        return "active"
    if getattr(result, "match_status", "") == "hit" and getattr(result, "is_available", False):
        return "active"
    return "degraded"


def _source_status_payload(source, configured: bool, status: str, result=None) -> dict:
    return {
        "source": getattr(source, "source_name", "unknown"),
        "configured": configured,
        "status": status,
        "match_status": getattr(result, "match_status", None),
        "is_available": getattr(result, "is_available", None),
        "total_stock": getattr(result, "total_stock", None),
        "lead_time_days": getattr(result, "lead_time_days", None),
        "unit_price": getattr(result, "unit_price", None),
        "error_reason": getattr(result, "error_reason", "") if result is not None else "",
    }


@router.get("/sources/status")
async def get_supply_sources_status(
    sample_mpn: str = Query("STM32F103C8T6", min_length=1),
    service: SupplyDataService = Depends(get_supply_service),
):
    sources = _all_supply_sources(service)
    rows = []
    summary = {
        "total_sources": len(sources),
        "active_sources": 0,
        "not_configured_sources": 0,
        "degraded_sources": 0,
    }
    for source in sources:
        configured = bool(getattr(source, "is_configured", False))
        result = None
        if configured:
            try:
                result = await source.query_by_mpn(sample_mpn)
            except Exception as exc:
                from app.services.sources.base import SourceResult
                result = SourceResult(
                    source=getattr(source, "source_name", "unknown"),
                    mpn_queried=sample_mpn,
                    match_status="request_failed",
                    error_reason=str(exc),
                    is_available=False,
                )
        status = _source_status_from_result(configured, result)
        if status == "active":
            summary["active_sources"] += 1
        elif status == "not_configured":
            summary["not_configured_sources"] += 1
        else:
            summary["degraded_sources"] += 1
        rows.append(_source_status_payload(source, configured, status, result))
    return {"sample_mpn": sample_mpn, "summary": summary, "sources": rows}


@router.get("/query")
async def query_supply(mpn: str = Query(..., min_length=1), service: SupplyDataService = Depends(get_supply_service)):
    await ensure_supply_service_initialized(service)
    result = await service.query_one(mpn)
    return _result_payload(result)


@router.post("/items/{item_id}/refresh")
async def refresh_item_supply(item_id: int, db: Session = Depends(get_db), service: SupplyDataService = Depends(get_supply_service)):
    await ensure_supply_service_initialized(service)
    item = db.query(BomItem).filter(BomItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="BOM item not found")
    mpn = item.raw_part_number or ""
    result = await service.query_one(mpn)
    updated = service.apply_to_bom_item(item, result, db, save=True)
    db.refresh(item)
    failure_reason = "" if updated else (result.error_reason or "供应数据暂不可用")
    return {
        "updated": updated,
        "failure_reason": failure_reason,
        "result": _result_payload(result),
        "item": _item_supply_payload(item),
    }


@router.post("/projects/{project_id}/refresh")
async def refresh_project_supply(
    project_id: int,
    limit: int = Query(50, ge=1, le=100),
    concurrency: int = Query(3, ge=1, le=5),
    db: Session = Depends(get_db),
    service: SupplyDataService = Depends(get_supply_service),
):
    await ensure_supply_service_initialized(service)
    project = db.query(BomProject).filter(BomProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="BOM project not found")
    items = (
        db.query(BomItem)
        .filter(BomItem.bom_upload_id == project_id, BomItem.raw_part_number.isnot(None))
        .order_by(BomItem.row_number)
        .limit(limit)
        .all()
    )
    mpns = [item.raw_part_number for item in items if item.raw_part_number]
    results = await service.query_batch(mpns, concurrency=concurrency)
    item_results = []
    updated_count = 0
    not_found_count = 0
    failed_count = 0
    for item in items:
        result = results.get(item.raw_part_number)
        if result is None:
            result = AggregatedResult(mpn_queried=item.raw_part_number or "", match_status="request_failed", error_reason="查询结果缺失")
        updated = service.apply_to_bom_item(item, result, db, save=False)
        if updated:
            updated_count += 1
        elif result.match_status == "not_found":
            not_found_count += 1
        else:
            failed_count += 1
        item_results.append({"item_id": item.id, "updated": updated, "result": _result_payload(result), "item": _item_supply_payload(item)})
    db.commit()
    return {
        "project_id": project_id,
        "processed_count": len(items),
        "updated_count": updated_count,
        "not_found_count": not_found_count,
        "failed_count": failed_count,
        "items": item_results,
    }


@router.get("/projects/{project_id}/status")
def get_project_supply_status(project_id: int, db: Session = Depends(get_db)):
    project = db.query(BomProject).filter(BomProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="BOM project not found")
    items = db.query(BomItem).filter(BomItem.bom_upload_id == project_id).all()
    items_with_mpn = [item for item in items if item.raw_part_number]
    items_with_supply_data = [
        item for item in items_with_mpn
        if (item.total_stock is not None and item.total_stock > 0) or item.lead_time_days or item.unit_price or (item.lifecycle_status and item.lifecycle_status != "Unknown")
    ]
    zero_stock_count = sum(1 for item in items_with_mpn if item.total_stock == 0)
    long_lead_count = sum(1 for item in items_with_mpn if item.lead_time_days and item.lead_time_days > 56)
    eol_count = sum(1 for item in items_with_mpn if item.eol_status in {"confirmed", "suspected"} or item.lifecycle_status in {"EOL", "Obsolete", "NRND"})
    coverage_rate = len(items_with_supply_data) / len(items_with_mpn) if items_with_mpn else 0
    return {
        "project_id": project_id,
        "total_items": len(items),
        "items_with_mpn": len(items_with_mpn),
        "items_with_supply_data": len(items_with_supply_data),
        "zero_stock_count": zero_stock_count,
        "long_lead_count": long_lead_count,
        "eol_count": eol_count,
        "coverage_rate": coverage_rate,
    }
