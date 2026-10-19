from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.database import Base


class WatchCommand(Base):
    __tablename__ = "watch_commands"

    id = Column(Integer, primary_key=True, autoincrement=True)
    raw_input = Column(Text, nullable=False)
    parsed_brand = Column(String(128), nullable=True)
    parsed_category = Column(String(128), nullable=True)
    parsed_keywords = Column(Text, nullable=True)
    status = Column(String(32), default="pending")
    research_summary = Column(Text, nullable=True)
    research_detail = Column(Text, nullable=True)
    generated_event_ids = Column(String(1024), nullable=True)
    affected_project_count = Column(Integer, default=0)
    suggestion = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "raw_input": self.raw_input,
            "status": self.status,
            "research_summary": self.research_summary,
            "affected_project_count": self.affected_project_count or 0,
            "suggestion": self.suggestion,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
