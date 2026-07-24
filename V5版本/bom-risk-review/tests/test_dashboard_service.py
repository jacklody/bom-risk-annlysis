from src.dashboard_service import (
    get_latest_bom_batch,
    get_latest_scoring_summary,
    get_recent_audit_logs,
    get_scored_batches,
    get_scoring_results_for_batch,
)
from src.database import initialize_database
from src.importers import read_bom_excel, read_supply_excel, save_bom_import, save_supply_import
from src.sample_data import create_sample_files
from src.scoring_service import run_scoring_for_batch


def prepare_scored_batch(tmp_path):
    db_path = tmp_path / "app.db"
    initialize_database(db_path)
    sample_dir = tmp_path / "samples"
    bom_path, supply_path = create_sample_files(sample_dir)
    bom_df = read_bom_excel(bom_path)
    supply_df = read_supply_excel(supply_path)
    batch_id = save_bom_import(bom_df, file_name="sample_bom.xlsx", db_path=db_path, operator="测试用户")
    save_supply_import(supply_df, file_name="sample_supply.xlsx", db_path=db_path, operator="测试用户")
    results, summary = run_scoring_for_batch(batch_id, db_path=db_path, operator="测试用户")
    return db_path, batch_id, len(results), summary


def test_get_latest_bom_batch_returns_most_recent_bom_import(tmp_path):
    db_path, batch_id, row_count, _ = prepare_scored_batch(tmp_path)

    latest_batch = get_latest_bom_batch(db_path)

    assert latest_batch["id"] == batch_id
    assert latest_batch["file_name"] == "sample_bom.xlsx"
    assert latest_batch["row_count"] == row_count


def test_get_latest_scoring_summary_matches_saved_results(tmp_path):
    db_path, batch_id, row_count, summary = prepare_scored_batch(tmp_path)

    latest_summary = get_latest_scoring_summary(db_path)

    assert latest_summary["batch_id"] == batch_id
    assert latest_summary["物料总数"] == row_count
    assert latest_summary["高风险数量"] == summary["高风险数量"]
    assert latest_summary["中风险数量"] == summary["中风险数量"]
    assert latest_summary["低风险数量"] == summary["低风险数量"]


def test_get_recent_audit_logs_returns_latest_five_logs(tmp_path):
    db_path, _, _, _ = prepare_scored_batch(tmp_path)

    logs = get_recent_audit_logs(db_path, limit=5)

    assert 1 <= len(logs) <= 5
    assert {"operation_time", "operation_type", "operation_object", "operation_result", "operator"}.issubset(logs[0].keys())


def test_get_scored_batches_and_results_for_selected_batch(tmp_path):
    db_path, batch_id, row_count, _ = prepare_scored_batch(tmp_path)

    batches = get_scored_batches(db_path)
    results = get_scoring_results_for_batch(batch_id, db_path)

    assert len(batches) == 1
    assert batches[0]["id"] == batch_id
    assert len(results) == row_count
    assert "风险等级" in results.columns
    assert "推荐结论" in results.columns
