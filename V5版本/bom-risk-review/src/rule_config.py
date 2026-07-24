from pathlib import Path

from src.audit_log import write_audit_log
from src.database import DEFAULT_DB_PATH, get_connection


RULE_KEYS = [
    ("lead_time_medium_days", "交期中风险阈值", "天"),
    ("lead_time_high_days", "交期高风险阈值", "天"),
    ("price_increase_rate", "价格涨幅阈值", "比例"),
    ("inventory_drop_rate", "库存下降率阈值", "比例"),
]


def get_rules(db_path: Path | str = DEFAULT_DB_PATH) -> dict[str, float]:
    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT rule_key, threshold_value FROM risk_rules").fetchall()
    return {row["rule_key"]: row["threshold_value"] for row in rows}


def update_rule(
    rule_key: str,
    threshold_value: float,
    operator: str | None = None,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            """
            UPDATE risk_rules
            SET threshold_value = ?, updated_at = CURRENT_TIMESTAMP
            WHERE rule_key = ?
            """,
            (threshold_value, rule_key),
        )
        conn.commit()

    write_audit_log(
        operation_type="修改规则",
        operation_object=rule_key,
        operation_result="成功",
        operator=operator,
        message=f"将 {rule_key} 阈值更新为 {threshold_value}",
        db_path=db_path,
    )
