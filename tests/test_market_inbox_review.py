"""Test market inbox review queue."""
from fastapi.testclient import TestClient
from app.database import SessionLocal, init_db
from app.main import app
from app.models.event import ExtractedMarketSignal, RawMarketNotice

client = TestClient(app)


def _clear():
    init_db()
    db = SessionLocal()
    db.query(ExtractedMarketSignal).delete()
    db.query(RawMarketNotice).delete()
    db.commit()
    db.close()


def test_review_confirm_promotes_signal_to_event():
    _clear()
    db = SessionLocal()
    notice = RawMarketNotice(
        title="TDK高容MLCC涨价通知",
        raw_text="TDK C3225X5R1A226M250AC 涨价15% 交期延长至16周",
        source_type="email",
        source_name="TDK代理商",
        parse_status="need_review",
    )
    db.add(notice)
    db.commit()
    db.refresh(notice)
    signal = ExtractedMarketSignal(
        raw_notice_id=notice.id,
        brand="TDK",
        category="high_cap_mlcc",
        mpn="C3225X5R1A226M250AC",
        event_type="price_increase",
        increase_max_pct=15,
        lead_time_weeks=16,
        shortage_confirmed=1,
        confidence=0.72,
        confidence_reason="来源较可靠；明确品牌；明确品类",
        review_status="need_review",
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    db.close()

    resp = client.post(
        f"/api/market-inbox/review/{signal.id}",
        json={"action": "confirm", "notes": "与供应商电话确认，确实涨价缺货"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["signal"]["review_status"] == "confirmed"
    assert data["signal"]["review_notes"] == "与供应商电话确认，确实涨价缺货"
    assert data["event_created"] is True
    assert data["scan_summary"]["projects_scanned"] >= 0


def test_review_queue_returns_status_summary_counts():
    _clear()
    db = SessionLocal()
    notice = RawMarketNotice(
        title="多条复核线索",
        raw_text="多条行情线索需要复核",
        source_type="manual",
        source_name="采购录入",
        parse_status="parsed",
    )
    db.add(notice)
    db.commit()
    db.refresh(notice)
    for idx, status in enumerate(["need_review", "observation", "confirmed", "rejected"]):
        db.add(ExtractedMarketSignal(
            raw_notice_id=notice.id,
            brand="TDK",
            category="high_cap_mlcc",
            confidence=0.5 + idx * 0.1,
            confidence_reason="测试",
            review_status=status,
        ))
    db.commit()
    db.close()

    resp = client.get("/api/market-inbox/review-queue")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert data["summary"] == {
        "need_review": 1,
        "observation": 1,
        "confirmed": 1,
        "rejected": 1,
        "queue_total": 2,
    }


def test_review_reject_marks_signal_rejected():
    _clear()
    db = SessionLocal()
    notice = RawMarketNotice(
        title="MLCC涨价传闻",
        raw_text="群里说MLCC可能会涨价，暂无官方通知",
        source_type="wechat_mp",
        source_name="微信群转发",
        parse_status="need_review",
    )
    db.add(notice)
    db.commit()
    db.refresh(notice)
    signal = ExtractedMarketSignal(
        raw_notice_id=notice.id,
        confidence=0.55,
        confidence_reason="来源较可靠",
        review_status="need_review",
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    db.close()

    resp = client.post(
        f"/api/market-inbox/review/{signal.id}",
        json={"action": "reject", "notes": "已与供应商确认，暂无涨价计划"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["signal"]["review_status"] == "rejected"
    assert data["event_created"] is False
