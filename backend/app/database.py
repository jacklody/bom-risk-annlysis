from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app.models import bom  # noqa: F401
    from app.models import dashboard_notification  # noqa: F401
    from app.models import event  # noqa: F401
    from app.models import watch  # noqa: F401
    from app.models import preferred  # noqa: F401
    from app.models import media_source  # noqa: F401
    from app.models import material_price  # noqa: F401  — v3.4

    Base.metadata.create_all(bind=engine)
    _ensure_migration_tracking()


def _ensure_migration_tracking():
    """v3.3: 创建 app_config 表用于迁移版本追踪。"""
    inspector = inspect(engine)
    if "app_config" not in inspector.get_table_names():
        from sqlalchemy import Column, Integer, String
        from app.database import Base as DBBase
        # 内联定义简单配置表
        class _AppConfig(DBBase):
            __tablename__ = "app_config"
            id = Column(Integer, primary_key=True, autoincrement=True)
            key = Column(String(128), unique=True, nullable=False)
            value = Column(String(1024), default="")
        _AppConfig.__table__.create(bind=engine)

    # 检查已执行的迁移，跳过已完成项
    with engine.begin() as conn:
        try:
            existing_keys = {row[0] for row in conn.execute(
                text("SELECT key FROM app_config WHERE key LIKE 'migration:%'")
            ).fetchall()}
        except Exception:
            existing_keys = set()

        for mig_key, mig_func in _MIGRATION_KEYS.items():
            full_key = f"migration:{mig_key}"
            if full_key in existing_keys:
                continue  # 已执行，跳过
            try:
                mig_func()
                conn.execute(
                    text("INSERT OR REPLACE INTO app_config (key, value) VALUES (:k, :v)"),
                    {"k": full_key, "v": "1"}
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(
                    f"迁移 {mig_key} 失败: {e}"
                )


def _migrate_bom_item_supply_columns():
    """轻量迁移：兼容已有SQLite库，补齐供应链风险字段（v2→v3）。"""
    inspector = inspect(engine)
    if "bom_items" not in inspector.get_table_names():
        return

    existing = {col["name"] for col in inspector.get_columns("bom_items")}

    # v2 字段
    v2_columns = {
        "production_risk_level": "VARCHAR(16) DEFAULT 'gray'",
        "production_risk_score": "FLOAT DEFAULT 0",
        "lead_time_risk_weeks": "INTEGER",
        "eol_status": "VARCHAR(32) DEFAULT 'none'",
        "supply_risk_tags": "VARCHAR(512)",
        "supply_risk_reason": "TEXT",
        "procurement_suggestion": "TEXT",
    }

    # v3 新增：API 实时数据字段
    v3_columns = {
        "total_stock": "INTEGER DEFAULT 0",
        "supplier_count": "INTEGER DEFAULT 0",
        "lead_time_days": "INTEGER",
        "unit_price": "FLOAT",
        "lifecycle_status": "VARCHAR(32) DEFAULT 'Unknown'",
        "supply_sources_summary": "TEXT",
        "commonality_score": "INTEGER DEFAULT 50",
    }

    all_columns = {**v2_columns, **v3_columns}

    with engine.begin() as conn:
        for name, ddl in all_columns.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE bom_items ADD COLUMN {name} {ddl}"))


def _migrate_extracted_market_signals():
    inspector = inspect(engine)
    if "extracted_market_signals" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("extracted_market_signals")}
    new_columns = {
        "reviewed_by": "VARCHAR(128)",
        "review_notes": "TEXT",
    }
    with engine.begin() as conn:
        for name, ddl in new_columns.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE extracted_market_signals ADD COLUMN {name} {ddl}"))


def _migrate_dashboard_notification_records():
    inspector = inspect(engine)
    if "dashboard_notification_records" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("dashboard_notification_records")}
    new_columns = {
        "provider": "VARCHAR(64)",
        "recipient_summary": "VARCHAR(512)",
        "failure_reason": "TEXT",
        "retry_count": "INTEGER DEFAULT 0",
        "last_attempt_at": "DATETIME",
        "delivered_at": "DATETIME",
    }
    with engine.begin() as conn:
        for name, ddl in new_columns.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE dashboard_notification_records ADD COLUMN {name} {ddl}"))


def _migrate_bom_project_orange_columns():
    """迁移：为 bom_projects 添加 orange 风险等级列。"""
    inspector = inspect(engine)
    if "bom_projects" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("bom_projects")}
    new_columns = {
        "items_orange": "INTEGER DEFAULT 0",
        "new_orange_count": "INTEGER DEFAULT 0",
    }
    with engine.begin() as conn:
        for name, ddl in new_columns.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE bom_projects ADD COLUMN {name} {ddl}"))


def _migrate_material_prices_v3_4():
    """v3.4: 创建 material_prices 表（若尚未通过 ORM 创建）。"""
    inspector = inspect(engine)
    if "material_prices" not in inspector.get_table_names():
        from app.models.material_price import MaterialPrice
        MaterialPrice.__table__.create(bind=engine)


# ── v3.3: 迁移注册表（必须在所有函数定义之后） ──
_MIGRATION_KEYS = {
    "bom_item_supply_v2v3": _migrate_bom_item_supply_columns,
    "extracted_market_signals_review": _migrate_extracted_market_signals,
    "dashboard_notification_provider": _migrate_dashboard_notification_records,
    "bom_project_orange": _migrate_bom_project_orange_columns,
    "material_prices_v3_4": _migrate_material_prices_v3_4,
}