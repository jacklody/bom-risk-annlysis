from pathlib import Path

import pandas as pd

from src.audit_log import write_audit_log
from src.database import DEFAULT_DB_PATH, get_connection
from src.risk_engine import evaluate_risks


def get_bom_batches(db_path: Path | str = DEFAULT_DB_PATH) -> list[dict]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, file_name, row_count, created_at
            FROM import_batches
            WHERE batch_type = 'BOM'
            ORDER BY id DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def load_bom_items_for_batch(batch_id: int, db_path: Path | str = DEFAULT_DB_PATH) -> pd.DataFrame:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                bom_version AS BOM版本,
                material_code AS 物料编码,
                material_name AS 物料名称,
                specification AS 规格型号,
                quantity AS 用量,
                is_virtual AS 是否虚拟件,
                alternative_group AS 替代料组,
                is_common AS 是否共用料
            FROM bom_items
            WHERE batch_id = ?
            ORDER BY id
            """,
            (batch_id,),
        ).fetchall()
    return pd.DataFrame([dict(row) for row in rows])


def load_current_supply_data(db_path: Path | str = DEFAULT_DB_PATH) -> pd.DataFrame:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                material_code AS 物料编码,
                supplier_count AS 供应商数量,
                primary_supplier AS 主供应商,
                lead_time_days AS 标准交期,
                current_inventory AS 当前库存,
                inventory_drop_rate AS 库存变化率,
                current_price AS 当前价格,
                historical_price AS 历史价格,
                is_discontinued AS 是否停产,
                has_alternative AS 是否有替代料
            FROM supply_risk_data
            ORDER BY id
            """
        ).fetchall()
    return pd.DataFrame([dict(row) for row in rows])


def _load_rules(db_path: Path | str = DEFAULT_DB_PATH) -> dict:
    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT rule_key, threshold_value FROM risk_rules").fetchall()
    return {row["rule_key"]: row["threshold_value"] for row in rows}


def _build_summary(results: pd.DataFrame) -> dict:
    risk_counts = results["风险等级"].value_counts().to_dict()
    return {
        "物料总数": int(len(results)),
        "高风险数量": int(risk_counts.get("高", 0)),
        "中风险数量": int(risk_counts.get("中", 0)),
        "低风险数量": int(risk_counts.get("低", 0)),
    }


def save_risk_results(batch_id: int, results: pd.DataFrame, db_path: Path | str = DEFAULT_DB_PATH) -> int:
    rows = [
        (
            batch_id,
            row["物料编码"],
            row["物料名称"],
            row["风险等级"],
            row["推荐结论"],
            row["风险原因"],
            row["建议动作"],
        )
        for _, row in results.iterrows()
    ]

    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM risk_results WHERE batch_id = ?", (batch_id,))
        conn.executemany(
            """
            INSERT INTO risk_results (
                batch_id,
                material_code,
                material_name,
                risk_level,
                recommendation,
                risk_reasons,
                suggested_action
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    return len(rows)


def run_scoring_for_batch(
    batch_id: int,
    db_path: Path | str = DEFAULT_DB_PATH,
    operator: str | None = None,
) -> tuple[pd.DataFrame, dict]:
    bom_df = load_bom_items_for_batch(batch_id, db_path)
    supply_df = load_current_supply_data(db_path)
    rules = _load_rules(db_path)
    results = evaluate_risks(bom_df, supply_df, rules)
    save_risk_results(batch_id, results, db_path)
    summary = _build_summary(results)

    write_audit_log(
        operation_type="执行评分",
        operation_object=str(batch_id),
        operation_result="成功",
        operator=operator,
        message=f"成功评分{summary['物料总数']}条BOM明细",
        db_path=db_path,
    )
    return results, summary
