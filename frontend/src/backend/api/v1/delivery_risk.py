"""交付风险预警 API (T2-010)。

端点:
- GET  /api/v1/delivery-risk/overview        项目级风险总览（红黄绿灯）
- GET  /api/v1/delivery-risk/materials       物料级风险列表（按风险分排序）
- GET  /api/v1/delivery-risk/timeline        风险时间线（最近30天事件流）
- GET  /api/v1/delivery-risk/recommendations 建议措施列表
- POST /api/v1/delivery-risk/ack             确认某条风险已处理
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.delivery_risk_service import DeliveryRiskService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/delivery-risk", tags=["delivery-risk"])


# ═══════════════════════════════════════════════════════════════════════════════
# 请求/响应模型
# ═══════════════════════════════════════════════════════════════════════════════

class ProjectOverviewResponse(BaseModel):
    """项目级风险总览响应。"""
    project_id: int
    project_name: str
    overall_risk_level: str  # "red" | "orange" | "yellow" | "green"
    total_materials: int
    red_count: int
    orange_count: int
    yellow_count: int
    green_count: int
    recent_event_count: int


class MaterialRiskItem(BaseModel):
    """物料级风险条目。"""
    material_id: int
    mpn: str
    brand: str
    category: str
    risk_score: float
    risk_level: str
    trend: str  # "up" | "down" | "flat"
    lead_time_impact_weeks: float
    exposure_score: float
    suggestion: str
    is_acknowledged: bool = False


class MaterialRiskListResponse(BaseModel):
    """物料风险列表响应。"""
    project_id: int
    materials: list[MaterialRiskItem]
    total_count: int
    high_risk_count: int


class TimelineEventItem(BaseModel):
    """时间线事件条目。"""
    event_id: int
    timestamp: str
    title: str
    event_type: str
    severity: str
    source: str
    affected_materials: list[str]


class TimelineResponse(BaseModel):
    """时间线响应。"""
    project_id: int
    events: list[TimelineEventItem]
    total_count: int


class RecommendationItemResponse(BaseModel):
    """建议条目。"""
    rec_id: str
    role: str
    action_type: str
    title: str
    detail: str
    urgency: str
    material: str


class RecommendationsResponse(BaseModel):
    """建议列表响应。"""
    project_id: int
    recommendations: list[RecommendationItemResponse]
    total_count: int


class AckRequest(BaseModel):
    """确认风险已处理请求。"""
    material_id: int = Field(..., description="物料ID")


class AckResponse(BaseModel):
    """确认风险响应。"""
    success: bool
    message: str


# ═══════════════════════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════════════════════

def _get_service(db: Session) -> DeliveryRiskService:
    """创建服务实例。"""
    return DeliveryRiskService(db)


# ═══════════════════════════════════════════════════════════════════════════════
# 端点实现
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/overview", response_model=ProjectOverviewResponse)
def get_project_overview(
    project_id: int = Query(..., description="项目ID"),
    db: Session = Depends(get_db),
) -> ProjectOverviewResponse:
    """获取项目级风险总览（红黄绿灯）。"""
    service = _get_service(db)
    overview = service.get_project_overview(project_id)
    if not overview:
        raise HTTPException(status_code=404, detail=f"项目 {project_id} 不存在")
    return ProjectOverviewResponse(**overview.to_dict())


@router.get("/materials", response_model=MaterialRiskListResponse)
def get_material_risk_list(
    project_id: int = Query(..., description="项目ID"),
    db: Session = Depends(get_db),
) -> MaterialRiskListResponse:
    """获取物料级风险列表（按风险分排序）。"""
    service = _get_service(db)
    materials = service.get_material_risk_list(project_id)
    high_risk_count = sum(1 for m in materials if m.risk_level in ("red", "orange"))
    return MaterialRiskListResponse(
        project_id=project_id,
        materials=[MaterialRiskItem(**m.to_dict()) for m in materials],
        total_count=len(materials),
        high_risk_count=high_risk_count,
    )


@router.get("/timeline", response_model=TimelineResponse)
def get_risk_timeline(
    project_id: int = Query(..., description="项目ID"),
    days: int = Query(30, description="回溯天数", ge=1, le=365),
    db: Session = Depends(get_db),
) -> TimelineResponse:
    """获取风险时间线（最近N天事件流）。"""
    service = _get_service(db)
    events = service.get_risk_timeline(project_id, days=days)
    return TimelineResponse(
        project_id=project_id,
        events=[TimelineEventItem(**e.to_dict()) for e in events],
        total_count=len(events),
    )


@router.get("/recommendations", response_model=RecommendationsResponse)
def get_recommendations(
    project_id: int = Query(..., description="项目ID"),
    db: Session = Depends(get_db),
) -> RecommendationsResponse:
    """获取建议措施列表。"""
    service = _get_service(db)
    recs = service.get_recommendations(project_id)
    return RecommendationsResponse(
        project_id=project_id,
        recommendations=[RecommendationItemResponse(**r.to_dict()) for r in recs],
        total_count=len(recs),
    )


@router.post("/ack", response_model=AckResponse)
def acknowledge_risk(
    request: AckRequest,
    db: Session = Depends(get_db),
) -> AckResponse:
    """确认某条风险已处理。"""
    service = _get_service(db)
    success = service.acknowledge_risk(request.material_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"物料 {request.material_id} 不存在",
        )
    return AckResponse(success=True, message="风险已确认处理")
