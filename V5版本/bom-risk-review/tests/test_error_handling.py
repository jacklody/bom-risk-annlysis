import sqlite3
from io import BytesIO

import pandas as pd
import pytest

from src.database import initialize_database
from src.importers import BomValidationError, SupplyValidationError, read_bom_excel, read_supply_excel
from src.risk_engine import evaluate_risks


def test_non_excel_file_raises_bom_validation_error_with_friendly_message():
    fake_file = BytesIO(b"this is not an excel file")
    fake_file.name = "test.txt"

    with pytest.raises(BomValidationError, match="BOM文件读取失败"):
        read_bom_excel(fake_file)


def test_non_excel_file_raises_supply_validation_error_with_friendly_message():
    fake_file = BytesIO(b"this is not an excel file")
    fake_file.name = "test.txt"

    with pytest.raises(SupplyValidationError, match="供应数据文件读取失败"):
        read_supply_excel(fake_file)


def test_empty_excel_raises_bom_validation_error():
    buf = BytesIO()
    pd.DataFrame().to_excel(buf, index=False)
    buf.seek(0)
    buf.name = "empty.xlsx"

    with pytest.raises(BomValidationError, match="文件中没有可导入的数据"):
        read_bom_excel(buf)


def test_empty_excel_raises_supply_validation_error():
    buf = BytesIO()
    pd.DataFrame().to_excel(buf, index=False)
    buf.seek(0)
    buf.name = "empty.xlsx"

    with pytest.raises(SupplyValidationError, match="文件中没有可导入的数据"):
        read_supply_excel(buf)


def bom_row(**overrides):
    default = {
        "物料编码": "M001", "物料名称": "测试物料", "规格型号": "A",
        "用量": 1, "是否虚拟件": "否", "替代料组": "", "是否共用料": "否",
    }
    default.update(overrides)
    return default


def supply_row(**overrides):
    default = {
        "物料编码": "M001", "供应商数量": 2, "主供应商": "供应商A",
        "标准交期": 20, "当前库存": 100, "库存变化率": 0.05,
        "当前价格": 10, "历史价格": 10, "是否停产": "否", "是否有替代料": "是",
    }
    default.update(overrides)
    return default


def test_zero_historical_price_adds_unable_to_calculate_price_warning():
    bom_df = pd.DataFrame([bom_row()])
    supply_df = pd.DataFrame([supply_row(历史价格=0)])

    results = evaluate_risks(bom_df, supply_df)
    row = results.iloc[0]
    assert "无法计算价格涨幅" in row["风险原因"]


def test_missing_supply_data_results_in_high_risk_with_explainable_reason():
    bom_df = pd.DataFrame([bom_row(物料编码="M999", 物料名称="无供应数据物料")])
    supply_df = pd.DataFrame([supply_row(物料编码="M001")])

    results = evaluate_risks(bom_df, supply_df)
    row = results.iloc[0]
    assert row["风险等级"] == "高"
    assert "未找到供应风险数据" in row["风险原因"]


def test_import_failure_writes_audit_log(tmp_path):
    db_path = tmp_path / "app.db"
    initialize_database(db_path)
    fake_file = BytesIO(b"not excel")
    fake_file.name = "bad.txt"

    try:
        read_bom_excel(fake_file, db_path=db_path)
    except BomValidationError:
        pass

    # 导入失败时应写入失败日志
    with sqlite3.connect(db_path) as conn:
        log = conn.execute(
            "SELECT operation_type, operation_result FROM audit_logs ORDER BY id DESC LIMIT 1"
        ).fetchone()

    assert log == ("导入BOM", "失败")
