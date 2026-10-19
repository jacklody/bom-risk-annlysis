from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.bom import BomItem, BomProject
from app.models.event import ExtractedMarketSignal, MarketEvent, PredictionValidationRecord, Severity

router = APIRouter()

PRIORITY_ORDER = {"high": 3, "medium": 2, "low": 1}
VALIDATION_OUTCOMES = {"confirmed_hit", "false_positive", "watching", "dismissed"}


class PredictionValidationRecordCreate(BaseModel):
    outcome: str
    reviewer: str | None = None
    notes: str | None = None


def _now():
    return datetime.now(timezone.utc)


def _as_aware(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _csv_id_set(csv_text: str | None) -> set[int]:
    ids: set[int] = set()
    if not csv_text:
        return ids
    for part in csv_text.split(","):
        token = part.strip()
        if not token:
            continue
        try:
            ids.add(int(token))
        except ValueError:
            continue
    return ids


def _csv_contains_id(csv_text: str | None, target_id: int) -> bool:
    return target_id in _csv_id_set(csv_text)


def _risk_value(item: BomItem) -> str:
    if not item.risk_level:
        return "gray"
    return item.risk_level.value if hasattr(item.risk_level, "value") else str(item.risk_level)


def _severity_value(event: MarketEvent) -> str:
    return event.severity.value if event.severity else "unknown"


def _event_title(event: MarketEvent) -> str:
    if event.raw_title and event.raw_title.strip():
        return event.raw_title.strip()
    brand = (event.brand or "未知品牌").strip()
    category = (event.category or "未知品类").strip()
    event_type = event.event_type.value if event.event_type else "other"
    return f"{brand} {category} {event_type}"


def _validation_trigger_reason(event: MarketEvent, impact: dict) -> str:
    severity = _severity_value(event)
    confidence = round((event.confidence or 0) * 100)
    return f"严重度 {severity}，置信度 {confidence}%，命中 {impact['project_count']} 个项目 {impact['item_count']} 个物料"


def _empty_impact() -> dict:
    return {
        "project_ids": [],
        "project_count": 0,
        "item_count": 0,
        "risk_counts": {"red": 0, "yellow": 0, "green": 0, "gray": 0},
        "items": [],
    }


def _unique_items(impacts: list[dict]) -> list[BomItem]:
    items_by_id: dict[int, BomItem] = {}
    for impact in impacts:
        for item in impact["items"]:
            if item.id is not None:
                items_by_id[item.id] = item
    return list(items_by_id.values())


def _risk_counts_for_items(items: list[BomItem]) -> dict[str, int]:
    risk_counts = {"red": 0, "yellow": 0, "green": 0, "gray": 0}
    for item in items:
        level = _risk_value(item)
        if level not in risk_counts:
            level = "gray"
        risk_counts[level] += 1
    return risk_counts


def _active_events(db: Session):
    return db.query(MarketEvent).filter(MarketEvent.is_active == 1).order_by(MarketEvent.id).all()


def _build_impact_map(db: Session, event_ids: list[int]) -> dict[int, dict]:
    impact_map = {event_id: _empty_impact() for event_id in event_ids}
    event_id_set = set(event_ids)
    if not event_id_set:
        return impact_map

    items = db.query(BomItem).filter(BomItem.matched_event_ids.isnot(None)).all()
    project_sets = {event_id: set() for event_id in event_ids}

    for item in items:
        for event_id in _csv_id_set(item.matched_event_ids) & event_id_set:
            impact = impact_map[event_id]
            impact["items"].append(item)
            impact["item_count"] += 1
            project_sets[event_id].add(item.bom_upload_id)
            level = _risk_value(item)
            if level not in impact["risk_counts"]:
                level = "gray"
            impact["risk_counts"][level] += 1

    for event_id, project_ids in project_sets.items():
        impact_map[event_id]["project_ids"] = sorted(project_ids)
        impact_map[event_id]["project_count"] = len(project_ids)
    return impact_map


def _event_impact(db: Session, event_id: int, impact_map: dict[int, dict] | None = None) -> dict:
    if impact_map is not None:
        return impact_map.get(event_id, _empty_impact())
    return _build_impact_map(db, [event_id]).get(event_id, _empty_impact())


def _trace_payload(event_ids: list[int], project_ids: list[int] | None = None, item_ids: list[int] | None = None) -> dict:
    event_ids = sorted({event_id for event_id in event_ids if event_id is not None})
    project_ids = sorted({project_id for project_id in (project_ids or []) if project_id is not None})
    item_ids = sorted({item_id for item_id in (item_ids or []) if item_id is not None})
    target_query = {}
    if event_ids:
        target_query["event_ids"] = ",".join(str(event_id) for event_id in event_ids)
    if project_ids:
        target_query["project_ids"] = ",".join(str(project_id) for project_id in project_ids)
    if item_ids:
        target_query["item_ids"] = ",".join(str(item_id) for item_id in item_ids)
    return {
        "event_ids": event_ids,
        "project_ids": project_ids,
        "item_ids": item_ids,
        "target_query": target_query,
    }


def _impact_item_ids(impact: dict) -> list[int]:
    return [item.id for item in impact["items"] if item.id is not None]


def _reviewed_event_ids(db: Session, event_ids: list[int]) -> set[int]:
    if not event_ids:
        return set()
    rows = (
        db.query(ExtractedMarketSignal.market_event_id)
        .filter(ExtractedMarketSignal.market_event_id.in_(event_ids))
        .all()
    )
    return {row[0] for row in rows if row[0] is not None}


def _latest_validation_records(db: Session, event_ids: list[int]) -> dict[int, PredictionValidationRecord]:
    if not event_ids:
        return {}
    rows = (
        db.query(PredictionValidationRecord)
        .filter(PredictionValidationRecord.event_id.in_(event_ids))
        .order_by(PredictionValidationRecord.created_at.desc(), PredictionValidationRecord.id.desc())
        .all()
    )
    latest: dict[int, PredictionValidationRecord] = {}
    for row in rows:
        if row.event_id not in latest:
            latest[row.event_id] = row
    return latest


def _has_review_source(db: Session, event_id: int, reviewed_ids: set[int] | None = None) -> bool:
    if reviewed_ids is not None:
        return event_id in reviewed_ids
    return (
        db.query(ExtractedMarketSignal)
        .filter(ExtractedMarketSignal.market_event_id == event_id)
        .first()
        is not None
    )


def _is_high_severity(event: MarketEvent) -> bool:
    return event.severity in {Severity.CRITICAL, Severity.HIGH}


def _validation_status(
    db: Session,
    event: MarketEvent,
    impact: dict,
    reviewed_ids: set[int] | None = None,
) -> str:
    has_review = _has_review_source(db, event.id, reviewed_ids)
    has_red_or_yellow = impact["risk_counts"]["red"] > 0 or impact["risk_counts"]["yellow"] > 0
    if _is_high_severity(event) and ((event.confidence or 0) < 0.75 or not has_review):
        return "needs_review"
    if impact["item_count"] > 0 and has_red_or_yellow:
        return "risk_hit"
    return "not_hit_yet"


def _build_actions(db: Session, events: list[MarketEvent] | None = None) -> list[dict]:
    events = events if events is not None else _active_events(db)
    event_ids = [event.id for event in events]
    impact_map = _build_impact_map(db, event_ids)
    reviewed_ids = _reviewed_event_ids(db, event_ids)
    projects = db.query(BomProject).all()
    actions: list[dict] = []
    grouped: dict[tuple[str, str], list[MarketEvent]] = defaultdict(list)
    now = _now()

    for event in events:
        impact = _event_impact(db, event.id, impact_map)
        has_review = _has_review_source(db, event.id, reviewed_ids)
        brand = event.brand or "暂无"
        category = event.category or "暂无"
        grouped[(brand, category)].append(event)

        if (_is_high_severity(event) and not has_review) or ((event.confidence or 0) < 0.75 and impact["item_count"] > 0):
            actions.append({
                "id": f"review_event:{event.id}",
                "action_type": "review_event",
                "priority": "high",
                "title": "建议复核高风险事件",
                "reason": "高严重度事件缺少复核来源，或低置信度事件已经命中 BOM 物料。",
                "brand": event.brand,
                "category": event.category,
                **_trace_payload([event.id], impact["project_ids"], _impact_item_ids(impact)),
                "project_count": impact["project_count"],
                "item_count": impact["item_count"],
                "target_route": "/events",
            })

        if impact["item_count"] > 0:
            actions.append({
                "id": f"validate_prediction:{event.id}",
                "action_type": "validate_prediction",
                "priority": "medium",
                "title": "建议验证预测命中",
                "reason": "事件已经命中 BOM 物料，需要确认命中物料和风险等级是否符合业务判断。",
                "brand": event.brand,
                "category": event.category,
                **_trace_payload([event.id], impact["project_ids"], _impact_item_ids(impact)),
                "project_count": impact["project_count"],
                "item_count": impact["item_count"],
                "target_route": "/events",
            })

        if (event.confidence or 0) < 0.75 and not has_review and impact["item_count"] == 0:
            actions.append({
                "id": f"consider_disable_event:{event.id}",
                "action_type": "consider_disable_event",
                "priority": "low",
                "title": "建议人工判断是否停用事件",
                "reason": "事件置信度偏低、无复核来源，且暂未命中任何 BOM 物料。",
                "brand": event.brand,
                "category": event.category,
                **_trace_payload([event.id]),
                "project_count": 0,
                "item_count": 0,
                "target_route": "/events",
            })

        if _is_high_severity(event):
            event_created_at = _as_aware(event.created_at)
            stale_projects = []
            for project in projects:
                last_analysis_at = _as_aware(project.last_analysis_at)
                if last_analysis_at is None or (event_created_at and last_analysis_at < event_created_at):
                    stale_projects.append(project.id)
            if stale_projects:
                actions.append({
                    "id": f"rescan_bom:{event.id}",
                    "action_type": "rescan_bom",
                    "priority": "high",
                    "title": "建议重扫历史 BOM",
                    "reason": "存在高风险事件晚于项目最后分析时间，历史 BOM 可能需要重新评估。",
                    "brand": event.brand,
                    "category": event.category,
                    **_trace_payload([event.id], stale_projects, _impact_item_ids(impact)),
                    "project_count": len(stale_projects),
                    "item_count": impact["item_count"],
                    "target_route": "/events",
                })

    for (brand, category), grouped_events in grouped.items():
        recent_events = [event for event in grouped_events if _as_aware(event.created_at) and _as_aware(event.created_at) >= now - timedelta(days=30)]
        if len(recent_events) >= 2:
            recent_impacts = [_event_impact(db, event.id, impact_map) for event in recent_events]
            unique_items = _unique_items(recent_impacts)
            project_ids = {item.bom_upload_id for item in unique_items}
            item_ids = [item.id for item in unique_items if item.id is not None]
            item_count = len(unique_items)
            actions.append({
                "id": f"watch_category:{brand}:{category}",
                "action_type": "watch_category",
                "priority": "medium",
                "title": "建议关注品牌品类趋势",
                "reason": "同一品牌和品类近 30 天出现多条活跃行情事件。",
                "brand": None if brand == "暂无" else brand,
                "category": None if category == "暂无" else category,
                **_trace_payload([event.id for event in recent_events], list(project_ids), item_ids),
                "project_count": len(project_ids),
                "item_count": item_count,
                "target_route": "/events",
            })

    actions.sort(key=lambda item: (-PRIORITY_ORDER.get(item["priority"], 0), -item["item_count"], item["id"]))
    return actions


def _rank_rows(rows, name_key):
    payload = []
    for row in rows.values():
        payload.append({
            name_key: row[name_key],
            "event_count": row["event_count"],
            "project_count": len(row["project_ids"]),
            "item_count": row["item_count"],
        })
    return sorted(payload, key=lambda item: (-item["item_count"], -item["event_count"], item[name_key]))


@router.get("/summary")
def get_trend_summary(db: Session = Depends(get_db)):
    events = _active_events(db)
    now = _now()
    event_ids = [event.id for event in events]
    impact_map = _build_impact_map(db, event_ids)
    event_impacts = [_event_impact(db, event.id, impact_map) for event in events]
    unique_items = _unique_items(event_impacts)
    affected_project_ids = {item.bom_upload_id for item in unique_items}
    affected_item_count = len(unique_items)
    risk_counts = _risk_counts_for_items(unique_items)
    red_item_count = risk_counts["red"]
    yellow_item_count = risk_counts["yellow"]

    action_count = len(_build_actions(db, events))
    return {
        "active_event_count": len(events),
        "total_events": len(events),
        "active_alerts": action_count,
        "high_severity_event_count": sum(1 for event in events if _is_high_severity(event)),
        "new_events_7d": sum(1 for event in events if _as_aware(event.created_at) and _as_aware(event.created_at) >= now - timedelta(days=7)),
        "new_events_30d": sum(1 for event in events if _as_aware(event.created_at) and _as_aware(event.created_at) >= now - timedelta(days=30)),
        "affected_project_count": len(affected_project_ids),
        "affected_item_count": affected_item_count,
        "red_item_count": red_item_count,
        "yellow_item_count": yellow_item_count,
        "action_count": action_count,
        "generated_at": now.isoformat(),
    }


@router.get("/timeline")
def get_trend_timeline(days: int = Query(30), db: Session = Depends(get_db)):
    if days not in {7, 30, 90}:
        days = 30
    now = _now()
    since = now - timedelta(days=days)
    events = [
        event
        for event in _active_events(db)
        if _as_aware(event.created_at) and _as_aware(event.created_at) >= since
    ]
    event_ids = [event.id for event in events]
    impact_map = _build_impact_map(db, event_ids)

    daily = defaultdict(lambda: {"event_count": 0, "high_severity_event_count": 0})
    brand_map = defaultdict(lambda: {"brand": "暂无", "event_count": 0, "project_ids": set(), "item_count": 0})
    category_map = defaultdict(lambda: {"category": "暂无", "event_count": 0, "project_ids": set(), "item_count": 0})
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "unknown": 0}

    for event in events:
        created_at = _as_aware(event.created_at)
        day_key = created_at.date().isoformat()
        daily[day_key]["event_count"] += 1
        if _is_high_severity(event):
            daily[day_key]["high_severity_event_count"] += 1
        severity = _severity_value(event)
        if severity not in severity_counts:
            severity = "unknown"
        severity_counts[severity] += 1

        impact = _event_impact(db, event.id, impact_map)
        brand = event.brand or "暂无"
        category = event.category or "暂无"
        brand_map[brand]["brand"] = brand
        brand_map[brand]["event_count"] += 1
        brand_map[brand].setdefault("item_ids", set()).update(item.id for item in impact["items"] if item.id is not None)
        brand_map[brand]["project_ids"].update(item.bom_upload_id for item in impact["items"] if item.id is not None)
        brand_map[brand]["item_count"] = len(brand_map[brand]["item_ids"])
        category_map[category]["category"] = category
        category_map[category]["event_count"] += 1
        category_map[category].setdefault("item_ids", set()).update(item.id for item in impact["items"] if item.id is not None)
        category_map[category]["project_ids"].update(item.bom_upload_id for item in impact["items"] if item.id is not None)
        category_map[category]["item_count"] = len(category_map[category]["item_ids"])

    return {
        "days": days,
        "daily_events": [
            {"date": day, **daily[day]}
            for day in sorted(daily.keys())
        ],
        "brand_rank": _rank_rows(brand_map, "brand"),
        "category_rank": _rank_rows(category_map, "category"),
        "severity_counts": severity_counts,
    }


@router.get("/validation")
def get_trend_validation(db: Session = Depends(get_db)):
    events = _active_events(db)
    event_ids = [event.id for event in events]
    impact_map = _build_impact_map(db, event_ids)
    reviewed_ids = _reviewed_event_ids(db, event_ids)
    latest_records = _latest_validation_records(db, event_ids)
    result_events = []
    counts = {"risk_hit": 0, "not_hit_yet": 0, "needs_review": 0}
    for event in events:
        impact = _event_impact(db, event.id, impact_map)
        status = _validation_status(db, event, impact, reviewed_ids)
        counts[status] += 1
        result_events.append({
            "event_id": event.id,
            "title": _event_title(event),
            "raw_title": event.raw_title,
            "source_name": event.source_name,
            "brand": event.brand,
            "category": event.category,
            "event_type": event.event_type.value if event.event_type else None,
            "severity": _severity_value(event),
            "confidence": event.confidence,
            "validation_status": status,
            "project_count": impact["project_count"],
            "item_count": impact["item_count"],
            "trigger_reason": _validation_trigger_reason(event, impact),
            "last_validation_record": latest_records[event.id].to_dict() if event.id in latest_records else None,
        })
    active_count = len(events)
    return {
        "risk_hit_count": counts["risk_hit"],
        "not_hit_yet_count": counts["not_hit_yet"],
        "needs_review_count": counts["needs_review"],
        "hit_rate": counts["risk_hit"] / active_count if active_count else 0,
        "review_needed_rate": counts["needs_review"] / active_count if active_count else 0,
        "events": result_events,
        "recent_records": [
            row.to_dict()
            for row in db.query(PredictionValidationRecord)
            .order_by(PredictionValidationRecord.created_at.desc(), PredictionValidationRecord.id.desc())
            .limit(10)
            .all()
        ],
    }


@router.post("/validation/{event_id}/records")
def create_prediction_validation_record(
    event_id: int,
    payload: PredictionValidationRecordCreate,
    db: Session = Depends(get_db),
):
    event = db.query(MarketEvent).filter(MarketEvent.id == event_id, MarketEvent.is_active == 1).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Market event not found")
    outcome = (payload.outcome or "").strip()
    if outcome not in VALIDATION_OUTCOMES:
        raise HTTPException(status_code=400, detail="Invalid validation outcome")
    impact = _event_impact(db, event_id)
    status = _validation_status(db, event, impact)
    record = PredictionValidationRecord(
        event_id=event_id,
        validation_status=status,
        outcome=outcome,
        reviewer=(payload.reviewer or "").strip() or None,
        notes=(payload.notes or "").strip() or None,
        affected_project_count=impact["project_count"],
        affected_item_count=impact["item_count"],
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record.to_dict()


@router.get("/actions")
def get_trend_actions(db: Session = Depends(get_db)):
    return {"actions": _build_actions(db)}
