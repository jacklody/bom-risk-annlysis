import sqlite3
from pathlib import Path

from src.database import DEFAULT_DB_PATH, get_connection


def write_audit_log(
    operation_type: str,
    operation_object: str | None,
    operation_result: str,
    operator: str | None = None,
    message: str | None = None,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> None:
    try:
        with get_connection(db_path) as conn:
            conn.execute(
                """
                INSERT INTO audit_logs (
                    operation_type,
                    operation_object,
                    operation_result,
                    operator,
                    message
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (operation_type, operation_object, operation_result, operator, message),
            )
            conn.commit()
    except sqlite3.OperationalError:
        pass
