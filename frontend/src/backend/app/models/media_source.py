from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, Float
from app.database import Base


class MediaSourceRun(Base):
    """媒体源单次采集运行记录。"""

    __tablename__ = "media_source_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(String(128), nullable=False, index=True)
    status = Column(String(32), default="running")  # running / success / empty / failed
    articles_crawled = Column(Integer, default=0)
    signals_parsed = Column(Integer, default=0)
    events_created = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "source_id": self.source_id,
            "status": self.status,
            "articles_crawled": self.articles_crawled,
            "signals_parsed": self.signals_parsed,
            "events_created": self.events_created,
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
