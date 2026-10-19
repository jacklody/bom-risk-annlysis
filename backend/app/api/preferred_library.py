import os
import shutil
import tempfile
from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.preferred import PreferredPart
from app.services.preferred_library.excel_importer import PreferredLibraryImporter
from app.services.preferred_library.review_service import PreferredLibraryReviewService

router = APIRouter(prefix="/api/preferred-library", tags=["preferred-library"])


@router.post("/import")
def import_preferred_library(file: UploadFile = File(...), db: Session = Depends(get_db)):
    suffix = os.path.splitext(file.filename or "preferred.xlsx")[1] or ".xlsx"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    try:
        return PreferredLibraryImporter(db).import_file(tmp_path, source_file=file.filename or "preferred.xlsx")
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


@router.get("/summary")
def preferred_summary(db: Session = Depends(get_db)):
    parts = db.query(PreferredPart).all()
    categories = {p.category_level_3 for p in parts if p.category_level_3}
    return {
        "total_parts": len(parts),
        "category_count": len(categories),
        "strong_recommended_count": sum(1 for p in parts if p.preferred_level == "strong_recommended"),
        "medium_recommended_count": sum(1 for p in parts if p.preferred_level == "medium_recommended"),
        "pending_review_count": sum(1 for p in parts if p.control_status == "pending_review"),
        "blocked_count": sum(1 for p in parts if p.control_status == "blocked"),
        "restricted_count": sum(1 for p in parts if p.control_status == "restricted"),
    }


@router.get("/parts")
def list_preferred_parts(
    category: str | None = Query(None),
    brand: str | None = Query(None),
    status: str | None = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(PreferredPart)
    if category:
        query = query.filter(PreferredPart.category_level_3.contains(category))
    if brand:
        query = query.filter(PreferredPart.normalized_brand.contains(brand.upper()))
    if status:
        query = query.filter(PreferredPart.control_status == status)
    parts = query.order_by(PreferredPart.id.desc()).limit(200).all()
    return {"parts": [p.to_dict() for p in parts]}


@router.post("/review/{bom_project_id}")
def review_project(bom_project_id: int, db: Session = Depends(get_db)):
    return PreferredLibraryReviewService(db).review_project(bom_project_id)


@router.get("/review/{bom_project_id}")
def get_review(bom_project_id: int, db: Session = Depends(get_db)):
    return PreferredLibraryReviewService(db).get_latest_review(bom_project_id)
