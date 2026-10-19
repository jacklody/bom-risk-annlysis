from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Enum as SAEnum, ForeignKey
from app.database import Base
import enum


class EventType(str, enum.Enum):
    SHORTAGE = "shortage"
    PRICE_INCREASE = "price_increase"
    CAPACITY_ISSUE = "capacity_issue"
    LEAD_TIME = "lead_time"
    EOL = "eol"
    POLICY = "policy"
    DISASTER = "disaster"
    MATERIAL_PRICE = "material_price"
    OTHER = "other"


class Severity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class MarketEvent(Base):
    __tablename__ = "market_events"

    id = Column(Integer, primary_key=True, autoincrement=True)

    source_url = Column(String(1024), nullable=True)
    source_name = Column(String(256), nullable=False)
    source_published_at = Column(DateTime, nullable=True)
    raw_text = Column(Text, nullable=False)
    raw_title = Column(String(512), nullable=True)

    brand = Column(String(128), nullable=True)
    category = Column(String(128), nullable=True)
    category_level = Column(Integer, default=1)

    event_type = Column(SAEnum(EventType), default=EventType.OTHER)
    severity = Column(SAEnum(Severity), default=Severity.UNKNOWN)

    estimated_lead_time_impact_weeks = Column(Integer, nullable=True)
    estimated_price_impact_pct = Column(Float, nullable=True)

    duration_start = Column(DateTime, nullable=True)
    duration_end = Column(DateTime, nullable=True)

    confidence = Column(Float, default=0.0)
    cross_validated = Column(Integer, default=0)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
    is_active = Column(Integer, default=1)

    def to_dict(self):
        return {
            "id": self.id,
            "brand": self.brand,
            "category": self.category,
            "event_type": self.event_type.value if self.event_type else None,
            "severity": self.severity.value if self.severity else None,
            "confidence": self.confidence,
            "cross_validated": self.cross_validated,
            "source_name": self.source_name,
            "source_url": self.source_url,
            "raw_title": self.raw_title,
            "raw_text_excerpt": (self.raw_text or "")[:240],
            "estimated_lead_time_impact_weeks": self.estimated_lead_time_impact_weeks,
            "estimated_price_impact_pct": self.estimated_price_impact_pct,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "is_active": self.is_active,
        }


class RawMarketNotice(Base):
    __tablename__ = "raw_market_notices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_type = Column(String(64), default="manual")
    source_name = Column(String(256), nullable=True)
    source_url = Column(String(1024), nullable=True)
    received_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    title = Column(String(512), nullable=True)
    raw_text = Column(Text, nullable=False)
    raw_file_name = Column(String(512), nullable=True)
    raw_file_hash = Column(String(128), nullable=True)
    sender = Column(String(256), nullable=True)
    parse_status = Column(String(32), default="pending")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "source_type": self.source_type,
            "source_name": self.source_name,
            "source_url": self.source_url,
            "received_at": self.received_at.isoformat() if self.received_at else None,
            "title": self.title,
            "raw_text_excerpt": (self.raw_text or "")[:300],
            "raw_file_name": self.raw_file_name,
            "raw_file_hash": self.raw_file_hash,
            "sender": self.sender,
            "parse_status": self.parse_status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class PredictionValidationRecord(Base):
    __tablename__ = "prediction_validation_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey("market_events.id"), nullable=False)
    validation_status = Column(String(32), nullable=False)
    outcome = Column(String(32), nullable=False)
    reviewer = Column(String(128), nullable=True)
    notes = Column(Text, nullable=True)
    affected_project_count = Column(Integer, default=0)
    affected_item_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "event_id": self.event_id,
            "validation_status": self.validation_status,
            "outcome": self.outcome,
            "reviewer": self.reviewer,
            "notes": self.notes,
            "affected_project_count": self.affected_project_count,
            "affected_item_count": self.affected_item_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ExtractedMarketSignal(Base):
    __tablename__ = "extracted_market_signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    raw_notice_id = Column(Integer, ForeignKey("raw_market_notices.id"), nullable=False)
    market_event_id = Column(Integer, ForeignKey("market_events.id"), nullable=True)
    brand = Column(String(128), nullable=True)
    category = Column(String(128), nullable=True)
    mpn = Column(String(128), nullable=True)
    series = Column(String(128), nullable=True)
    event_type = Column(String(64), default="other")
    increase_min_pct = Column(Float, nullable=True)
    increase_max_pct = Column(Float, nullable=True)
    lead_time_weeks = Column(Integer, nullable=True)
    shortage_confirmed = Column(Integer, default=0)
    effective_date_text = Column(String(128), nullable=True)
    confidence = Column(Float, default=0.0)
    confidence_reason = Column(Text, nullable=True)
    evidence_text = Column(Text, nullable=True)
    review_status = Column(String(32), default="observation")
    reviewed_by = Column(String(128), nullable=True)
    review_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "raw_notice_id": self.raw_notice_id,
            "market_event_id": self.market_event_id,
            "brand": self.brand,
            "category": self.category,
            "mpn": self.mpn,
            "series": self.series,
            "event_type": self.event_type,
            "increase_min_pct": self.increase_min_pct,
            "increase_max_pct": self.increase_max_pct,
            "lead_time_weeks": self.lead_time_weeks,
            "shortage_confirmed": bool(self.shortage_confirmed),
            "effective_date_text": self.effective_date_text,
            "confidence": self.confidence,
            "confidence_reason": self.confidence_reason,
            "evidence_text": self.evidence_text,
            "review_status": self.review_status,
            "reviewed_by": self.reviewed_by,
            "review_notes": self.review_notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
