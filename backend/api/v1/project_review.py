"""新项目选型评审 API 端点 (T2-009)。

提供BOM物料选型评审结论的查询、审批和导出功能。

端点:
- GET  /api/v1/project-review/summary    获取评审汇总
- GET  /api/v1/project-review/bom-items   获取BOM物料评审列表
- POST /api/v1/project-review/approve     批准/驳回某物料选型
- GET  /api/v1/project-review/export      导出评审报告
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.project_review_service import (
    ProjectReviewService,
    ReviewItem,
    ReviewSummary,
    get_project_review_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/project-review", tags=["project-review"])


# ═══════════════════════════════════════════════════════════════════════════════
# 请求/响应模型
# ═══════════════════════════════════════════════════════════════════════════════

class SummaryResponse(BaseModel):
    """评审汇总响应。"""
    project_id: str
    project_name: str
    created_at: str = ""
    total_items: int = 0
    risk_distribution: dict[str, int] = {}
    category_coverage: dict[str, int] = {}
    approved_count: int = 0
    rejected_count: int = 0
    pending_count: int = 0


class BomItemResponse(BaseModel):
    """BOM物料评审项响应。"""
    bom_item_id: str
    mpn: str
    category: str
    manufacturer: str = ""
    risk_level: str = "gray"
    risk_score: float = 0.0
    exposure_score: float = 0.0
    escalation_rules: list[str] = []
    recommendation: str = ""
    alt_suggestions: list[str] = []
    approved: Optional[bool] = None


class BomItemListResponse(BaseModel):
    """BOM物料列表响应（分页）。"""
    items: list[BomItemResponse]
    total: int
    page: int
    page_size: int


class ApproveRequest(BaseModel):
    """审批请求。"""
    project_id: str
    bom_item_id: str
    approved: bool


class ApproveResponse(BaseModel):
    """审批响应。"""
    success: bool
    message: str = ""


class ExportResponse(BaseModel):
    """导出响应。"""
    format: str
    summary: dict
    items: list[dict]


# ═══════════════════════════════════════════════════════════════════════════════
# 辅助转换
# ═══════════════════════════════════════════════════════════════════════════════

def _get_service() -> ProjectReviewService:
    """获取 ProjectReviewService 实例。"""
    return get_project_review_service()


def _summary_to_response(summary: ReviewSummary) -> SummaryResponse:
    return SummaryResponse(
        project_id=summary.project_id,
        project_name=summary.project_name,
        created_at=summary.created_at,
        total_items=summary.total_items,
        risk_distribution=summary.risk_distribution,
        category_coverage=summary.category_coverage,
        approved_count=summary.approved_count,
        rejected_count=summary.rejected_count,
        pending_count=summary.pending_count,
    )


def _item_to_response(item: ReviewItem) -> BomItemResponse:
    return BomItemResponse(
        bom_item_id=item.bom_item_id,
        mpn=item.mpn,
        category=item.category,
        manufacturer=item.manufacturer,
        risk_level=item.risk_level,
        risk_score=item.risk_score,
        exposure_score=item.exposure_score,
        escalation_rules=item.escalation_rules,
        recommendation=item.recommendation,
        alt_suggestions=item.alt_suggestions,
        approved=item.approved,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# API 端点
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/summary", response_model=SummaryResponse)
def get_summary(
    project_id: str = Query(..., description="项目ID"),
) -> SummaryResponse:
    """获取评审汇总（风险等级分布、品类覆盖）。"""
    service = _get_service()
    summary = service.get_summary(project_id)
    return _summary_to_response(summary)


@router.get("/bom-items", response_model=BomItemListResponse)
def get_bom_items(
    project_id: str = Query(..., description="项目ID"),
    risk_level: Optional[str] = Query(None, description="风险等级筛选"),
    category: Optional[str] = Query(None, description="品类筛选"),
    manufacturer: Optional[str] = Query(None, description="供应商筛选"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
) -> BomItemListResponse:
    """获取BOM物料评审列表（分页+筛选）。"""
    service = _get_service()
    items, total = service.get_bom_items(
        project_id=project_id,
        risk_level=risk_level,
        category=category,
        manufacturer=manufacturer,
        page=page,
        page_size=page_size,
    )
    return BomItemListResponse(
        items=[_item_to_response(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/approve", response_model=ApproveResponse)
def approve_item(
    request: ApproveRequest,
) -> ApproveResponse:
    """批准/驳回某物料选型。"""
    service = _get_service()
    success = service.approve_item(
        project_id=request.project_id,
        bom_item_id=request.bom_item_id,
        approved=request.approved,
    )
    if not success:
        raise HTTPException(status_code=404, detail="物料未找到")
    return ApproveResponse(
        success=True,
        message=f"物料 {request.bom_item_id} 已{'批准' if request.approved else '驳回'}",
    )


@router.get("/export", response_model=ExportResponse)
def export_review(
    project_id: str = Query(..., description="项目ID"),
    format: str = Query("json", description="导出格式 (json/excel/pdf)"),
) -> ExportResponse:
    """导出评审报告。"""
    service = _get_service()
    data = service.export_review(project_id, format=format)
    return ExportResponse(**data)
