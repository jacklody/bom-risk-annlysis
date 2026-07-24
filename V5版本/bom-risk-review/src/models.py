CREATE_TABLES_SQL = [
    """
    CREATE TABLE IF NOT EXISTS import_batches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_type TEXT NOT NULL,
        file_name TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        row_count INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT '成功',
        message TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS bom_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id INTEGER NOT NULL,
        bom_version TEXT,
        material_code TEXT NOT NULL,
        material_name TEXT NOT NULL,
        specification TEXT,
        quantity REAL NOT NULL,
        is_virtual TEXT,
        alternative_group TEXT,
        is_common TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (batch_id) REFERENCES import_batches(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS supply_risk_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        material_code TEXT NOT NULL,
        supplier_count INTEGER NOT NULL,
        primary_supplier TEXT,
        lead_time_days REAL NOT NULL,
        current_inventory REAL NOT NULL,
        inventory_drop_rate REAL NOT NULL,
        current_price REAL NOT NULL,
        historical_price REAL NOT NULL,
        is_discontinued TEXT NOT NULL,
        has_alternative TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS risk_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id INTEGER NOT NULL,
        material_code TEXT NOT NULL,
        material_name TEXT,
        risk_level TEXT NOT NULL,
        recommendation TEXT NOT NULL,
        risk_reasons TEXT NOT NULL,
        suggested_action TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (batch_id) REFERENCES import_batches(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS risk_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rule_key TEXT NOT NULL UNIQUE,
        rule_name TEXT NOT NULL,
        threshold_value REAL NOT NULL,
        unit TEXT,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        operation_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        operation_type TEXT NOT NULL,
        operation_object TEXT,
        operation_result TEXT NOT NULL,
        operator TEXT,
        message TEXT
    )
    """,
]

DEFAULT_RULES = [
    ("lead_time_medium_days", "交期中风险阈值", 30, "天"),
    ("lead_time_high_days", "交期高风险阈值", 60, "天"),
    ("price_increase_rate", "价格涨幅阈值", 0.2, "比例"),
    ("inventory_drop_rate", "库存下降率阈值", 0.3, "比例"),
]
