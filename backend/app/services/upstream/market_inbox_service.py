"""行情情报收件箱服务。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.knowledge.brand_category_map import normalize_brand
from app.models.bom import BomItem, BomProject, RiskLevel
from app.models.event import ExtractedMarketSignal, MarketEvent, RawMarketNotice
from app.services.bom_matcher import BOMMatcher
from app.services.event_collector import EventCollector
from app.services.upstream.category_classifier import classify_component_category
from app.services.upstream.market_notice_parser import ParsedMarketSignal, parse_market_notice


@dataclass
class SubmitNoticePayload:
    title: str = ""
    raw_text: str = ""
    source_type: str = "manual"
    source_name: str = ""
    source_url: str = ""
    sender: str = ""
    auto_scan: bool = True


class MarketInboxService:
    def __init__(self, db: Session):
        self.db = db

    def submit_notice(self, payload: SubmitNoticePayload) -> dict[str, Any]:
        notice = RawMarketNotice(
            title=payload.title,
            raw_text=payload.raw_text,
            source_type=payload.source_type or "manual",
            source_name=payload.source_name,
            source_url=payload.source_url,
            sender=payload.sender,
            parse_status="pending",
        )
        self.db.add(notice)
        self.db.commit()
        self.db.refresh(notice)

        parsed = parse_market_notice(
            raw_text=payload.raw_text,
            title=payload.title,
            source_type=payload.source_type or "manual",
            source_name=payload.source_name or "",
        )

        signals: list[ExtractedMarketSignal] = []
        events_created = 0
        events_skipped = 0
        collector = EventCollector(self.db)

        for parsed_signal in parsed:
            signal = self._save_signal(notice.id, parsed_signal)
            if self._should_promote_to_event(parsed_signal):
                event = collector._save_event(self._event_payload(notice, parsed_signal))
                if event:
                    signal.market_event_id = event.id
                    events_created += 1
                else:
                    events_skipped += 1
            else:
                events_skipped += 1
            signals.append(signal)

        notice.parse_status = self._parse_status(signals)
        self.db.commit()
        self.db.refresh(notice)
        for signal in signals:
            self.db.refresh(signal)

        scan_summary = self._scan_history_boms() if payload.auto_scan and events_created else self._empty_scan_summary()

        return {
            "notice": notice.to_dict(),
            "signals": [signal.to_dict() for signal in signals],
            "events_created": events_created,
            "events_skipped": events_skipped,
            "scan_summary": scan_summary,
        }

    def list_notices(self) -> dict[str, Any]:
        notices = self.db.query(RawMarketNotice).order_by(RawMarketNotice.created_at.desc()).all()
        return {"total": len(notices), "notices": [notice.to_dict() for notice in notices]}

    def get_notice(self, notice_id: int) -> dict[str, Any] | None:
        notice = self.db.query(RawMarketNotice).filter(RawMarketNotice.id == notice_id).first()
        if not notice:
            return None
        signals = self.db.query(ExtractedMarketSignal).filter(
            ExtractedMarketSignal.raw_notice_id == notice_id
        ).all()
        return {"notice": notice.to_dict(), "signals": [signal.to_dict() for signal in signals]}

    def _save_signal(self, notice_id: int, parsed: ParsedMarketSignal) -> ExtractedMarketSignal:
        signal = ExtractedMarketSignal(
            raw_notice_id=notice_id,
            brand=parsed.brand,
            category=parsed.category,
            mpn=parsed.mpn,
            series=parsed.series,
            event_type=parsed.event_type,
            increase_min_pct=parsed.increase_min_pct,
            increase_max_pct=parsed.increase_max_pct,
            lead_time_weeks=parsed.lead_time_weeks,
            shortage_confirmed=1 if parsed.shortage_confirmed else 0,
            effective_date_text=parsed.effective_date_text,
            confidence=parsed.confidence,
            confidence_reason=parsed.confidence_reason,
            evidence_text=parsed.evidence_text,
            review_status=parsed.review_status,
        )
        self.db.add(signal)
        self.db.commit()
        self.db.refresh(signal)
        return signal

    def _should_promote_to_event(self, parsed: ParsedMarketSignal) -> bool:
        return parsed.review_status == "auto_confirmed" and parsed.confidence >= 0.8

    def _event_payload(self, notice: RawMarketNotice, parsed: ParsedMarketSignal) -> dict[str, Any]:
        severity = "high" if parsed.shortage_confirmed or (parsed.increase_max_pct or 0) >= 15 else "medium"
        return {
            "source_name": notice.source_name or notice.source_type or "market_inbox",
            "source_url": notice.source_url or f"market-inbox://notice/{notice.id}",
            "raw_text": notice.raw_text,
            "raw_title": notice.title,
            "brand": parsed.brand,
            "category": parsed.category,
            "event_type": parsed.event_type,
            "severity": severity,
            "confidence": parsed.confidence,
            "estimated_lead_time_impact_weeks": parsed.lead_time_weeks,
            "estimated_price_impact_pct": parsed.increase_max_pct,
        }

    def _parse_status(self, signals: list[ExtractedMarketSignal]) -> str:
        if not signals:
            return "failed"
        if any(signal.review_status == "need_review" for signal in signals):
            return "need_review"
        return "parsed"

    def _scan_history_boms(self) -> dict[str, Any]:
        projects = self.db.query(BomProject).filter(BomProject.status == "active").all()
        active_events = self.db.query(MarketEvent).filter(MarketEvent.is_active == 1).all()
        matcher = BOMMatcher(active_events)
        affected_projects = 0
        red_count = 0
        yellow_count = 0
        top_impacted_items: list[dict[str, Any]] = []

        for project in projects:
            items = self.db.query(BomItem).filter(BomItem.bom_upload_id == project.id).all()
            impacted_count = 0
            for item in items:
                level, score, events, reason = matcher.match_item(item)
                events = self._merge_v33_category_events(item, events, active_events)
                if events and level.value == "green":
                    level, score, reason = self._risk_from_events(events, item)
                if not events:
                    continue
                impacted_count += 1
                if level.value == "red":
                    red_count += 1
                elif level.value in {"yellow", "orange"}:
                    yellow_count += 1
                item.risk_level = level
                item.risk_score = score
                item.risk_reason = reason
                item.matched_event_ids = ",".join(str(event.id) for event in events)
                top_impacted_items.append({
                    "project_id": project.id,
                    "project_name": project.project_name or project.filename,
                    "mpn": item.raw_part_number,
                    "brand": item.normalized_brand or item.raw_brand,
                    "risk_level": level.value,
                    "reason": reason,
                })
            if impacted_count:
                affected_projects += 1
        self.db.commit()

        return {
            "projects_scanned": len(projects),
            "affected_projects": affected_projects,
            "new_red_count": red_count,
            "new_yellow_count": yellow_count,
            "top_impacted_items": top_impacted_items[:20],
        }

    def _risk_from_events(self, events: list[MarketEvent], item: BomItem) -> tuple[RiskLevel, float, str]:
        strongest = max(events, key=lambda event: (event.confidence or 0) * (1.2 if (event.estimated_price_impact_pct or 0) >= 10 else 1.0))
        impact = strongest.estimated_price_impact_pct or 0
        confidence = strongest.confidence or 0.5
        severity = strongest.severity.value if hasattr(strongest.severity, "value") else str(strongest.severity or "")
        if impact >= 15 or severity in {"high", "critical"}:
            level = RiskLevel.RED
            base = 80.0
        else:
            level = RiskLevel.YELLOW
            base = 65.0
        score = min(100.0, base * max(confidence, 0.6))
        category = self._classify_item_v33_category(item)
        reason = (
            f"品牌/品类补充命中: {strongest.brand or '未指定品牌'} {strongest.category or category} "
            f"受{strongest.event_type.value if strongest.event_type else '行情'}事件影响"
        )
        if impact:
            reason += f"，预计价格影响{impact:g}%"
        return level, score, reason

    def _merge_v33_category_events(self, item: BomItem, events: list[MarketEvent], active_events: list[MarketEvent]) -> list[MarketEvent]:
        merged = list(events or [])
        existing_ids = {event.id for event in merged if event.id is not None}
        item_category = self._classify_item_v33_category(item)
        for event in active_events:
            if event.id in existing_ids:
                continue
            event_category = (event.category or "").strip().lower()
            if event_category and event_category == item_category and self._event_brand_matches_item(item, event):
                merged.append(event)
                if event.id is not None:
                    existing_ids.add(event.id)
        return merged

    def _classify_item_v33_category(self, item: BomItem) -> str:
        description = " ".join(str(value or "") for value in [item.normalized_category, item.raw_spec, item.raw_category, item.raw_part_number])
        manufacturer = item.normalized_brand or item.raw_brand or ""
        return classify_component_category(description, manufacturer=manufacturer).category.lower()

    def _event_brand_matches_item(self, item: BomItem, event: MarketEvent) -> bool:
        event_brand = (event.brand or "").strip()
        if not event_brand:
            return True
        event_brand_norm = normalize_brand(event_brand) or event_brand
        item_brand_text = " ".join(str(value or "") for value in [item.normalized_brand, item.raw_brand]).lower()
        item_brand_norm = normalize_brand(item.normalized_brand or "") or normalize_brand(item.raw_brand or "") or ""
        return (
            event_brand.lower() in item_brand_text
            or event_brand_norm.lower() in item_brand_text
            or (item_brand_norm and item_brand_norm.lower() == event_brand_norm.lower())
        )

    def review_signal(self, signal_id: int, action: str, notes: str = "", reviewer: str = "") -> dict[str, Any]:
        signal = self.db.query(ExtractedMarketSignal).filter(ExtractedMarketSignal.id == signal_id).first()
        if not signal:
            return {"error": "Signal not found"}
        if signal.review_status not in {"need_review", "observation"}:
            return {"error": f"Signal already finalized with status {signal.review_status}"}

        signal.reviewed_by = reviewer or "purchaser"
        signal.review_notes = notes

        event_created = False
        scan_summary = self._empty_scan_summary()

        if action == "confirm":
            signal.review_status = "confirmed"
            signal.confidence = max(signal.confidence, 0.80)
            collector = EventCollector(self.db)
            notice = self.db.query(RawMarketNotice).filter(RawMarketNotice.id == signal.raw_notice_id).first()
            severity = "high" if signal.shortage_confirmed or (signal.increase_max_pct or 0) >= 15 else "medium"
            payload = {
                "source_name": notice.source_name if notice else "market_inbox_review",
                "source_url": notice.source_url if notice else f"market-inbox://review/{signal_id}",
                "raw_text": notice.raw_text if notice else "",
                "raw_title": notice.title if notice else "",
                "brand": signal.brand,
                "category": signal.category,
                "event_type": signal.event_type or "other",
                "severity": severity,
                "confidence": signal.confidence,
                "estimated_lead_time_impact_weeks": signal.lead_time_weeks,
                "estimated_price_impact_pct": signal.increase_max_pct,
            }
            event = collector._save_event(payload)
            if event:
                signal.market_event_id = event.id
                event_created = True
                scan_summary = self._scan_history_boms()
        elif action == "reject":
            signal.review_status = "rejected"
        elif action == "observe":
            signal.review_status = "observation"
        else:
            return {"error": f"Unknown action: {action}"}

        self.db.commit()
        self.db.refresh(signal)
        return {
            "signal": signal.to_dict(),
            "event_created": event_created,
            "scan_summary": scan_summary,
        }

    def list_review_queue(self, status: str | None = None) -> dict[str, Any]:
        q = self.db.query(ExtractedMarketSignal)
        if status:
            q = q.filter(ExtractedMarketSignal.review_status == status)
        else:
            q = q.filter(ExtractedMarketSignal.review_status.in_(["need_review", "observation"]))
        signals = q.order_by(ExtractedMarketSignal.confidence.desc()).all()
        summary = self._review_status_summary()
        return {
            "total": len(signals),
            "summary": summary,
            "signals": [self._signal_with_notice_context(s) for s in signals],
        }

    def _review_status_summary(self) -> dict[str, int]:
        statuses = ["need_review", "observation", "confirmed", "rejected"]
        summary = {status: 0 for status in statuses}
        rows = self.db.query(ExtractedMarketSignal.review_status).all()
        for row in rows:
            status = row[0]
            if status in summary:
                summary[status] += 1
        summary["queue_total"] = summary["need_review"] + summary["observation"]
        return summary

    def _signal_with_notice_context(self, signal: ExtractedMarketSignal) -> dict[str, Any]:
        payload = signal.to_dict()
        notice = self.db.query(RawMarketNotice).filter(RawMarketNotice.id == signal.raw_notice_id).first()
        if notice:
            payload.update({
                "raw_notice_title": notice.title,
                "raw_notice_source_type": notice.source_type,
                "raw_notice_source_name": notice.source_name,
                "raw_notice_sender": notice.sender,
                "raw_notice_excerpt": (notice.raw_text or "")[:300],
            })
        return payload

    def _empty_scan_summary(self) -> dict[str, Any]:
        return {
            "projects_scanned": 0,
            "affected_projects": 0,
            "new_red_count": 0,
            "new_yellow_count": 0,
            "top_impacted_items": [],
        }
