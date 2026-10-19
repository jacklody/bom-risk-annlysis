from fastapi.testclient import TestClient

from app.database import SessionLocal, init_db
from app.main import app
from app.models.event import EventType, MarketEvent, Severity

client = TestClient(app)


def _clean_events():
    init_db()
    db = SessionLocal()
    db.query(MarketEvent).delete()
    db.commit()
    db.close()


def _seed_event(
    *,
    brand: str,
    category: str,
    event_type: EventType,
    severity: Severity,
    is_active: int = 1,
    confidence: float = 0.8,
) -> int:
    db = SessionLocal()
    try:
        event = MarketEvent(
            source_name="测试来源",
            source_url="test://market-event",
            raw_text=f"{brand} {category} 行情通知",
            raw_title=f"{brand} {category} 通知",
            brand=brand,
            category=category,
            event_type=event_type,
            severity=severity,
            estimated_lead_time_impact_weeks=12,
            estimated_price_impact_pct=18.0,
            confidence=confidence,
            is_active=is_active,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event.id
    finally:
        db.close()


def test_list_events_filters_by_brand():
    _clean_events()
    _seed_event(
        brand="TDK",
        category="high_cap_mlcc",
        event_type=EventType.PRICE_INCREASE,
        severity=Severity.HIGH,
    )
    _seed_event(
        brand="Murata",
        category="high_cap_mlcc",
        event_type=EventType.SHORTAGE,
        severity=Severity.MEDIUM,
    )

    resp = client.get("/api/events/", params={"brand": "TDK"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["events"][0]["brand"] == "TDK"


def test_list_events_filters_by_category():
    _clean_events()
    _seed_event(
        brand="TDK",
        category="high_cap_mlcc",
        event_type=EventType.PRICE_INCREASE,
        severity=Severity.HIGH,
    )
    _seed_event(
        brand="TDK",
        category="resistor",
        event_type=EventType.SHORTAGE,
        severity=Severity.MEDIUM,
    )

    resp = client.get("/api/events/", params={"category": "high_cap_mlcc"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["events"][0]["category"] == "high_cap_mlcc"


def test_list_events_filters_by_event_type_and_severity():
    _clean_events()
    _seed_event(
        brand="TDK",
        category="high_cap_mlcc",
        event_type=EventType.PRICE_INCREASE,
        severity=Severity.HIGH,
    )
    _seed_event(
        brand="Murata",
        category="resistor",
        event_type=EventType.SHORTAGE,
        severity=Severity.MEDIUM,
    )

    resp = client.get("/api/events/", params={"event_type": "price_increase", "severity": "high"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["events"][0]["brand"] == "TDK"
    assert data["events"][0]["event_type"] == "price_increase"
    assert data["events"][0]["severity"] == "high"


def test_list_events_active_status_all_and_inactive():
    _clean_events()
    _seed_event(
        brand="TDK",
        category="mlcc",
        event_type=EventType.PRICE_INCREASE,
        severity=Severity.HIGH,
        is_active=1,
    )
    _seed_event(
        brand="Yageo",
        category="resistor",
        event_type=EventType.SHORTAGE,
        severity=Severity.LOW,
        is_active=0,
    )

    default_resp = client.get("/api/events/")
    assert default_resp.status_code == 200
    assert default_resp.json()["total"] == 1
    assert default_resp.json()["events"][0]["brand"] == "TDK"

    inactive_resp = client.get("/api/events/", params={"active_status": "inactive"})
    assert inactive_resp.status_code == 200
    assert inactive_resp.json()["total"] == 1
    assert inactive_resp.json()["events"][0]["brand"] == "Yageo"

    all_resp = client.get("/api/events/", params={"active_status": "all"})
    assert all_resp.status_code == 200
    assert all_resp.json()["total"] == 2


def test_list_events_filters_by_event_ids_for_traceable_action_jump():
    _clean_events()
    target_id = _seed_event(
        brand="TDK",
        category="high_cap_mlcc",
        event_type=EventType.PRICE_INCREASE,
        severity=Severity.HIGH,
    )
    _seed_event(
        brand="Murata",
        category="resistor",
        event_type=EventType.SHORTAGE,
        severity=Severity.MEDIUM,
    )

    resp = client.get("/api/events/", params={"active_status": "all", "event_ids": str(target_id)})

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["events"][0]["id"] == target_id
    assert data["events"][0]["brand"] == "TDK"


def test_get_event_returns_detail_fields():
    _clean_events()
    event_id = _seed_event(
        brand="TDK",
        category="high_cap_mlcc",
        event_type=EventType.LEAD_TIME,
        severity=Severity.CRITICAL,
        confidence=0.91,
    )

    resp = client.get(f"/api/events/{event_id}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == event_id
    assert data["brand"] == "TDK"
    assert data["category"] == "high_cap_mlcc"
    assert data["event_type"] == "lead_time"
    assert data["severity"] == "critical"
    assert data["confidence"] == 0.91
    assert data["raw_text_excerpt"]


def test_update_event_status_disables_event_and_hides_from_active_list():
    _clean_events()
    event_id = _seed_event(
        brand="TDK",
        category="high_cap_mlcc",
        event_type=EventType.PRICE_INCREASE,
        severity=Severity.HIGH,
        is_active=1,
    )

    resp = client.patch(f"/api/events/{event_id}/status", json={"action": "disable"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["event"]["id"] == event_id
    assert data["event"]["is_active"] == 0
    assert data["message"] == "事件已停用"

    active_resp = client.get("/api/events/")
    assert active_resp.status_code == 200
    assert active_resp.json()["total"] == 0

    all_resp = client.get("/api/events/", params={"active_status": "all"})
    assert all_resp.status_code == 200
    assert all_resp.json()["total"] == 1


def test_update_event_status_enables_event_again():
    _clean_events()
    event_id = _seed_event(
        brand="TDK",
        category="high_cap_mlcc",
        event_type=EventType.PRICE_INCREASE,
        severity=Severity.HIGH,
        is_active=0,
    )

    resp = client.patch(f"/api/events/{event_id}/status", json={"action": "enable"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["event"]["id"] == event_id
    assert data["event"]["is_active"] == 1
    assert data["message"] == "事件已启用"

    active_resp = client.get("/api/events/")
    assert active_resp.status_code == 200
    assert active_resp.json()["total"] == 1


def test_update_event_status_rejects_unknown_action():
    _clean_events()
    event_id = _seed_event(
        brand="TDK",
        category="high_cap_mlcc",
        event_type=EventType.PRICE_INCREASE,
        severity=Severity.HIGH,
    )

    resp = client.patch(f"/api/events/{event_id}/status", json={"action": "archive"})

    assert resp.status_code == 422


def test_get_event_impact_summarizes_projects_and_items():
    from app.models.bom import BomItem, BomProject, RiskLevel

    _clean_events()
    db = SessionLocal()
    db.query(BomItem).delete()
    db.query(BomProject).delete()
    db.commit()
    try:
        event = MarketEvent(
            source_name="测试来源",
            source_url="test://impact",
            raw_text="TDK MLCC 涨价缺货",
            raw_title="TDK MLCC 通知",
            brand="TDK",
            category="high_cap_mlcc",
            event_type=EventType.PRICE_INCREASE,
            severity=Severity.HIGH,
            confidence=0.9,
            is_active=1,
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        project = BomProject(filename="real_bom.xlsx", project_name="真实项目A", status="active", total_items=2)
        db.add(project)
        db.commit()
        db.refresh(project)

        db.add_all([
            BomItem(
                bom_upload_id=project.id,
                row_number=1,
                raw_part_number="C3225X5R1A226M250AC",
                raw_brand="TDK",
                raw_category="MLCC",
                normalized_brand="TDK",
                normalized_category="high_cap_mlcc",
                risk_level=RiskLevel.RED,
                risk_score=91,
                matched_event_ids=str(event.id),
            ),
            BomItem(
                bom_upload_id=project.id,
                row_number=2,
                raw_part_number="C1608X7R1H104K080AA",
                raw_brand="TDK",
                raw_category="MLCC",
                normalized_brand="TDK",
                normalized_category="high_cap_mlcc",
                risk_level=RiskLevel.YELLOW,
                risk_score=72,
                matched_event_ids=f"999,{event.id}",
            ),
        ])
        db.commit()
        event_id = event.id
    finally:
        db.close()

    resp = client.get(f"/api/events/{event_id}/impact")

    assert resp.status_code == 200
    data = resp.json()
    assert data["event_id"] == event_id
    assert data["project_count"] == 1
    assert data["item_count"] == 2
    assert data["risk_counts"] == {"red": 1, "yellow": 1, "green": 0, "gray": 0}
    assert data["projects"][0]["project_id"]
    assert data["projects"][0]["project_name"] == "真实项目A"
    assert data["projects"][0]["affected_item_count"] == 2
    assert data["projects"][0]["highest_risk_level"] == "red"


def test_get_event_source_signal_returns_review_context():
    from app.models.event import ExtractedMarketSignal, RawMarketNotice

    _clean_events()
    db = SessionLocal()
    db.query(ExtractedMarketSignal).delete()
    db.query(RawMarketNotice).delete()
    db.commit()
    try:
        event = MarketEvent(
            source_name="行情收件箱复核",
            source_url="market-inbox://review/1",
            raw_text="TDK 高容 MLCC 缺货涨价",
            raw_title="TDK MLCC 复核确认",
            brand="TDK",
            category="high_cap_mlcc",
            event_type=EventType.PRICE_INCREASE,
            severity=Severity.HIGH,
            confidence=0.85,
            is_active=1,
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        notice = RawMarketNotice(
            source_type="email",
            source_name="采购邮箱",
            source_url="mail://notice-001",
            title="TDK MLCC 缺货涨价邮件",
            raw_text="供应商确认 TDK 高容 MLCC 缺货，交期 16 周。",
            sender="buyer@example.com",
            parse_status="parsed",
        )
        db.add(notice)
        db.commit()
        db.refresh(notice)

        signal = ExtractedMarketSignal(
            raw_notice_id=notice.id,
            market_event_id=event.id,
            brand="TDK",
            category="high_cap_mlcc",
            event_type="price_increase",
            confidence=0.85,
            evidence_text="供应商确认缺货涨价",
            review_status="confirmed",
            reviewed_by="purchaser",
            review_notes="电话复核属实",
        )
        db.add(signal)
        db.commit()
        event_id = event.id
    finally:
        db.close()

    resp = client.get(f"/api/events/{event_id}/source-signal")

    assert resp.status_code == 200
    data = resp.json()
    assert data["event_id"] == event_id
    assert data["signal"]["review_status"] == "confirmed"
    assert data["signal"]["reviewed_by"] == "purchaser"
    assert data["signal"]["review_notes"] == "电话复核属实"
    assert data["signal"]["evidence_text"] == "供应商确认缺货涨价"
    assert data["raw_notice"]["source_type"] == "email"
    assert data["raw_notice"]["source_name"] == "采购邮箱"
    assert data["raw_notice"]["sender"] == "buyer@example.com"
    assert data["raw_notice"]["title"] == "TDK MLCC 缺货涨价邮件"
    assert "交期 16 周" in data["raw_notice"]["raw_text_excerpt"]
