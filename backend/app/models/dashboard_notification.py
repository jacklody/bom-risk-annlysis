from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database import Base


class DashboardNotificationRecord(Base):
    __tablename__ = "dashboard_notification_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel = Column(String(64), default="manual", nullable=False)
    status = Column(String(32), default="prepared", nullable=False)
    idempotency_key = Column(String(256), nullable=True, index=True)
    subject = Column(String(512), nullable=False)
    body = Column(Text, nullable=False)
    preview_json = Column(Text, nullable=False)
    delivered = Column(Integer, default=0, nullable=False)
    external_delivery = Column(Integer, default=0, nullable=False)
    provider = Column(String(64), nullable=True)
    recipient_summary = Column(String(512), nullable=True)
    failure_reason = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    last_attempt_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "channel": self.channel,
            "status": self.status,
            "idempotency_key": self.idempotency_key,
            "subject": self.subject,
            "body": self.body,
            "delivered": bool(self.delivered),
            "external_delivery": bool(self.external_delivery),
            "provider": self.provider,
            "recipient_summary": self.recipient_summary,
            "failure_reason": self.failure_reason,
            "retry_count": self.retry_count or 0,
            "last_attempt_at": self.last_attempt_at.isoformat() if self.last_attempt_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "message": self.message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
