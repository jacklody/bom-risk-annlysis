"""BomItem 模型更新 — 新增供应链实时数据字段。

在现有 BomItem 基础上增加以下字段，用于存储 SupplyDataService
从 LCSC/Mouser 等 API 获取的实时交期/库存/价格数据。
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Enum as SAEnum
from app.database import Base
import enum


class RiskLevel(str, enum.Enum):
    RED = "red"
    ORANGE = "orange"
    YELLOW = "yellow"
    GREEN = "green"
    GRAY = "gray"


class BomProject(Base):
    """BOM项目"""
    __tablename__ = "bom_projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(256), nullable=False)
    project_name = Column(String(256), nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String(32), default="active")

    total_items = Column(Integer, default=0)
    items_analyzed = Column(Integer, default=0)
    items_red = Column(Integer, default=0)
    items_orange = Column(Integer, default=0)
    items_yellow = Column(Integer, default=0)
    items_green = Column(Integer, default=0)
    items_gray = Column(Integer, default=0)

    new_red_count = Column(Integer, default=0)
    new_orange_count = Column(Integer, default=0)
    new_yellow_count = Column(Integer, default=0)
    last_analysis_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    def to_summary(self):
        return {
            "id": self.id,
            "project_name": self.project_name or self.filename,
            "filename": self.filename,
            "status": self.status,
            "total_items": self.total_items,
            "items_red": self.items_red or 0,
            "items_orange": self.items_orange or 0,
            "items_yellow": self.items_yellow or 0,
            "items_green": self.items_green or 0,
            "items_gray": self.items_gray or 0,
            "new_red_count": self.new_red_count or 0,
            "new_orange_count": self.new_orange_count or 0,
            "new_yellow_count": self.new_yellow_count or 0,
            "has_new_risks": (self.new_red_count or 0) + (self.new_orange_count or 0) + (self.new_yellow_count or 0) > 0,
            "last_analysis_at": self.last_analysis_at.isoformat() if self.last_analysis_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class BomItem(Base):
    __tablename__ = "bom_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bom_upload_id = Column(Integer, nullable=False)

    row_number = Column(Integer, nullable=False)
    raw_part_number = Column(String(256), nullable=True)
    raw_description = Column(Text, nullable=True)
    raw_brand = Column(String(256), nullable=True)
    raw_category = Column(String(256), nullable=True)
    raw_spec = Column(String(512), nullable=True)
    raw_qty = Column(String(64), nullable=True)

    normalized_brand = Column(String(128), nullable=True)
    normalized_category = Column(String(128), nullable=True)
    normalized_category_path = Column(String(512), nullable=True)

    # 行情事件风险
    risk_level = Column(SAEnum(RiskLevel), default=RiskLevel.GRAY)
    risk_score = Column(Float, default=0.0)
    risk_reason = Column(Text, nullable=True)
    matched_event_ids = Column(String(512), nullable=True)

    # 供应链风险（v2 字段，保留）
    production_risk_level = Column(String(16), default="gray")
    production_risk_score = Column(Float, default=0.0)
    lead_time_risk_weeks = Column(Integer, nullable=True)
    eol_status = Column(String(32), default="none")
    supply_risk_tags = Column(String(512), nullable=True)
    supply_risk_reason = Column(Text, nullable=True)
    procurement_suggestion = Column(Text, nullable=True)

    # ============================================================
    # v3 新增：API 实时数据字段
    # ============================================================
    total_stock = Column(Integer, default=0)          # 各渠道库存汇总
    supplier_count = Column(Integer, default=0)       # 有现货的独立供应商数
    lead_time_days = Column(Integer, nullable=True)   # 工厂交期（天）
    unit_price = Column(Float, nullable=True)         # 最低单价
    lifecycle_status = Column(String(32), default="Unknown")  # Active/NRND/EOL/Obsolete
    supply_sources_summary = Column(Text, nullable=True)       # 多源供应证据摘要
    commonality_score = Column(Integer, default=50)   # 通用性评分 0-100

    last_risk_level = Column(String(16), nullable=True)
    risk_changed_at = Column(DateTime, nullable=True)
    risk_trigger_event_ids = Column(String(1024), nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
