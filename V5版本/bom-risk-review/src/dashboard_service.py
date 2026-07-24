from pathlib import Path

import pandas as pd

from src.database import DEFAULT_DB_PATH, get_connection


RESULT_COLUMNS = ["物料编码", "物料名称", "风险等级", "推荐结论", "风险原因", "建议动作"]


def get_latest_bom_batch(db_path: Path | str = DEFAULT_DB_PATH) -> dict | None:
    with get_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, file_name, row_count, created_at
            FROM import_batches
            WHERE batch_type = 'BOM'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
    return dict(row) if row else None


def get_latest_scoring_summary(db_path: Path | str = DEFAULT_DB_PATH) -> dict | None:
    with get_connection(db_path) as conn:
        latest = conn.execute(
            """
            SELECT batch_id, MAX(created_at) AS latest_time
            FROM risk_results
            GROUP BY batch_id
            ORDER BY latest_time DESC, batch_id DESC
            LIMIT 1
            """
        ).fetchone()
        if latest is None:
            return None

        rows = conn.execute(
            """
            SELECT risk_level, COUNT(*) AS count
            FROM risk_results
            WHERE batch_id = ?
            GROUP BY risk_level
            """,
            (latest["batch_id"],),
        ).fetchall()

    counts = {row["risk_level"]: row["count"] for row in rows}
    total = sum(counts.values())
    return {
        "batch_id": latest["batch_id"],
        "物料总数": int(total),
        "高风险数量": int(counts.get("高", 0)),
        "中风险数量": int(counts.get("中", 0)),
        "低风险数量": int(counts.get("低", 0)),
    }


def get_recent_audit_logs(db_path: Path | str = DEFAULT_DB_PATH, limit: int = 5) -> list[dict]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT operation_time, operation_type, operation_object, operation_result, operator
            FROM audit_logs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_scored_batches(db_path: Path | str = DEFAULT_DB_PATH) -> list[dict]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT
                b.id,
                b.file_name,
                b.row_count,
                b.created_at
            FROM import_batches b
            INNER JOIN risk_results r ON r.batch_id = b.id
            WHERE b.batch_type = 'BOM'
            ORDER BY b.id DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_scoring_results_for_batch(batch_id: int, db_path: Path | str = DEFAULT_DB_PATH) -> pd.DataFrame:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                material_code AS 物料编码,
                material_name AS 物料名称,
                risk_level AS 风险等级,
                recommendation AS 推荐结论,
                risk_reasons AS 风险原因,
                suggested_action AS 建议动作
            FROM risk_results
            WHERE batch_id = ?
            ORDER BY id
            """,
            (batch_id,),
        ).fetchall()
    return pd.DataFrame([dict(row) for row in rows], columns=RESULT_COLUMNS)
