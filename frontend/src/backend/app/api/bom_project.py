"""BOM项目管理 + 增量扫描接口"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.bom import BomProject, BomItem
from app.models.event import MarketEvent
from app.services.incremental_scanner import IncrementalScanner
from app.services.bom_matcher import BOMMatcher

router = APIRouter()


@router.get("/projects")
def list_projects(
    db: Session = Depends(get_db),
    status: str | None = Query(None),
):
    query = db.query(BomProject)
    if status:
        query = query.filter(BomProject.status == status)
    projects = query.order_by(BomProject.updated_at.desc()).limit(50).all()
    return {"projects": [p.to_summary() for p in projects]}


@router.get("/projects/{project_id}")
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(BomProject).filter(BomProject.id == project_id).first()
    if not project:
        return {"error": "Project not found"}

    items = (
        db.query(BomItem)
        .filter(BomItem.bom_upload_id == project_id)
        .order_by(BomItem.row_number)
        .all()
    )

    return {
        "project": project.to_summary(),
        "items": [
            {
                "id": i.id,
                "row_number": i.row_number,
                "part_number": i.raw_part_number,
                "brand": i.raw_brand,
                "category": i.raw_category,
                "risk_level": i.risk_level.value if i.risk_level else "gray",
                "risk_score": i.risk_score,
                "risk_reason": i.risk_reason,
                "production_risk_level": i.production_risk_level,
                "production_risk_score": i.production_risk_score,
                "lead_time_risk_weeks": i.lead_time_risk_weeks,
                "eol_status": i.eol_status,
                "total_stock": i.total_stock,
                "supplier_count": i.supplier_count,
                "lead_time_days": i.lead_time_days,
                "unit_price": i.unit_price,
                "lifecycle_status": i.lifecycle_status,
                "commonality_score": i.commonality_score,
                "supply_risk_tags": i.supply_risk_tags,
                "supply_risk_reason": i.supply_risk_reason,
                "procurement_suggestion": i.procurement_suggestion,
                "last_risk_level": i.last_risk_level,
                "risk_changed_at": i.risk_changed_at.isoformat()
                if i.risk_changed_at else None,
                "is_new_risk": (
                    i.last_risk_level
                    and i.risk_level
                    and i.risk_level.value != i.last_risk_level
                    and i.risk_level.value in ("red", "yellow")
                ),
            }
            for i in items
        ],
    }


@router.get("/projects/{project_id}/new-risks")
def get_new_risks(project_id: int, db: Session = Depends(get_db)):
    items = (
        db.query(BomItem)
        .filter(
            BomItem.bom_upload_id == project_id,
            BomItem.last_risk_level is not None,
            BomItem.risk_level.in_(["red", "yellow"]),
            BomItem.last_risk_level != BomItem.risk_level,
        )
        .all()
    )
    return {
        "new_risks": [
            {
                "id": i.id,
                "part_number": i.raw_part_number,
                "risk_level": i.risk_level.value if i.risk_level else "",
                "risk_reason": i.risk_reason,
                "changed_at": i.risk_changed_at.isoformat()
                if i.risk_changed_at else None,
            }
            for i in items
        ]
    }


@router.post("/projects/{project_id}/archive")
def archive_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(BomProject).filter(BomProject.id == project_id).first()
    if not project:
        return {"error": "Project not found"}
    project.status = "archived"
    db.commit()
    return {"status": "ok"}


@router.post("/projects/rescan-all")
def rescan_all(db: Session = Depends(get_db)):
    scanner = IncrementalScanner(db)
    return scanner.scan_all_projects()


@router.get("/projects/{project_id}/events")
def get_project_events(project_id: int, db: Session = Depends(get_db)):
    """BOM→关联的市场事件"""
    items = (
        db.query(BomItem.matched_event_ids)
        .filter(BomItem.bom_upload_id == project_id)
        .all()
    )
    event_ids = set()
    for (ids,) in items:
        if ids:
            for eid in ids.split(","):
                if eid.strip():
                    event_ids.add(int(eid.strip()))
    events = (
        db.query(MarketEvent)
        .filter(MarketEvent.id.in_(event_ids))
        .all()
    )
    return {"events": [e.to_dict() for e in events]}


@router.get("/events/{event_id}/affected-projects")
def get_affected_projects(event_id: int, db: Session = Depends(get_db)):
    """事件→影响的BOM项目"""
    items = (
        db.query(BomItem.bom_upload_id)
        .filter(BomItem.matched_event_ids.contains(str(event_id)))
        .distinct()
        .all()
    )
    project_ids = [i[0] for i in items]
    projects = (
        db.query(BomProject)
        .filter(BomProject.id.in_(project_ids))
        .all()
    )
    return {"projects": [p.to_summary() for p in projects]}
