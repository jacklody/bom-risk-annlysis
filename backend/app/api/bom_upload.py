"""BOM上传接口（v2 — 支持单文件/多文件批量）"""

from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.bom import BomItem, BomProject
from app.services.bom_parser import parse_bom_file, normalize_item

router = APIRouter()


def _process_upload(contents: bytes, filename: str, project_name: str, db: Session) -> dict:
    """处理单个BOM文件上传，返回项目信息"""
    items_data = parse_bom_file(contents, filename)
    # 过滤掉part_number为空的行
    items_data = [r for r in items_data if r.get("part_number")]

    name = project_name or filename.rsplit(".", 1)[0]
    project = BomProject(
        filename=filename,
        project_name=name,
        total_items=len(items_data),
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    multi_brand_count = 0
    for idx, row in enumerate(items_data):
        norm = normalize_item(row)
        if norm.get("is_multi_brand"):
            multi_brand_count += 1
        item = BomItem(
            bom_upload_id=project.id,
            row_number=idx + 1,
            raw_part_number=row.get("part_number", ""),
            raw_description=row.get("description", ""),
            raw_brand=row.get("brand", ""),
            raw_category=row.get("category", ""),
            raw_spec=row.get("spec", ""),
            raw_qty=str(row.get("qty", "1")),
            normalized_brand=norm.get("brand"),
            normalized_category=norm.get("category"),
        )
        db.add(item)

    db.commit()
    return {
        "upload_id": project.id,
        "project_name": name,
        "total_items": len(items_data),
        "multi_brand_items": multi_brand_count,
    }


@router.post("/upload")
async def upload_bom(
    file: UploadFile = File(...),
    project_name: str = Form(""),
    db: Session = Depends(get_db),
):
    """上传单个BOM文件（Excel/CSV/XLS）"""
    contents = await file.read()
    return _process_upload(contents, file.filename, project_name, db)


@router.post("/upload-batch")
async def upload_bom_batch(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """批量上传多个BOM文件"""
    results = []
    for f in files:
        contents = await f.read()
        try:
            r = _process_upload(contents, f.filename, "", db)
            results.append({"filename": f.filename, "status": "ok", **r})
        except Exception as e:
            results.append({"filename": f.filename, "status": "error", "error": str(e)})
    return {"uploads": results, "total": len(results)}


@router.get("/lists")
def list_uploads(db: Session = Depends(get_db)):
    projects = (
        db.query(BomProject)
        .order_by(BomProject.created_at.desc())
        .limit(20)
        .all()
    )
    return [p.to_summary() for p in projects]
