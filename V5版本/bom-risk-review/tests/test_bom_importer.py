import sqlite3

import pandas as pd
import pytest

from src.database import initialize_database
from src.importers import BomValidationError, read_bom_excel, save_bom_import
from src.sample_data import BOM_COLUMNS, build_sample_bom_data, create_sample_files


def write_bom_excel(path, rows, columns=None):
    pd.DataFrame(rows, columns=columns or BOM_COLUMNS).to_excel(path, index=False)


def test_read_bom_excel_validates_and_returns_dataframe(tmp_path):
    sample_dir = tmp_path / "samples"
    bom_path, _ = create_sample_files(sample_dir)

    df = read_bom_excel(bom_path)

    assert list(df.columns) == BOM_COLUMNS
    assert len(df) == 8
    assert df.loc[0, "物料编码"] == "M001"


def test_read_bom_excel_reports_missing_required_field(tmp_path):
    invalid_path = tmp_path / "missing_material_code.xlsx"
    rows = build_sample_bom_data()
    columns = [column for column in BOM_COLUMNS if column != "物料编码"]
    write_bom_excel(invalid_path, rows, columns=columns)

    with pytest.raises(BomValidationError, match="缺少必填字段：物料编码"):
        read_bom_excel(invalid_path)


def test_read_bom_excel_reports_empty_material_code(tmp_path):
    invalid_path = tmp_path / "empty_material_code.xlsx"
    rows = build_sample_bom_data()
    rows[0]["物料编码"] = ""
    write_bom_excel(invalid_path, rows)

    with pytest.raises(BomValidationError, match="物料编码不能为空"):
        read_bom_excel(invalid_path)


def test_read_bom_excel_reports_duplicate_material_code(tmp_path):
    invalid_path = tmp_path / "duplicate_material_code.xlsx"
    rows = build_sample_bom_data()
    rows[1]["物料编码"] = rows[0]["物料编码"]
    write_bom_excel(invalid_path, rows)

    with pytest.raises(BomValidationError, match="物料编码不能重复"):
        read_bom_excel(invalid_path)


def test_read_bom_excel_reports_non_numeric_quantity(tmp_path):
    invalid_path = tmp_path / "invalid_quantity.xlsx"
    rows = build_sample_bom_data()
    rows[0]["用量"] = "不是数字"
    write_bom_excel(invalid_path, rows)

    with pytest.raises(BomValidationError, match="用量必须为数字"):
        read_bom_excel(invalid_path)


def test_save_bom_import_writes_batch_items_and_audit_log(tmp_path):
    db_path = tmp_path / "app.db"
    initialize_database(db_path)
    sample_dir = tmp_path / "samples"
    bom_path, _ = create_sample_files(sample_dir)
    df = read_bom_excel(bom_path)

    batch_id = save_bom_import(df, file_name="sample_bom.xlsx", db_path=db_path, operator="测试用户")

    with sqlite3.connect(db_path) as conn:
        batch = conn.execute("SELECT batch_type, file_name, row_count FROM import_batches WHERE id = ?", (batch_id,)).fetchone()
        item_count = conn.execute("SELECT COUNT(*) FROM bom_items WHERE batch_id = ?", (batch_id,)).fetchone()[0]
        log = conn.execute("SELECT operation_type, operation_object, operation_result, operator FROM audit_logs ORDER BY id DESC LIMIT 1").fetchone()

    assert batch == ("BOM", "sample_bom.xlsx", len(df))
    assert item_count == len(df)
    assert log == ("导入BOM", "sample_bom.xlsx", "成功", "测试用户")
