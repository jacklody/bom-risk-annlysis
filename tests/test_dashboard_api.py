from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.database import SessionLocal, init_db
from app.main import app
from app.models.bom import BomItem, BomProject, RiskLevel
from app.models.dashboard_notification import DashboardNotificationRecord
from app.models.event import EventType, MarketEvent, Severity

client = TestClient(app)


def _clean_dashboard_data():
    init_db()
    db = SessionLocal()
    db.query(DashboardNotificationRecord).delete()
    db.query(BomItem).delete()
    db.query(BomProject).delete()
    db.query(MarketEvent).delete()
    db.commit()
    db.close()


def _seed_dashboard_project():
    db = SessionLocal()
    try:
        project = BomProject(
            filename="scheme-b-demo.xlsx",
            project_name="方案B演示项目",
            status="active",
            total_items=3,
            items_analyzed=3,
            items_red=1,
            items_yellow=1,
            items_green=1,
            items_gray=0,
            new_red_count=1,
            new_yellow_count=2,
            last_analysis_at=datetime.now(timezone.utc),
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        event = MarketEvent(
            source_name="采购邮箱",
            source_url="test://dashboard-event",
            raw_title="ST MCU 交期延长",
            raw_text="ST MCU 交期延长，价格上涨",
            brand="ST",
            category="MCU",
            event_type=EventType.LEAD_TIME,
            severity=Severity.HIGH,
            confidence=0.86,
            created_at=datetime.now(timezone.utc) - timedelta(days=2),
            is_active=1,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        db.add_all([
            BomItem(
                bom_upload_id=project.id,
                row_number=1,
                raw_part_number="STM32F103C8T6",
                raw_brand="ST",
                raw_category="MCU",
                normalized_category="MCU",
                risk_level=RiskLevel.RED,
                risk_score=92,
                matched_event_ids=str(event.id),
                total_stock=0,
                supplier_count=1,
                lead_time_days=56,
                procurement_suggestion="建议锁单并准备替代料。",
            ),
            BomItem(
                bom_upload_id=project.id,
                row_number=2,
                raw_part_number="C-MLCC-001",
                raw_brand="TDK",
                raw_category="MLCC",
                normalized_category="MLCC",
                risk_level=RiskLevel.YELLOW,
                risk_score=66,
                matched_event_ids=str(event.id),
                total_stock=300,
                supplier_count=2,
                lead_time_days=28,
                procurement_suggestion="建议观察价格变化。",
            ),
            BomItem(
                bom_upload_id=project.id,
                row_number=3,
                raw_part_number="R-SAFE-001",
                raw_brand="Yageo",
                raw_category="电阻",
                normalized_category="电阻",
                risk_level=RiskLevel.GREEN,
                risk_score=20,
            ),
        ])
        db.commit()
        return project.id, event.id
    finally:
        db.close()


def test_dashboard_summary_returns_overview_project_category_event_and_actions():
    _clean_dashboard_data()
    project_id, event_id = _seed_dashboard_project()

    resp = client.get("/api/dashboard/summary")

    assert resp.status_code == 200
    data = resp.json()
    assert data["overview"]["project_count"] == 1
    assert data["overview"]["high_risk_project_count"] == 1
    assert data["overview"]["red_item_count"] == 1
    assert data["overview"]["active_event_count_30d"] == 1
    assert data["overview"]["pending_action_count"] >= 1
    assert data["project_risks"][0]["project_id"] == project_id
    assert data["project_risks"][0]["risk_counts"]["red"] == 1
    assert data["category_risks"][0]["category"] in {"MCU", "MLCC"}
    assert data["category_risks"][0]["related_event_ids"] == [event_id]
    assert data["category_risks"][0]["target_query"] == {"event_ids": str(event_id)}
    assert data["recent_events"][0]["id"] == event_id
    assert data["recent_events"][0]["impact_item_count"] == 2
    assert data["risk_changes"]["new_red_item_count"] == 1
    assert data["risk_changes"]["new_yellow_item_count"] == 2
    assert data["risk_changes"]["changed_project_count"] == 1
    assert data["risk_changes"]["recent_event_count_7d"] == 1
    assert data["risk_changes"]["notification_ready"] is True
    assert "方案B演示项目新增红色风险1项、橙色风险0项、黄色风险2项" in data["risk_changes"]["notification_summary"]
    assert data["risk_changes"]["projects"][0]["project_id"] == project_id
    assert data["risk_changes"]["projects"][0]["target_route"] == f"/projects/{project_id}"
    assert data["risk_changes"]["events"][0]["id"] == event_id
    assert data["risk_changes"]["events"][0]["target_query"] == {"event_ids": str(event_id)}
    assert "supply_sources" in data
    assert data["generated_at"]


def test_dashboard_summary_empty_state_is_stable():
    _clean_dashboard_data()

    resp = client.get("/api/dashboard/summary")

    assert resp.status_code == 200
    data = resp.json()
    assert data["overview"]["project_count"] == 0
    assert data["project_risks"] == []
    assert data["category_risks"] == []
    assert data["recent_events"] == []
    assert data["trend_actions"] == []
    assert data["risk_changes"]["new_red_item_count"] == 0
    assert data["risk_changes"]["new_yellow_item_count"] == 0
    assert data["risk_changes"]["changed_project_count"] == 0
    assert data["risk_changes"]["recent_event_count_7d"] == 0
    assert data["risk_changes"]["notification_ready"] is False
    assert data["risk_changes"]["projects"] == []
    assert data["risk_changes"]["events"] == []


def test_dashboard_notification_preview_uses_risk_changes_for_manual_channel():
    _clean_dashboard_data()
    project_id, event_id = _seed_dashboard_project()

    resp = client.get("/api/dashboard/notification/preview")

    assert resp.status_code == 200
    data = resp.json()
    assert data["channel"] == "manual"
    assert data["ready"] is True
    assert data["subject"] == "BOM风险变化提醒：新增红色风险1项，橙色风险0项，黄色风险2项"
    assert "方案B演示项目新增红色风险1项、橙色风险0项、黄色风险2项" in data["body"]
    assert data["risk_changes"]["projects"][0]["project_id"] == project_id
    assert data["risk_changes"]["events"][0]["id"] == event_id
    assert data["actions"][0]["label"] == "查看风险仪表盘"
    assert data["actions"][0]["target_route"] == "/dashboard"


def test_dashboard_notification_dispatch_records_manual_delivery_without_external_channel():
    _clean_dashboard_data()
    _seed_dashboard_project()

    resp = client.post("/api/dashboard/notification/dispatch", json={"channel": "manual"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "prepared"
    assert data["channel"] == "manual"
    assert data["delivered"] is False
    assert data["external_delivery"] is False
    assert data["preview"]["ready"] is True
    assert "请在正式通知通道接入后发送" in data["message"]


def test_dashboard_notification_dispatch_persists_history_and_suppresses_duplicate_key():
    _clean_dashboard_data()
    _seed_dashboard_project()

    first = client.post(
        "/api/dashboard/notification/dispatch",
        json={"channel": "manual", "idempotency_key": "daily-risk-20260630"},
    )
    second = client.post(
        "/api/dashboard/notification/dispatch",
        json={"channel": "manual", "idempotency_key": "daily-risk-20260630"},
    )
    history = client.get("/api/dashboard/notification/history")

    assert first.status_code == 200
    first_data = first.json()
    assert first_data["status"] == "prepared"
    assert first_data["record_id"]
    assert first_data["deduplicated"] is False

    assert second.status_code == 200
    second_data = second.json()
    assert second_data["status"] == "suppressed"
    assert second_data["deduplicated"] is True
    assert second_data["duplicated_from_record_id"] == first_data["record_id"]

    assert history.status_code == 200
    rows = history.json()["records"]
    record = next(row for row in rows if row["id"] == first_data["record_id"])
    assert record["channel"] == "manual"
    assert record["status"] == "prepared"
    assert record["idempotency_key"] == "daily-risk-20260630"
    assert record["subject"] == "BOM风险变化提醒：新增红色风险1项，橙色风险0项，黄色风险2项"
    assert record["delivered"] is False


def test_dashboard_notification_channels_returns_safe_channel_statuses():
    _clean_dashboard_data()

    resp = client.get("/api/dashboard/notification/channels")

    assert resp.status_code == 200
    channels = resp.json()["channels"]
    by_channel = {row["channel"]: row for row in channels}
    assert by_channel["manual"]["enabled"] is True
    assert by_channel["manual"]["configured"] is True
    assert by_channel["manual"]["external_delivery"] is False
    assert by_channel["mock"]["enabled"] is True
    assert by_channel["mock"]["configured"] is True
    assert by_channel["mock"]["external_delivery"] is True
    assert by_channel["email"]["enabled"] is False
    assert by_channel["email"]["configured"] is False
    assert by_channel["email"]["status"] == "not_configured"
    assert by_channel["feishu"]["status"] == "not_configured"
    assert by_channel["wecom"]["status"] == "not_configured"


def test_dashboard_notification_mock_channel_marks_record_as_sent():
    _clean_dashboard_data()
    _seed_dashboard_project()

    resp = client.post(
        "/api/dashboard/notification/dispatch",
        json={"channel": "mock", "idempotency_key": "mock-risk-20260630"},
    )
    history = client.get("/api/dashboard/notification/history")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "sent"
    assert data["channel"] == "mock"
    assert data["delivered"] is True
    assert data["external_delivery"] is True
    assert data["failure_reason"] is None
    assert data["recipient_summary"] == "测试收件人"
    assert data["delivered_at"]

    rows = history.json()["records"]
    record = next(row for row in rows if row["id"] == data["record_id"])
    assert record["status"] == "sent"
    assert record["provider"] == "mock"
    assert record["delivered"] is True
    assert record["external_delivery"] is True
    assert record["recipient_summary"] == "测试收件人"
    assert record["retry_count"] == 0
    assert record["delivered_at"]


def test_dashboard_notification_unconfigured_real_channel_is_blocked_without_delivery():
    _clean_dashboard_data()
    _seed_dashboard_project()

    resp = client.post(
        "/api/dashboard/notification/dispatch",
        json={"channel": "email", "idempotency_key": "email-risk-20260630"},
    )
    history = client.get("/api/dashboard/notification/history")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "blocked"
    assert data["channel"] == "email"
    assert data["delivered"] is False
    assert data["external_delivery"] is False
    assert data["failure_reason"] == "email 通道尚未配置，已阻断外发。"
    assert data["recipient_summary"] == "未配置收件人"
    assert data["delivered_at"] is None

    rows = history.json()["records"]
    record = next(row for row in rows if row["id"] == data["record_id"])
    assert record["status"] == "blocked"
    assert record["provider"] == "email"
    assert record["delivered"] is False
    assert record["external_delivery"] is False
    assert record["failure_reason"] == "email 通道尚未配置，已阻断外发。"


def test_dashboard_notification_email_channel_available_when_smtp_configured(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "notification_email_enabled", True)
    monkeypatch.setattr(settings, "notification_email_smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "notification_email_smtp_port", 587)
    monkeypatch.setattr(settings, "notification_email_sender", "notice@example.com")
    monkeypatch.setattr(settings, "notification_email_recipients", "buyer@example.com,pm@example.com")

    resp = client.get("/api/dashboard/notification/channels")

    assert resp.status_code == 200
    by_channel = {row["channel"]: row for row in resp.json()["channels"]}
    assert by_channel["email"]["enabled"] is True
    assert by_channel["email"]["configured"] is True
    assert by_channel["email"]["status"] == "available"
    assert by_channel["email"]["message"] == "邮件通道已配置，可发送真实邮件通知。"


def test_dashboard_notification_email_dispatch_sends_smtp_and_records_history(monkeypatch):
    from app.config import settings
    import app.services.dashboard_notification as notification_service

    _clean_dashboard_data()
    _seed_dashboard_project()

    sent_messages = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            self.host = host
            self.port = port
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def starttls(self):
            self.started_tls = True

        def login(self, username, password):
            self.username = username
            self.password = password

        def send_message(self, message):
            sent_messages.append(message)

    monkeypatch.setattr(settings, "notification_email_enabled", True)
    monkeypatch.setattr(settings, "notification_email_smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "notification_email_smtp_port", 587)
    monkeypatch.setattr(settings, "notification_email_username", "notice@example.com")
    monkeypatch.setattr(settings, "notification_email_password", "secret-token")
    monkeypatch.setattr(settings, "notification_email_sender", "notice@example.com")
    monkeypatch.setattr(settings, "notification_email_recipients", "buyer@example.com,pm@example.com")
    monkeypatch.setattr(settings, "notification_email_use_tls", True)
    monkeypatch.setattr(notification_service.smtplib, "SMTP", FakeSMTP)

    resp = client.post(
        "/api/dashboard/notification/dispatch",
        json={"channel": "email", "idempotency_key": "email-smtp-success-20260630"},
    )
    history = client.get("/api/dashboard/notification/history")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "sent"
    assert data["channel"] == "email"
    assert data["delivered"] is True
    assert data["external_delivery"] is True
    assert data["provider"] == "email"
    assert data["recipient_summary"] == "2 个收件人"
    assert data["failure_reason"] is None
    assert data["delivered_at"]
    assert len(sent_messages) == 1
    assert sent_messages[0]["Subject"] == "BOM风险变化提醒：新增红色风险1项，橙色风险0项，黄色风险2项"
    assert sent_messages[0]["From"] == "notice@example.com"
    assert sent_messages[0]["To"] == "buyer@example.com, pm@example.com"
    assert "secret-token" not in str(data)
    assert "secret-token" not in str(history.json())

    rows = history.json()["records"]
    record = next(row for row in rows if row["id"] == data["record_id"])
    assert record["status"] == "sent"
    assert record["provider"] == "email"
    assert record["recipient_summary"] == "2 个收件人"


def test_dashboard_notification_email_dispatch_records_smtp_failure(monkeypatch):
    from app.config import settings
    import app.services.dashboard_notification as notification_service

    _clean_dashboard_data()
    _seed_dashboard_project()

    class FailingSMTP:
        def __init__(self, host, port, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def starttls(self):
            pass

        def login(self, username, password):
            pass

        def send_message(self, message):
            raise RuntimeError("network down")

    monkeypatch.setattr(settings, "notification_email_enabled", True)
    monkeypatch.setattr(settings, "notification_email_smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "notification_email_smtp_port", 587)
    monkeypatch.setattr(settings, "notification_email_sender", "notice@example.com")
    monkeypatch.setattr(settings, "notification_email_recipients", "buyer@example.com")
    monkeypatch.setattr(settings, "notification_email_use_tls", True)
    monkeypatch.setattr(notification_service.smtplib, "SMTP", FailingSMTP)

    resp = client.post(
        "/api/dashboard/notification/dispatch",
        json={"channel": "email", "idempotency_key": "email-smtp-failed-20260630"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "failed"
    assert data["delivered"] is False
    assert data["external_delivery"] is True
    assert data["provider"] == "email"
    assert data["recipient_summary"] == "1 个收件人"
    assert data["failure_reason"] == "SMTP发送失败：network down"
    assert data["delivered_at"] is None
