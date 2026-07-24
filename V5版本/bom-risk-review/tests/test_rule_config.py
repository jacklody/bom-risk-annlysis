import sqlite3

from src.database import initialize_database
from src.importers import read_bom_excel, read_supply_excel, save_bom_import, save_supply_import
from src.rule_config import get_rules, update_rule
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
    return db_path, batch_id


def test_get_rules_returns_default_thresholds(tmp_path):
    db_path = tmp_path / "app.db"
    initialize_database(db_path)

    rules = get_rules(db_path)

    assert rules["lead_time_medium_days"] == 30
    assert rules["lead_time_high_days"] == 60
    assert rules["price_increase_rate"] == 0.2
    assert rules["inventory_drop_rate"] == 0.3


def test_update_rule_changes_threshold_and_writes_audit_log(tmp_path):
    db_path = tmp_path / "app.db"
    initialize_database(db_path)

    update_rule("lead_time_high_days", 50, operator="测试用户", db_path=db_path)

    rules = get_rules(db_path)
    assert rules["lead_time_high_days"] == 50

    with sqlite3.connect(db_path) as conn:
        log = conn.execute(
            "SELECT operation_type, operation_object, operation_result, operator FROM audit_logs ORDER BY id DESC LIMIT 1"
        ).fetchone()

    assert log == ("修改规则", "lead_time_high_days", "成功", "测试用户")


def test_scoring_uses_updated_rule_threshold(tmp_path):
    db_path, batch_id = prepare_scored_batch(tmp_path)

    # M001 交期为 25 天，默认中风险阈值 30 天时为低风险
    results_before, _ = run_scoring_for_batch(batch_id, db_path=db_path, operator="测试用户")
    m001_before = results_before[results_before["物料编码"] == "M001"].iloc[0]
    assert m001_before["风险等级"] == "低"

    # 将中风险阈值改为 20，交期 25 变为中风险
    update_rule("lead_time_medium_days", 20, operator="测试用户", db_path=db_path)

    # 重新评分
    results_after, _ = run_scoring_for_batch(batch_id, db_path=db_path, operator="测试用户")
    m001_after = results_after[results_after["物料编码"] == "M001"].iloc[0]
    assert m001_after["风险等级"] == "中"
