from pathlib import Path
from openpyxl import Workbook
from fastapi.testclient import TestClient
from app.database import SessionLocal, init_db
from app.main import app
from app.models.bom import BomItem, BomProject, RiskLevel
from app.models.preferred import BomSelectionReview, PreferredPart

client = TestClient(app)


def _clear():
    init_db()
    db = SessionLocal()
    db.query(BomSelectionReview).delete()
    db.query(PreferredPart).delete()
    db.query(BomItem).delete()
    db.query(BomProject).delete()
    db.commit()
    db.close()


def test_preferred_library_import_summary_and_review_api(tmp_path):
    _clear()
    file_path = tmp_path / "preferred.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "二极管"
    ws.append(["品牌", "名称", "通用化状态", "物料号", "型号", "封装形式", "应用方案", "成本"])
    ws.append(["YAGEO", "快恢复二极管", "⭐强推入库(跨3+项目)", "D-001", "US1M", "SMA", "电源整流", 0.12])
    wb.save(file_path)

    with file_path.open("rb") as f:
        resp = client.post("/api/preferred-library/import", files={"file": ("preferred.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert resp.status_code == 200
    assert resp.json()["imported_parts"] == 1

    summary = client.get("/api/preferred-library/summary")
    assert summary.status_code == 200
    assert summary.json()["total_parts"] == 1
    assert summary.json()["strong_recommended_count"] == 1

    db = SessionLocal()
    db.add(BomProject(id=301, filename="new.csv", project_name="新项目", total_items=1))
    db.add(BomItem(bom_upload_id=301, row_number=1, raw_part_number="D-001", raw_brand="YAGEO", raw_category="二极管", raw_spec="US1M SMA", risk_level=RiskLevel.GREEN))
    db.commit()
    db.close()

    review = client.post("/api/preferred-library/review/301")
    assert review.status_code == 200
    data = review.json()
    assert data["summary"]["preferred_hit_count"] == 1
    assert data["items"][0]["selection_risk_level"] == "green"
