from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.knowledge.media_sources import list_media_sources
from app.models.bom import BomItem, BomProject, RiskLevel
from app.models.event import MarketEvent

RISK_STAT_NOTE = "高风险项目定义为红色物料数大于 0 的项目"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _iso(value: datetime | None) -> str | None:
    aware = _as_aware(value)
    return aware.isoformat() if aware else None


def _risk_value(level) -> str:
    if isinstance(level, RiskLevel):
        return level.value
    return str(level or "gray")


def _csv_ids(value: str | None) -> list[int]:
    ids = []
    for part in (value or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError:
            continue
    return ids


def _target_query(event_ids: list[int] | None = None, project_ids: list[int] | None = None, item_ids: list[int] | None = None) -> dict:
    query = {}
    event_ids = sorted({item for item in (event_ids or []) if item is not None})
    project_ids = sorted({item for item in (project_ids or []) if item is not None})
    item_ids = sorted({item for item in (item_ids or []) if item is not None})
    if event_ids:
        query["event_ids"] = ",".join(str(item) for item in event_ids)
    if project_ids:
        query["project_ids"] = ",".join(str(item) for item in project_ids)
    if item_ids:
        query["item_ids"] = ",".join(str(item) for item in item_ids)
    return query


def _items_by_event(items: list[BomItem]) -> dict[int, list[BomItem]]:
    mapping: dict[int, list[BomItem]] = defaultdict(list)
    for item in items:
        for event_id in _csv_ids(item.matched_event_ids):
            mapping[event_id].append(item)
    return mapping


def _project_risks(projects: list[BomProject], items: list[BomItem]) -> list[dict]:
    items_by_project: dict[int, list[BomItem]] = defaultdict(list)
    for item in items:
        items_by_project[item.bom_upload_id].append(item)

    rows = []
    for project in projects:
        project_items = items_by_project.get(project.id, [])
        counts = {"red": 0, "orange": 0, "yellow": 0, "green": 0, "gray": 0}
        for item in project_items:
            level = _risk_value(item.risk_level)
            counts[level if level in counts else "gray"] += 1
        if not project_items:
            counts = {
                "red": project.items_red or 0,
                "orange": project.items_orange or 0,
                "yellow": project.items_yellow or 0,
                "green": project.items_green or 0,
                "gray": project.items_gray or 0,
            }
        item_count = len(project_items) or project.total_items or sum(counts.values())
        rows.append({
            "project_id": project.id,
            "project_name": project.project_name or project.filename,
            "file_name": project.filename,
            "item_count": item_count,
            "red_count": counts["red"],
            "orange_count": counts["orange"],
            "yellow_count": counts["yellow"],
            "green_count": counts["green"],
            "gray_count": counts["gray"],
            "risk_counts": counts,
            "last_analyzed_at": _iso(project.last_analysis_at),
            "target_route": f"/projects/{project.id}",
            "target_query": {},
        })
    return sorted(rows, key=lambda row: (-row["red_count"], -row["orange_count"], -row["yellow_count"], row["last_analyzed_at"] or ""), reverse=False)


def _category_risks(items: list[BomItem]) -> list[dict]:
    rows: dict[str, dict] = {}
    for item in items:
        category = item.normalized_category or item.raw_category or "未归类"
        row = rows.setdefault(category, {"category": category, "red_count": 0, "orange_count": 0, "yellow_count": 0, "related_event_ids": set()})
        level = _risk_value(item.risk_level)
        if level == "red":
            row["red_count"] += 1
        elif level == "orange":
            row["orange_count"] += 1
        elif level == "yellow":
            row["yellow_count"] += 1
        row["related_event_ids"].update(_csv_ids(item.matched_event_ids))

    payload = []
    for row in rows.values():
        related_event_ids = sorted(row["related_event_ids"])
        payload.append({
            "category": row["category"],
            "red_count": row["red_count"],
            "orange_count": row["orange_count"],
            "yellow_count": row["yellow_count"],
            "related_event_count": len(related_event_ids),
            "related_event_ids": related_event_ids,
            "target_route": "/events",
            "target_query": _target_query(related_event_ids),
        })
    return sorted(payload, key=lambda row: (-row["red_count"], -row["orange_count"], -row["yellow_count"], -row["related_event_count"], row["category"]))


def _recent_events(events: list[MarketEvent], items_by_event: dict[int, list[BomItem]], now: datetime) -> list[dict]:
    since = now - timedelta(days=30)
    recent = [event for event in events if _as_aware(event.created_at) and _as_aware(event.created_at) >= since]
    recent.sort(key=lambda event: _as_aware(event.created_at) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    payload = []
    for event in recent[:10]:
        impact_items = items_by_event.get(event.id, [])
        project_ids = sorted({item.bom_upload_id for item in impact_items if item.bom_upload_id is not None})
        item_ids = sorted({item.id for item in impact_items if item.id is not None})
        payload.append({
            "id": event.id,
            "title": event.raw_title or event.raw_text or f"事件 {event.id}",
            "source_name": event.source_name,
            "brand": event.brand,
            "category": event.category,
            "event_type": event.event_type.value if event.event_type else None,
            "severity": event.severity.value if event.severity else None,
            "confidence": event.confidence,
            "price_impact_pct": event.estimated_price_impact_pct,
            "lead_time_impact_weeks": event.estimated_lead_time_impact_weeks,
            "impact_project_count": len(project_ids),
            "impact_item_count": len(item_ids),
            "created_at": _iso(event.created_at),
            "target_route": "/events",
            "target_query": _target_query([event.id]),
        })
    return payload


def _trend_actions(events: list[MarketEvent], items_by_event: dict[int, list[BomItem]]) -> list[dict]:
    actions = []
    for event in events:
        impact_items = items_by_event.get(event.id, [])
        if not impact_items:
            continue
        project_ids = sorted({item.bom_upload_id for item in impact_items if item.bom_upload_id is not None})
        item_ids = sorted({item.id for item in impact_items if item.id is not None})
        actions.append({
            "id": f"review_event:{event.id}",
            "action_type": "review_event",
            "priority": "high" if (event.severity and event.severity.value in {"critical", "high"}) else "medium",
            "title": "建议复核高风险事件",
            "reason": "事件已经命中 BOM 物料，需要确认影响范围和采购处理优先级。",
            "brand": event.brand,
            "category": event.category,
            "event_ids": [event.id],
            "project_ids": project_ids,
            "item_ids": item_ids,
            "project_count": len(project_ids),
            "item_count": len(item_ids),
            "target_route": "/events",
            "target_query": _target_query([event.id], project_ids, item_ids),
        })
    return sorted(actions, key=lambda row: (-row["item_count"], row["id"]))[:10]


def _risk_changes(projects: list[BomProject], events: list[MarketEvent], now: datetime) -> dict:
    recent_since = now - timedelta(days=7)
    changed_projects = []
    for project in projects:
        new_red = project.new_red_count or 0
        new_orange = project.new_orange_count or 0
        new_yellow = project.new_yellow_count or 0
        if new_red + new_orange + new_yellow <= 0:
            continue
        changed_projects.append({
            "project_id": project.id,
            "project_name": project.project_name or project.filename,
            "file_name": project.filename,
            "new_red_count": new_red,
            "new_orange_count": new_orange,
            "new_yellow_count": new_yellow,
            "last_analyzed_at": _iso(project.last_analysis_at),
            "target_route": f"/projects/{project.id}",
            "target_query": {},
        })
    changed_projects.sort(key=lambda row: (-row["new_red_count"], -row["new_orange_count"], -row["new_yellow_count"], row["project_name"] or ""))

    recent_events = [event for event in events if _as_aware(event.created_at) and _as_aware(event.created_at) >= recent_since]
    recent_events.sort(key=lambda event: _as_aware(event.created_at) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    event_rows = [{
        "id": event.id,
        "title": event.raw_title or event.raw_text or f"事件 {event.id}",
        "source_name": event.source_name,
        "severity": event.severity.value if event.severity else None,
        "created_at": _iso(event.created_at),
        "target_route": "/events",
        "target_query": _target_query([event.id]),
    } for event in recent_events[:5]]

    new_red_total = sum(row["new_red_count"] for row in changed_projects)
    new_orange_total = sum(row["new_orange_count"] for row in changed_projects)
    new_yellow_total = sum(row["new_yellow_count"] for row in changed_projects)
    project_summaries = [
        f"{row['project_name']}新增红色风险{row['new_red_count']}项、橙色风险{row['new_orange_count']}项、黄色风险{row['new_yellow_count']}项"
        for row in changed_projects[:3]
    ]
    notification_parts = []
    if project_summaries:
        notification_parts.append("；".join(project_summaries))
    if event_rows:
        notification_parts.append(f"近7天新增活跃事件{len(event_rows)}条")
    notification_summary = "；".join(notification_parts) if notification_parts else "暂无新增红/橙/黄风险或近7天活跃事件。"

    return {
        "window_days": 7,
        "new_red_item_count": new_red_total,
        "new_orange_item_count": new_orange_total,
        "new_yellow_item_count": new_yellow_total,
        "changed_project_count": len(changed_projects),
        "recent_event_count_7d": len(recent_events),
        "notification_ready": bool(changed_projects or recent_events),
        "notification_summary": notification_summary,
        "projects": changed_projects[:10],
        "events": event_rows,
    }



def _supply_sources() -> list[dict]:
    sources = []
    for source in list_media_sources(enabled_only=False):
        data = source.to_dict()
        status = data.get("status")
        failure_reason = ""
        if status == "waiting_for_manual_forward":
            failure_reason = "该来源需要人工转发或 Feed 配置后才能进入自动处理。"
        elif status == "waiting_for_configuration":
            failure_reason = "该来源需要补充抓取配置或授权后才能稳定使用。"
        elif status == "disabled":
            failure_reason = "该来源当前已暂停自动采集。"
        sources.append({
            "source_id": data.get("source_id"),
            "name": data.get("name"),
            "source_type": data.get("source_type"),
            "channel_type": data.get("channel_type"),
            "status": status,
            "crawler_strategy": data.get("crawler_strategy"),
            "enabled": data.get("enabled"),
            "failure_reason": failure_reason,
            "last_checked_at": None,
        })
    return sources


def _material_overview(db: Session) -> dict | None:
    """集成上游原材料价格监控摘要（Phase 4 仪表盘集成）。

    尝试加载 MaterialPriceService 缓存统计和各域高风险材料数量。
    若服务不可用则返回 None，前端可据此判断是否需要展示该模块。
    """
    try:
        from app.services.material_price_service import get_material_price_service
        svc = get_material_price_service()
        cache = svc.get_cache_stats()
    except Exception:
        return None

    # 统计已缓存材料中的风险分布（从缓存推断，避免额外 DB 查询）
    degraded_count = cache.get("degraded", 0)
    by_domain = cache.get("by_domain", {})

    return {
        "total_materials_cached": cache.get("total_cached", 0),
        "fresh_cache_count": cache.get("fresh", 0),
        "stale_cache_count": cache.get("stale", 0),
        "degraded_count": degraded_count,
        "metals_api_calls_month": cache.get("metals_api_calls_this_month", 0),
        "metals_api_quota": cache.get("metals_api_quota", 60),
        "by_domain": by_domain,
        "status": "degraded" if degraded_count > 0 else "healthy",
        "last_updated": _now().isoformat(),
    }


def _material_top_alerts(db: Session, limit: int = 5) -> list[dict] | None:
    """从 material_prices 表提取近期价格变动最大的材料预警。"""
    try:
        from sqlalchemy import desc, func, text
        from app.models.material_price import MaterialPrice
        from app.knowledge.material_mapping import get_material_entry

        since = _now() - timedelta(days=30)
        # 取最近 30 天有价格记录的材料的最新价格
        subq = (
            db.query(
                MaterialPrice.material_key,
                func.max(MaterialPrice.fetch_timestamp).label("latest_ts"),
            )
            .filter(MaterialPrice.fetch_timestamp >= since)
            .group_by(MaterialPrice.material_key)
            .subquery()
        )

        latest_prices = (
            db.query(MaterialPrice)
            .join(
                subq,
                (MaterialPrice.material_key == subq.c.material_key)
                & (MaterialPrice.fetch_timestamp == subq.c.latest_ts),
            )
            .all()
        )

        alerts = []
        for mp in latest_prices[:limit * 3]:  # oversample for filtering
            entry = get_material_entry(mp.material_key)
            if not entry:
                continue
            alerts.append({
                "material_key": mp.material_key,
                "material_name_zh": entry.name_zh,
                "domain": entry.domain,
                "latest_price": mp.price_value,
                "unit": mp.price_unit,
                "source_name": mp.source_name,
                "last_fetched": mp.fetch_timestamp.isoformat() if mp.fetch_timestamp else None,
            })

        return alerts[:limit]
    except Exception:
        return None


def build_dashboard_summary(db: Session) -> dict:
    now = _now()
    projects = db.query(BomProject).all()
    items = db.query(BomItem).all()
    events = db.query(MarketEvent).filter(MarketEvent.is_active == 1).all()
    items_by_event = _items_by_event(items)
    project_rows = _project_risks(projects, items)
    recent_events = _recent_events(events, items_by_event, now)
    trend_actions = _trend_actions(events, items_by_event)
    return {
        "overview": {
            "project_count": len(projects),
            "high_risk_project_count": sum(1 for row in project_rows if row["red_count"] > 0 or row["orange_count"] > 0),
            "red_item_count": sum(1 for item in items if _risk_value(item.risk_level) == "red"),
            "active_event_count_30d": len(recent_events),
            "pending_action_count": len(trend_actions),
            "risk_stat_note": RISK_STAT_NOTE,
        },
        "project_risks": project_rows,
        "category_risks": _category_risks(items),
        "recent_events": recent_events,
        "trend_actions": trend_actions,
        "risk_changes": _risk_changes(projects, events, now),
        "supply_sources": _supply_sources(),
        "material_alerts": _material_overview(db),           # Phase 4: 原料价格监控
        "material_top": _material_top_alerts(db, limit=5),   # Phase 4: 最新价格 Top-5
        "generated_at": now.isoformat(),
    }
