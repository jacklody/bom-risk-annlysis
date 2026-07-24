import sqlite3
from pathlib import Path

from src.models import CREATE_TABLES_SQL, DEFAULT_RULES


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "app.db"


def get_connection(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database(db_path: Path | str = DEFAULT_DB_PATH) -> Path:
    path = Path(db_path)
    with get_connection(path) as conn:
        for sql in CREATE_TABLES_SQL:
            conn.execute(sql)
        conn.executemany(
            """
            INSERT OR IGNORE INTO risk_rules (rule_key, rule_name, threshold_value, unit)
            VALUES (?, ?, ?, ?)
            """,
            DEFAULT_RULES,
        )
        conn.commit()
    return path
