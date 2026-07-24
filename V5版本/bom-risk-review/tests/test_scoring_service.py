import sqlite3

from src.database import initialize_database
from src.importers import read_bom_excel, read_supply_excel, save_bom_import, save_supply_import
from src.sample_data import create_sample_files
from src.scoring_service import (
    get_bom_batches,
    load_bom_items_for_batch,
    load_current_supply_data,
    run_scoring_for_batch,
)


def prepare_imported_data(tmp_path):
    db_path = tmp_path / "app.db"
    initialize_database(db_path)
    sample_dir = tmp_path / "samples"
    bom_path, supply_path = create_sample_files(sample_dir)
    bom_df = read_bom_excel(bom_path)
    supply_df = read_supply_excel(supply_path)
    batch_id = save_bom_import(bom_df, file_name="sample_bom.xlsx", db_path=db_path, operator="测试用户")
    save_supply_import(supply_df, file_name="sample_supply.xlsx", db_path=db_path, operator="测试用户")
    return db_path, batch_id, len(bom_df)


def test_get_bom_batches_returns_imported_bom_batches(tmp_path):
    db_path, batch_id, _ = prepare_imported_data(tmp_path)

    batches = get_bom_batches(db_path)

    assert len(batches) == 1
    assert batches[0]["id"] == batch_id
    assert batches[0]["file_name"] == "sample_bom.xlsx"


def test_load_bom_items_for_batch_returns_bom_dataframe(tmp_path):
    db_path, batch_id, row_count = prepare_imported_data(tmp_path)

    bom_df = load_bom_items_for_batch(batch_id, db_path)

    assert len(bom_df) == row_count
    assert "物料编码" in bom_df.columns
    assert "物料名称" in bom_df.columns


def test_load_current_supply_data_returns_supply_dataframe(tmp_path):
    db_path, _, _ = prepare_imported_data(tmp_path)

    supply_df = load_current_supply_data(db_path)

    assert len(supply_df) == 8
    assert "物料编码" in supply_df.columns
    assert "标准交期" in supply_df.columns


def test_run_scoring_for_batch_saves_results_summary_and_audit_log(tmp_path):
    db_path, batch_id, row_count = prepare_imported_data(tmp_path)

    results, summary = run_scoring_for_batch(batch_id, db_path=db_path, operator="测试用户")

    with sqlite3.connect(db_path) as conn:
        saved_count = conn.execute("SELECT COUNT(*) FROM risk_results WHERE batch_id = ?", (batch_id,)).fetchone()[0]
        log = conn.execute("SELECT operation_type, operation_object, operation_result, operator FROM audit_logs ORDER BY id DESC LIMIT 1").fetchone()

    assert len(results) == row_count
    assert saved_count == row_count
    assert summary["物料总数"] == row_count
    assert summary["高风险数量"] + summary["中风险数量"] + summary["低风险数量"] == row_count
    assert log == ("执行评分", str(batch_id), "成功", "测试用户")
