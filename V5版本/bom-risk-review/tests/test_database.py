import sqlite3

from src.database import get_connection, initialize_database


EXPECTED_TABLES = {
    "import_batches",
    "bom_items",
    "supply_risk_data",
    "risk_results",
    "risk_rules",
    "audit_logs",
}


def table_names(db_path):
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {row[0] for row in rows}


def test_initialize_database_creates_required_tables(tmp_path):
    db_path = tmp_path / "app.db"

    initialize_database(db_path)

    assert EXPECTED_TABLES.issubset(table_names(db_path))


def test_initialize_database_seeds_default_rules_once(tmp_path):
    db_path = tmp_path / "app.db"

    initialize_database(db_path)
    initialize_database(db_path)

    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT rule_key, threshold_value FROM risk_rules ORDER BY rule_key").fetchall()

    rules = {rule_key: threshold_value for rule_key, threshold_value in rows}
    assert rules["lead_time_medium_days"] == 30
    assert rules["lead_time_high_days"] == 60
    assert rules["price_increase_rate"] == 0.2
    assert rules["inventory_drop_rate"] == 0.3
    assert len(rows) == 4
