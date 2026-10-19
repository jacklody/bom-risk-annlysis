"""市场事件接口"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.bom import BomItem, BomProject
from app.models.event import EventType, ExtractedMarketSignal, MarketEvent, RawMarketNotice, Severity
from app.models.media_source import MediaSourceRun
from app.knowledge.media_sources import get_media_source, list_media_sources
from app.services.event_collector import EventCollector
from app.services.upstream.manual_event_service import build_market_event_from_manual_payload

router = APIRouter()


class EventStatusRequest(BaseModel):
    action: str = Field(..., pattern="^(disable|enable)$")


def _csv_contains_id(csv_text: str | None, target_id: int) -> bool:
    if not csv_text:
        return False
    return str(target_id) in {part.strip() for part in csv_text.split(",") if part.strip()}


def _risk_value(item: BomItem) -> str:
    if not item.risk_level:
        return "gray"
    return item.risk_level.value if hasattr(item.risk_level, "value") else str(item.risk_level)


def _highest_risk(levels: list[str]) -> str:
    order = {"red": 4, "yellow": 3, "green": 2, "gray": 1}
    if not levels:
        return "gray"
    return max(levels, key=lambda level: order.get(level, 0))


def _parse_csv_ids(csv_text: str | None) -> list[int]:
    if not csv_text:
        return []
    return [int(part.strip()) for part in csv_text.split(",") if part.strip().isdigit()]


@router.get("/")
def list_events(
    db: Session = Depends(get_db),
    brand: str | None = Query(None),
    category: str | None = Query(None),
    event_type: EventType | None = Query(None),
    severity: Severity | None = Query(None),
    active_status: str = Query("active", pattern="^(active|inactive|all)$"),
    is_active: bool | None = Query(None),
    event_ids: str | None = Query(None),
    skip: int = 0,
    limit: int = 50,
):
    query = db.query(MarketEvent)

    if active_status == "active":
        if is_active is False:
            query = query.filter(MarketEvent.is_active == 0)
        else:
            query = query.filter(MarketEvent.is_active == 1)
    elif active_status == "inactive":
        query = query.filter(MarketEvent.is_active == 0)

    parsed_event_ids = _parse_csv_ids(event_ids)
    if parsed_event_ids:
        query = query.filter(MarketEvent.id.in_(parsed_event_ids))

    if brand:
        query = query.filter(MarketEvent.brand.contains(brand))
    if category:
        query = query.filter(MarketEvent.category.contains(category))
    if event_type:
        query = query.filter(MarketEvent.event_type == event_type)
    if severity:
        query = query.filter(MarketEvent.severity == severity)

    total = query.count()
    events = (
        query.order_by(MarketEvent.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return {"total": total, "events": [e.to_dict() for e in events]}


@router.get("/media-sources")
def list_registered_media_sources(enabled_only: bool = Query(False)):
    """查看已登记的行业媒体/行情数据源及接入状态。"""
    sources = list_media_sources(enabled_only=enabled_only)
    return {
        "total": len(sources),
        "sources": [source.to_dict() for source in sources],
    }


@router.get("/media-source-runs")
def list_media_source_runs(
    source_id: str | None = Query(None),
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """查看媒体源采集运行记录。"""
    query = db.query(MediaSourceRun)
    if source_id:
        query = query.filter(MediaSourceRun.source_id == source_id)
    runs = (
        query.order_by(MediaSourceRun.started_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "total": len(runs),
        "runs": [run.to_dict() for run in runs],
    }


@router.post("/collect")
def trigger_collection(db: Session = Depends(get_db)):
    """手动触发事件采集（含行情知识库播种 + 行业媒体爬虫 + LCSC趋势）"""
    collector = EventCollector(db)
    new_events = collector.collect_all()
    return {
        "collected": len(new_events),
        "events": [e.to_dict() for e in new_events],
    }


@router.post("/forward-article")
def forward_article(payload: dict, db: Session = Depends(get_db)):
    """手动转发公众号/行业文章，解析后生成市场事件。

    必填: source_id, text
    选填: title
    """
    from app.knowledge.media_sources import get_media_source
    from app.services.upstream.market_notice_parser import parse_market_notice

    source_id = (payload.get("source_id") or "").strip()
    title = (payload.get("title") or "").strip()
    text = (payload.get("text") or "").strip()

    if not source_id:
        raise HTTPException(status_code=400, detail="source_id is required")
    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    source = get_media_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"Unknown media source: {source_id}")

    collector = EventCollector(db)
    signals = parse_market_notice(
        raw_text=text,
        title=title,
        source_type=source.source_type,
        source_name=source_id,
    )

    new_events = []
    for sig in signals:
        d = sig.to_dict()
        d["source_url"] = payload.get("source_url", "")
        d["source_name"] = source_id
        d["source_type"] = source.source_type
        if source.source_type == "wechat_mp":
            d["confidence"] = round(d.get("confidence", 0) * 0.65, 2)
            d["confidence_reason"] = (
                (d.get("confidence_reason", "") or "")
                + "；公众号/社交来源降权"
            )

        if d.get("confidence", 0) < 0.20:
            continue

        evt_data = {
            "source_name": source_id,
            "source_url": payload.get("source_url", ""),
            "raw_title": title[:200] or (d.get("evidence_text") or "")[:200],
            "raw_text": text[:2000],
            "brand": d.get("brand"),
            "category": d.get("category"),
            "event_type": d.get("event_type", "other"),
            "severity": "medium" if d.get("confidence", 0) < 0.7 else "high",
            "confidence": d.get("confidence", 0.55),
            "estimated_lead_time_impact_weeks": d.get("lead_time_weeks"),
            "estimated_price_impact_pct": d.get("increase_max_pct"),
        }
        saved = collector._save_event(evt_data, min_confidence=0.18)
        if saved:
            new_events.append(saved)

    run_status = "success" if new_events else "empty"
    collector.record_source_run(
        source_id=source_id,
        status=run_status,
        articles_crawled=1,
        signals_parsed=len(signals),
        events_created=len(new_events),
    )

    return {
        "status": "ok",
        "source_id": source_id,
        "source_name": source.name,
        "signals_parsed": len(signals),
        "events_created": len(new_events),
        "events": [e.to_dict() for e in new_events],
    }


@router.post("/collect-media")
def trigger_media_crawl(
    source_id: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """手动触发行业媒体爬虫（不含知识库播种，仅抓取外部媒体）"""
    source = get_media_source(source_id) if source_id else None
    if source_id and not source:
        raise HTTPException(status_code=404, detail=f"Unknown media source: {source_id}")
    if source and source.status() != "active":
        return {
            "status": "skipped",
            "source_id": source_id,
            "source_status": source.status(),
            "articles_crawled": 0,
            "signals_parsed": 0,
            "events_created": 0,
            "events": [],
            "message": "该来源需要手动转发或配置授权后才能采集，请先通过行情收件箱/转发入口录入。",
        }

    from app.services.media_crawler import IndustryMediaCrawler

    skipped_sources = []
    if not source_id:
        skipped_sources = [
            {
                "source_id": candidate.source_id,
                "name": candidate.name,
                "source_status": candidate.status(),
                "message": "该来源需要手动转发或配置授权后才能采集",
            }
            for candidate in list_media_sources()
            if candidate.status() in {"waiting_for_manual_forward", "waiting_for_configuration", "disabled"}
        ]

    crawler = IndustryMediaCrawler()
    try:
        articles = crawler.crawl_all(source_id=source_id)
        signals = crawler.parse_to_signals(articles)
    finally:
        crawler.close()

    collector = EventCollector(db)
    new_events = []
    for sig in signals:
        if sig.get("confidence", 0) < 0.3:
            continue
        evt_data = {
            "source_name": sig.get("source_name", "industry_media"),
            "source_url": sig.get("source_url", ""),
            "raw_title": (sig.get("evidence_text") or "")[:200],
            "raw_text": sig.get("evidence_text", ""),
            "brand": sig.get("brand"),
            "category": sig.get("category"),
            "event_type": sig.get("event_type", "other"),
            "severity": "medium" if sig.get("confidence", 0) < 0.7 else "high",
            "confidence": sig.get("confidence", 0.55),
            "estimated_lead_time_impact_weeks": sig.get("lead_time_weeks"),
            "estimated_price_impact_pct": sig.get("increase_max_pct"),
        }
        saved = collector._save_event(evt_data)
        if saved:
            new_events.append(saved)

    # 记录运行
    sid = source_id or "all"
    run_status = "success" if articles else "empty"
    collector.record_source_run(
        source_id=sid,
        status=run_status,
        articles_crawled=len(articles),
        signals_parsed=len(signals),
        events_created=len(new_events),
    )

    return {
        "status": "ok",
        "source_id": source_id or "all",
        "articles_crawled": len(articles),
        "signals_parsed": len(signals),
        "events_created": len(new_events),
        "skipped_count": len(skipped_sources),
        "skipped_sources": skipped_sources,
        "events": [e.to_dict() for e in new_events],
    }


@router.post("/manual")
def add_manual_event(
    payload: dict,
    db: Session = Depends(get_db),
):
    """手动添加市场事件，并使用 v3.2 情报可信度模型结构化。"""
    collector = EventCollector(db)
    event_data = build_market_event_from_manual_payload(payload)
    event = collector._save_event(event_data)
    if event:
        return {
            "status": "ok",
            "event": event.to_dict(),
            "review_recommendation": event_data.get("review_recommendation"),
            "can_trigger_high_risk": event_data.get("can_trigger_high_risk"),
            "confidence_reason": event_data.get("confidence_reason"),
        }
    return {
        "status": "skipped",
        "reason": "low confidence",
        "review_recommendation": event_data.get("review_recommendation"),
        "can_trigger_high_risk": event_data.get("can_trigger_high_risk"),
        "confidence_reason": event_data.get("confidence_reason"),
    }


@router.patch("/{event_id}/status")
def update_event_status(event_id: int, payload: EventStatusRequest, db: Session = Depends(get_db)):
    event = db.query(MarketEvent).filter(MarketEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if payload.action == "disable":
        event.is_active = 0
        message = "事件已停用"
    else:
        event.is_active = 1
        message = "事件已启用"

    db.commit()
    db.refresh(event)
    return {"event": event.to_dict(), "message": message}


@router.get("/{event_id}/impact")
def get_event_impact(event_id: int, db: Session = Depends(get_db)):
    event = db.query(MarketEvent).filter(MarketEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    items = db.query(BomItem).all()
    matched_items = [item for item in items if _csv_contains_id(item.matched_event_ids, event_id)]
    project_ids = sorted({item.bom_upload_id for item in matched_items})
    projects = db.query(BomProject).filter(BomProject.id.in_(project_ids)).all() if project_ids else []
    project_map = {project.id: project for project in projects}

    risk_counts = {"red": 0, "yellow": 0, "green": 0, "gray": 0}
    grouped: dict[int, list[BomItem]] = {}
    for item in matched_items:
        level = _risk_value(item)
        if level not in risk_counts:
            level = "gray"
        risk_counts[level] += 1
        grouped.setdefault(item.bom_upload_id, []).append(item)

    project_payloads = []
    for project_id, project_items in grouped.items():
        levels = [_risk_value(item) for item in project_items]
        project = project_map.get(project_id)
        project_payloads.append({
            "project_id": project_id,
            "project_name": (project.project_name or project.filename) if project else f"项目 {project_id}",
            "affected_item_count": len(project_items),
            "highest_risk_level": _highest_risk(levels),
        })

    project_payloads.sort(key=lambda item: item["project_id"])
    return {
        "event_id": event_id,
        "project_count": len(grouped),
        "item_count": len(matched_items),
        "risk_counts": risk_counts,
        "projects": project_payloads,
    }


@router.get("/{event_id}/source-signal")
def get_event_source_signal(event_id: int, db: Session = Depends(get_db)):
    event = db.query(MarketEvent).filter(MarketEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    signal = (
        db.query(ExtractedMarketSignal)
        .filter(ExtractedMarketSignal.market_event_id == event_id)
        .order_by(ExtractedMarketSignal.id.desc())
        .first()
    )
    notice = None
    if signal:
        notice = db.query(RawMarketNotice).filter(RawMarketNotice.id == signal.raw_notice_id).first()

    return {
        "event_id": event_id,
        "signal": signal.to_dict() if signal else None,
        "raw_notice": notice.to_dict() if notice else None,
    }


@router.get("/{event_id}")
def get_event(event_id: int, db: Session = Depends(get_db)):
    event = db.query(MarketEvent).filter(MarketEvent.id == event_id).first()
    if not event:
        return {"error": "Event not found"}
    return event.to_dict()
