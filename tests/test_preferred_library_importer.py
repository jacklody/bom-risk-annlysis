from openpyxl import Workbook
from app.database import SessionLocal, init_db
from app.models.preferred import PreferredPart
from app.services.preferred_library.normalizer import (
    normalize_brand,
    normalize_mpn,
    parse_preferred_level,
)
from app.services.preferred_library.excel_importer import PreferredLibraryImporter


def test_preferred_status_text_maps_to_level_and_control_status():
    assert parse_preferred_level("⭐强推入库(跨3+项目)") == ("strong_recommended", "preferred")
    assert parse_preferred_level("📌中推入库(跨2项目)") == ("medium_recommended", "preferred")
    assert parse_preferred_level("待评审") == ("unknown", "pending_review")
    assert parse_preferred_level("禁用") == ("unknown", "blocked")
    assert parse_preferred_level("限用") == ("unknown", "restricted")


def test_brand_and_mpn_normalization_removes_noise():
    assert normalize_brand(" TDK ") == "TDK"
    assert normalize_brand("国巨/YAGEO") == "YAGEO"
    assert normalize_mpn(" C3225X5R1A226M250AC ") == "C3225X5R1A226M250AC"
    assert normalize_mpn("SOT-23 / S8050") == "SOT23S8050"


def test_import_multi_sheet_preferred_library_maps_rows(tmp_path):
    init_db()
    db = SessionLocal()
    db.query(PreferredPart).delete()
    db.commit()
    file_path = tmp_path / "preferred.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "二极管"
    ws.append(["品牌", "名称", "通用化状态", "物料号", "型号", "封装形式", "应用方案", "成本"])
    ws.append(["YAGEO", "快恢复二极管", "⭐强推入库(跨3+项目)", "D-001", "US1M", "SMA", "电源整流", 0.12])
    ws2 = wb.create_sheet("压敏电阻")
    ws2.append(["品牌", "名称", "通用化状态", "物料号", "型号", "尺寸", "应用方案", "未税"])
    ws2.append(["TDK", "压敏电阻", "待评审", "RV-001", "B72214S", "14D", "浪涌保护", 0.31])
    wb.save(file_path)

    try:
        result = PreferredLibraryImporter(db).import_file(str(file_path), source_file="preferred.xlsx")
        assert result["sheets"] == 2
        assert result["imported_parts"] == 2
        assert result["strong_recommended_count"] == 1
        assert result["pending_review_count"] == 1
        diode = db.query(PreferredPart).filter(PreferredPart.part_number == "D-001").one()
        assert diode.source_sheet == "二极管"
        assert diode.category_level_3 == "二极管"
        assert diode.normalized_mpn == "US1M"
        assert diode.preferred_level == "strong_recommended"
        assert diode.control_status == "preferred"
    finally:
        db.close()
