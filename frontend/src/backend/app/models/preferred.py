from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from app.database import Base
import json


class PreferredPart(Base):
    __tablename__ = "preferred_parts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_file = Column(String(512), nullable=True)
    source_sheet = Column(String(256), nullable=True)
    source_row = Column(Integer, nullable=True)
    category_level_2 = Column(String(128), nullable=True)
    category_level_3 = Column(String(128), nullable=True)
    brand = Column(String(128), nullable=True)
    normalized_brand = Column(String(128), nullable=True)
    name = Column(String(256), nullable=True)
    part_number = Column(String(128), nullable=True)
    mpn = Column(String(256), nullable=True)
    normalized_mpn = Column(String(256), nullable=True)
    manufacturer_mpn = Column(String(256), nullable=True)
    package = Column(String(128), nullable=True)
    mounting_type = Column(String(128), nullable=True)
    size = Column(String(128), nullable=True)
    spec_text = Column(Text, nullable=True)
    key_params_json = Column(Text, nullable=True)
    application_scenarios = Column(Text, nullable=True)
    preferred_level = Column(String(64), default="unknown")
    control_status = Column(String(64), default="unknown")
    cost = Column(Float, nullable=True)
    cost_unit = Column(String(64), nullable=True)
    recommendation_reason = Column(Text, nullable=True)
    raw_row_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "source_file": self.source_file,
            "source_sheet": self.source_sheet,
            "source_row": self.source_row,
            "category_level_2": self.category_level_2,
            "category_level_3": self.category_level_3,
            "brand": self.brand,
            "normalized_brand": self.normalized_brand,
            "name": self.name,
            "part_number": self.part_number,
            "mpn": self.mpn,
            "normalized_mpn": self.normalized_mpn,
            "manufacturer_mpn": self.manufacturer_mpn,
            "package": self.package,
            "mounting_type": self.mounting_type,
            "size": self.size,
            "spec_text": self.spec_text,
            "application_scenarios": self.application_scenarios,
            "preferred_level": self.preferred_level,
            "control_status": self.control_status,
            "cost": self.cost,
            "cost_unit": self.cost_unit,
            "recommendation_reason": self.recommendation_reason,
        }


class HistoricalPartIndex(Base):
    __tablename__ = "historical_part_indexes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    normalized_brand = Column(String(128), nullable=True)
    normalized_mpn = Column(String(256), nullable=True)
    normalized_category = Column(String(128), nullable=True)
    first_seen_at = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    project_count = Column(Integer, default=0)
    usage_count = Column(Integer, default=0)
    latest_project_names_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class BomSelectionReview(Base):
    __tablename__ = "bom_selection_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bom_project_id = Column(Integer, nullable=False)
    bom_item_id = Column(Integer, ForeignKey("bom_items.id"), nullable=False)
    preferred_part_id = Column(Integer, ForeignKey("preferred_parts.id"), nullable=True)
    match_status = Column(String(64), default="not_found")
    match_score = Column(Float, default=0.0)
    preferred_level = Column(String(64), default="unknown")
    control_status = Column(String(64), default="unknown")
    is_new_part = Column(Integer, default=0)
    history_usage_count = Column(Integer, default=0)
    history_project_count = Column(Integer, default=0)
    delivery_control_status = Column(String(64), default="normal")
    delivery_control_reason = Column(Text, nullable=True)
    selection_risk_level = Column(String(32), default="info")
    selection_reason = Column(Text, nullable=True)
    selection_action = Column(Text, nullable=True)
    recommended_alternatives_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "bom_project_id": self.bom_project_id,
            "bom_item_id": self.bom_item_id,
            "preferred_part_id": self.preferred_part_id,
            "match_status": self.match_status,
            "match_score": self.match_score,
            "preferred_level": self.preferred_level,
            "control_status": self.control_status,
            "is_new_part": bool(self.is_new_part),
            "history_usage_count": self.history_usage_count or 0,
            "history_project_count": self.history_project_count or 0,
            "delivery_control_status": self.delivery_control_status,
            "delivery_control_reason": self.delivery_control_reason,
            "selection_risk_level": self.selection_risk_level,
            "selection_reason": self.selection_reason,
            "selection_action": self.selection_action,
            "recommended_alternatives": self._recommended_alternatives(),
        }

    def _recommended_alternatives(self) -> list[dict]:
        raw = self.recommended_alternatives_json
        if not raw or not raw.strip():
            return []
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
