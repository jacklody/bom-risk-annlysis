import sqlite3

import pandas as pd
import pytest

from src.database import initialize_database
from src.importers import SupplyValidationError, read_supply_excel, save_supply_import
from src.sample_data import SUPPLY_COLUMNS, build_sample_supply_data, create_sample_files


def write_supply_excel(path, rows, columns=None):
    pd.DataFrame(rows, columns=columns or SUPPLY_COLUMNS).to_excel(path, index=False)


def test_read_supply_excel_validates_and_returns_dataframe(tmp_path):
    sample_dir = tmp_path / "samples"
    _, supply_path = create_sample_files(sample_dir)

    df = read_supply_excel(supply_path)

    assert list(df.columns) == SUPPLY_COLUMNS
    assert len(df) == 8
    assert df.loc[0, "物料编码"] == "M001"


def test_read_supply_excel_reports_missing_required_field(tmp_path):
    invalid_path = tmp_path / "missing_lead_time.xlsx"
    rows = build_sample_supply_data()
    columns = [column for column in SUPPLY_COLUMNS if column != "标准交期"]
    write_supply_excel(invalid_path, rows, columns=columns)

    with pytest.raises(SupplyValidationError, match="缺少必填字段：标准交期"):
        read_supply_excel(invalid_path)


def test_read_supply_excel_reports_empty_material_code(tmp_path):
    invalid_path = tmp_path / "empty_material_code.xlsx"
    rows = build_sample_supply_data()
    rows[0]["物料编码"] = ""
    write_supply_excel(invalid_path, rows)

    with pytest.raises(SupplyValidationError, match="物料编码不能为空"):
        read_supply_excel(invalid_path)


def test_read_supply_excel_reports_non_numeric_supplier_count(tmp_path):
    invalid_path = tmp_path / "invalid_supplier_count.xlsx"
    rows = build_sample_supply_data()
    rows[0]["供应商数量"] = "不是数字"
    write_supply_excel(invalid_path, rows)

    with pytest.raises(SupplyValidationError, match="供应商数量必须为数字"):
        read_supply_excel(invalid_path)


def test_read_supply_excel_reports_non_numeric_lead_time(tmp_path):
    invalid_path = tmp_path / "invalid_lead_time.xlsx"
    rows = build_sample_supply_data()
    rows[0]["标准交期"] = "不是数字"
    write_supply_excel(invalid_path, rows)

    with pytest.raises(SupplyValidationError, match="标准交期必须为数字"):
        read_supply_excel(invalid_path)


def test_read_supply_excel_reports_non_numeric_inventory_price_and_rate(tmp_path):
    invalid_path = tmp_path / "invalid_inventory.xlsx"
    rows = build_sample_supply_data()
    rows[0]["当前库存"] = "不是数字"
    write_supply_excel(invalid_path, rows)

    with pytest.raises(SupplyValidationError, match="当前库存必须为数字"):
        read_supply_excel(invalid_path)


def test_save_supply_import_writes_rows_and_audit_log(tmp_path):
    db_path = tmp_path / "app.db"
    initialize_database(db_path)
    sample_dir = tmp_path / "samples"
    _, supply_path = create_sample_files(sample_dir)
    df = read_supply_excel(supply_path)

    saved_count = save_supply_import(df, file_name="sample_supply.xlsx", db_path=db_path, operator="测试用户")

    with sqlite3.connect(db_path) as conn:
        row_count = conn.execute("SELECT COUNT(*) FROM supply_risk_data").fetchone()[0]
        log = conn.execute("SELECT operation_type, operation_object, operation_result, operator FROM audit_logs ORDER BY id DESC LIMIT 1").fetchone()

    assert saved_count == len(df)
    assert row_count == len(df)
    assert log == ("导入供应数据", "sample_supply.xlsx", "成功", "测试用户")
