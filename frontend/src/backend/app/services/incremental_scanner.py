"""增量风险扫描服务"""

from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.event import MarketEvent
from app.models.bom import BomItem, BomProject
from app.services.bom_matcher import BOMMatcher


class IncrementalScanner:

    def __init__(self, db: Session):
        self.db = db

    def scan_all_projects(self) -> dict:
        active_events = (
            self.db.query(MarketEvent)
            .filter(MarketEvent.is_active == 1)
            .all()
        )
        matcher = BOMMatcher(active_events)
        projects = (
            self.db.query(BomProject)
            .filter(BomProject.status == "active")
            .all()
        )
        summary = {"scanned": len(projects), "projects_with_changes": 0}
        for project in projects:
            changed = self._scan_project(project, matcher)
            if changed:
                summary["projects_with_changes"] += 1
        self.db.commit()
        return summary

    def _scan_project(self, project: BomProject, matcher: BOMMatcher) -> bool:
        items = (
            self.db.query(BomItem)
            .filter(BomItem.bom_upload_id == project.id)
            .all()
        )
        has_changes = False
        new_red = 0
        new_orange = 0
        new_yellow = 0
        for item in items:
            last_risk = item.last_risk_level or "gray"
            level, score, events, reason = matcher.match_item(item)
            item.risk_level = level
            item.risk_score = score
            item.risk_reason = reason
            item.matched_event_ids = ",".join(str(e.id) for e in events)
            new_level = level.value
            if new_level != last_risk and self._is_worse(new_level, last_risk):
                has_changes = True
                item.risk_changed_at = datetime.now(timezone.utc)
                item.risk_trigger_event_ids = item.matched_event_ids
                if new_level == "red":
                    new_red += 1
                elif new_level == "orange":
                    new_orange += 1
                elif new_level == "yellow":
                    new_yellow += 1
            item.last_risk_level = new_level
        project.new_red_count = new_red
        project.new_orange_count = new_orange
        project.new_yellow_count = new_yellow
        project.items_analyzed = len(items)
        project.items_red = sum(1 for i in items if i.risk_level and i.risk_level.value == "red")
        project.items_orange = sum(1 for i in items if i.risk_level and i.risk_level.value == "orange")
        project.items_yellow = sum(1 for i in items if i.risk_level and i.risk_level.value == "yellow")
        project.items_green = sum(1 for i in items if i.risk_level and i.risk_level.value == "green")
        project.items_gray = sum(1 for i in items if i.risk_level and i.risk_level.value == "gray")
        project.last_analysis_at = datetime.now(timezone.utc)
        return has_changes

    @staticmethod
    def _is_worse(new_level: str, old_level: str) -> bool:
        order = {"gray": 0, "green": 1, "yellow": 2, "orange": 3, "red": 4}
        return order.get(new_level, 0) > order.get(old_level, 0)
