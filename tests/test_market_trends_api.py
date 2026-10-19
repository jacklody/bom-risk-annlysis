from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.database import SessionLocal, init_db
from app.main import app
from app.models.bom import BomItem, BomProject, RiskLevel
from app.models.event import EventType, ExtractedMarketSignal, MarketEvent, PredictionValidationRecord, RawMarketNotice, Severity

client = TestClient(app)


def _clean_trend_data():
    init_db()
    db = SessionLocal()
    db.query(PredictionValidationRecord).delete()
    db.query(ExtractedMarketSignal).delete()
    db.query(RawMarketNotice).delete()
    db.query(BomItem).delete()
    db.query(BomProject).delete()
    db.query(MarketEvent).delete()
    db.commit()
    db.close()


def _seed_event(*, brand="TDK", category="high_cap_mlcc", severity=Severity.HIGH, confidence=0.85, days_ago=0, is_active=1):
    db = SessionLocal()
    try:
        event = MarketEvent(
            source_name="趋势测试来源",
            source_url="test://trend",
            raw_text=f"{brand} {category} 行情波动",
            raw_title=f"{brand} {category} 通知",
            brand=brand,
            category=category,
            event_type=EventType.PRICE_INCREASE,
            severity=severity,
            confidence=confidence,
            created_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
            is_active=is_active,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event.id
    finally:
        db.close()


def _seed_project_with_items(event_id: int, *, matched_event_ids: str | None = None):
    db = SessionLocal()
    try:
        project = BomProject(
            filename="trend-demo.xlsx",
            project_name="趋势验证项目",
            total_items=2,
            items_analyzed=2,
            items_red=1,
            items_yellow=1,
            last_analysis_at=datetime.now(timezone.utc) - timedelta(days=3),
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        event_ids = matched_event_ids if matched_event_ids is not None else str(event_id)
        db.add_all([
            BomItem(
                bom_upload_id=project.id,
                row_number=1,
                raw_part_number="C-RED",
                raw_brand="TDK",
                raw_category="high_cap_mlcc",
                normalized_brand="TDK",
                normalized_category="high_cap_mlcc",
                risk_level=RiskLevel.RED,
                risk_score=0.92,
                matched_event_ids=event_ids,
            ),
            BomItem(
                bom_upload_id=project.id,
                row_number=2,
                raw_part_number="C-YELLOW",
                raw_brand="TDK",
                raw_category="high_cap_mlcc",
                normalized_brand="TDK",
                normalized_category="high_cap_mlcc",
                risk_level=RiskLevel.YELLOW,
                risk_score=0.68,
                matched_event_ids=event_ids,
            ),
        ])
        db.commit()
        return project.id
    finally:
        db.close()


def _seed_review_source(event_id: int, *, summary: str | None = "证据摘要"):
    db = SessionLocal()
    try:
        notice = RawMarketNotice(
            source_type="manual",
            source_name="趋势测试来源",
            title=summary,
            raw_text="用于验证行情趋势接口的原始通知",
            parse_status="reviewed",
        )
        db.add(notice)
        db.commit()
        db.refresh(notice)
        signal = ExtractedMarketSignal(
            raw_notice_id=notice.id,
            market_event_id=event_id,
            brand="TDK",
            category="high_cap_mlcc",
            event_type="price_increase",
            confidence=0.9,
            evidence_text=summary,
            review_status="accepted",
        )
        db.add(signal)
        db.commit()
        return signal.id
    finally:
        db.close()


def test_trend_summary_counts_events_and_impacted_bom_items():
    _clean_trend_data()
    event_id = _seed_event(days_ago=2)
    _seed_project_with_items(event_id)
    _seed_event(brand="Murata", category="resistor", severity=Severity.LOW, days_ago=40)
    _seed_event(brand="Yageo", category="resistor", severity=Severity.HIGH, is_active=0)

    resp = client.get("/api/market-trends/summary")

    assert resp.status_code == 200
    data = resp.json()
    assert data["active_event_count"] == 2
    assert data["total_events"] == 2
    assert data["active_alerts"] >= 1
    assert data["high_severity_event_count"] == 1
    assert data["new_events_7d"] == 1
    assert data["new_events_30d"] == 1
    assert data["affected_project_count"] == 1
    assert data["affected_item_count"] == 2
    assert data["red_item_count"] == 1
    assert data["yellow_item_count"] == 1
    assert data["action_count"] >= 1
    assert data["generated_at"]


def test_trend_summary_ignores_partial_csv_id_matches():
    _clean_trend_data()
    event_id = _seed_event(days_ago=2)
    _seed_project_with_items(event_id, matched_event_ids=f"{event_id}1, {event_id}2")

    resp = client.get("/api/market-trends/summary")

    assert resp.status_code == 200
    data = resp.json()
    assert data["affected_project_count"] == 0
    assert data["affected_item_count"] == 0
    assert data["red_item_count"] == 0
    assert data["yellow_item_count"] == 0


def test_trend_summary_deduplicates_items_matched_by_multiple_events():
    _clean_trend_data()
    first_id = _seed_event(brand="TDK", category="high_cap_mlcc", severity=Severity.HIGH, days_ago=1)
    second_id = _seed_event(brand="TDK", category="high_cap_mlcc", severity=Severity.MEDIUM, days_ago=2)
    _seed_project_with_items(first_id, matched_event_ids=f"{first_id},{second_id}")

    resp = client.get("/api/market-trends/summary")

    assert resp.status_code == 200
    data = resp.json()
    assert data["affected_project_count"] == 1
    assert data["affected_item_count"] == 2
    assert data["red_item_count"] == 1
    assert data["yellow_item_count"] == 1


def test_trend_summary_handles_review_source_with_empty_summary():
    _clean_trend_data()
    event_id = _seed_event(days_ago=2)
    _seed_review_source(event_id, summary=None)

    resp = client.get("/api/market-trends/summary")

    assert resp.status_code == 200
    assert resp.json()["active_event_count"] == 1


def test_trend_timeline_groups_by_date_brand_category_and_severity():
    _clean_trend_data()
    first_id = _seed_event(brand="TDK", category="high_cap_mlcc", severity=Severity.HIGH, days_ago=1)
    second_id = _seed_event(brand="TDK", category="high_cap_mlcc", severity=Severity.MEDIUM, days_ago=2)
    _seed_project_with_items(first_id)
    _seed_project_with_items(second_id)

    resp = client.get("/api/market-trends/timeline", params={"days": 30})

    assert resp.status_code == 200
    data = resp.json()
    assert data["days"] == 30
    assert data["brand_rank"][0]["brand"] == "TDK"
    assert data["brand_rank"][0]["event_count"] == 2
    assert data["category_rank"][0]["category"] == "high_cap_mlcc"
    assert data["severity_counts"]["high"] == 1
    assert data["severity_counts"]["medium"] == 1
    assert sum(day["event_count"] for day in data["daily_events"]) == 2


def test_trend_timeline_deduplicates_items_within_brand_and_category_rank():
    _clean_trend_data()
    first_id = _seed_event(brand="TDK", category="high_cap_mlcc", severity=Severity.HIGH, days_ago=1)
    second_id = _seed_event(brand="TDK", category="high_cap_mlcc", severity=Severity.MEDIUM, days_ago=2)
    _seed_project_with_items(first_id, matched_event_ids=f"{first_id},{second_id}")

    resp = client.get("/api/market-trends/timeline", params={"days": 30})

    assert resp.status_code == 200
    data = resp.json()
    assert data["brand_rank"][0]["brand"] == "TDK"
    assert data["brand_rank"][0]["event_count"] == 2
    assert data["brand_rank"][0]["project_count"] == 1
    assert data["brand_rank"][0]["item_count"] == 2
    assert data["category_rank"][0]["category"] == "high_cap_mlcc"
    assert data["category_rank"][0]["event_count"] == 2
    assert data["category_rank"][0]["project_count"] == 1
    assert data["category_rank"][0]["item_count"] == 2


def test_trend_validation_classifies_hit_not_hit_and_needs_review():
    _clean_trend_data()
    hit_id = _seed_event(brand="TDK", category="high_cap_mlcc", severity=Severity.MEDIUM, confidence=0.9)
    _seed_project_with_items(hit_id)
    _seed_event(brand="Murata", category="resistor", severity=Severity.LOW, confidence=0.9)
    _seed_event(brand="Yageo", category="resistor", severity=Severity.HIGH, confidence=0.6)

    resp = client.get("/api/market-trends/validation")

    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_hit_count"] == 1
    assert data["not_hit_yet_count"] == 1
    assert data["needs_review_count"] == 1
    assert data["hit_rate"] == 1 / 3
    hit_event = next(event for event in data["events"] if event["event_id"] == hit_id)
    assert hit_event["title"] == "TDK high_cap_mlcc 通知"
    assert hit_event["source_name"] == "趋势测试来源"
    assert hit_event["trigger_reason"] == "严重度 medium，置信度 90%，命中 1 个项目 2 个物料"
    statuses = {event["validation_status"] for event in data["events"]}
    assert "risk_hit" in statuses
    assert "not_hit_yet" in statuses
    assert "needs_review" in statuses


def test_trend_actions_generate_active_warning_queue_without_writes():
    _clean_trend_data()
    hit_id = _seed_event(brand="TDK", category="high_cap_mlcc", severity=Severity.HIGH, confidence=0.7)
    _seed_event(brand="TDK", category="high_cap_mlcc", severity=Severity.MEDIUM, confidence=0.9)
    low_id = _seed_event(brand="Unknown", category="connector", severity=Severity.LOW, confidence=0.5)
    _seed_project_with_items(hit_id)

    before_events = client.get("/api/events/", params={"active_status": "all"}).json()["total"]
    resp = client.get("/api/market-trends/actions")
    after_events = client.get("/api/events/", params={"active_status": "all"}).json()["total"]

    assert resp.status_code == 200
    actions = resp.json()["actions"]
    action_types = {action["action_type"] for action in actions}
    assert "review_event" in action_types
    assert "rescan_bom" in action_types
    assert "watch_category" in action_types
    assert "validate_prediction" in action_types
    assert "consider_disable_event" in action_types
    assert before_events == after_events
    assert any(action["event_ids"] == [low_id] for action in actions if action["action_type"] == "consider_disable_event")


def test_trend_actions_include_traceable_project_and_item_context():
    _clean_trend_data()
    event_id = _seed_event(brand="TDK", category="high_cap_mlcc", severity=Severity.HIGH, confidence=0.9)
    project_id = _seed_project_with_items(event_id)

    resp = client.get("/api/market-trends/actions")

    assert resp.status_code == 200
    actions = resp.json()["actions"]
    validate_action = next(action for action in actions if action["action_type"] == "validate_prediction")
    assert validate_action["event_ids"] == [event_id]
    assert validate_action["project_ids"] == [project_id]
    assert len(validate_action["item_ids"]) == 2
    assert validate_action["target_query"] == {
        "event_ids": str(event_id),
        "project_ids": str(project_id),
        "item_ids": ",".join(str(item_id) for item_id in validate_action["item_ids"]),
    }


def test_trend_actions_deduplicate_watch_category_items_matched_by_multiple_events():
    _clean_trend_data()
    first_id = _seed_event(brand="TDK", category="high_cap_mlcc", severity=Severity.HIGH, confidence=0.9)
    second_id = _seed_event(brand="TDK", category="high_cap_mlcc", severity=Severity.MEDIUM, confidence=0.9)
    _seed_review_source(first_id)
    _seed_project_with_items(first_id, matched_event_ids=f"{first_id},{second_id}")

    resp = client.get("/api/market-trends/actions")

    assert resp.status_code == 200
    watch_actions = [action for action in resp.json()["actions"] if action["action_type"] == "watch_category"]
    assert len(watch_actions) == 1
    assert watch_actions[0]["project_count"] == 1
    assert watch_actions[0]["item_count"] == 2


def test_create_prediction_validation_record_persists_business_review():
    _clean_trend_data()
    event_id = _seed_event(brand="TDK", category="high_cap_mlcc", severity=Severity.MEDIUM, confidence=0.9)
    _seed_project_with_items(event_id)

    resp = client.post(
        f"/api/market-trends/validation/{event_id}/records",
        json={
            "outcome": "confirmed_hit",
            "reviewer": "采购A",
            "notes": "BOM 中两颗高容 MLCC 已确认受影响",
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["event_id"] == event_id
    assert data["validation_status"] == "risk_hit"
    assert data["outcome"] == "confirmed_hit"
    assert data["reviewer"] == "采购A"
    assert data["notes"] == "BOM 中两颗高容 MLCC 已确认受影响"
    assert data["affected_project_count"] == 1
    assert data["affected_item_count"] == 2
    assert data["created_at"]

    validation = client.get("/api/market-trends/validation").json()
    assert validation["recent_records"][0]["id"] == data["id"]
    event_rows = {row["event_id"]: row for row in validation["events"]}
    assert event_rows[event_id]["last_validation_record"]["outcome"] == "confirmed_hit"


def _snapshot_trend_tables():
    db = SessionLocal()
    try:
        return {
            "events": [
                {
                    "id": event.id,
                    "is_active": event.is_active,
                    "confidence": event.confidence,
                    "updated_at": event.updated_at,
                }
                for event in db.query(MarketEvent).order_by(MarketEvent.id).all()
            ],
            "projects": [
                {
                    "id": project.id,
                    "status": project.status,
                    "last_analysis_at": project.last_analysis_at,
                    "updated_at": project.updated_at,
                }
                for project in db.query(BomProject).order_by(BomProject.id).all()
            ],
            "items": [
                {
                    "id": item.id,
                    "risk_level": item.risk_level,
                    "risk_score": item.risk_score,
                    "matched_event_ids": item.matched_event_ids,
                }
                for item in db.query(BomItem).order_by(BomItem.id).all()
            ],
            "signals": [
                {
                    "id": signal.id,
                    "market_event_id": signal.market_event_id,
                    "review_status": signal.review_status,
                    "evidence_text": signal.evidence_text,
                }
                for signal in db.query(ExtractedMarketSignal).order_by(ExtractedMarketSignal.id).all()
            ],
        }
    finally:
        db.close()


def test_trend_actions_review_event_follows_design_condition():
    _clean_trend_data()
    low_confidence_reviewed_no_impact_id = _seed_event(
        brand="TDK",
        category="high_cap_mlcc",
        severity=Severity.HIGH,
        confidence=0.7,
    )
    _seed_review_source(low_confidence_reviewed_no_impact_id)
    low_confidence_hit_id = _seed_event(
        brand="Murata",
        category="resistor",
        severity=Severity.MEDIUM,
        confidence=0.7,
    )
    _seed_review_source(low_confidence_hit_id)
    _seed_project_with_items(low_confidence_hit_id)

    resp = client.get("/api/market-trends/actions")

    assert resp.status_code == 200
    review_actions = [action for action in resp.json()["actions"] if action["action_type"] == "review_event"]
    assert {action["event_ids"][0] for action in review_actions} == {low_confidence_hit_id}
    assert low_confidence_reviewed_no_impact_id not in {action["event_ids"][0] for action in review_actions}


def test_market_trend_endpoints_are_read_only_for_core_tables():
    _clean_trend_data()
    event_id = _seed_event(brand="TDK", category="high_cap_mlcc", severity=Severity.HIGH, confidence=0.7)
    _seed_review_source(event_id)
    _seed_project_with_items(event_id)
    before = _snapshot_trend_tables()

    endpoints = [
        ("/api/market-trends/summary", {}),
        ("/api/market-trends/timeline", {"days": 30}),
        ("/api/market-trends/validation", {}),
        ("/api/market-trends/actions", {}),
    ]
    for url, params in endpoints:
        resp = client.get(url, params=params)
        assert resp.status_code == 200

    assert _snapshot_trend_tables() == before
