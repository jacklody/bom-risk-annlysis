import pathlib

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal, init_db
from app.main import app
from app.models.bom import BomItem, BomProject
from app.models.event import ExtractedMarketSignal, MarketEvent, RawMarketNotice

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    init_db()
    db = SessionLocal()
    db.query(ExtractedMarketSignal).delete()
    db.query(RawMarketNotice).delete()
    db.query(BomItem).delete()
    db.query(BomProject).delete()
    db.query(MarketEvent).delete()
    db.commit()
    db.close()
    yield


def _sample_bom_path() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[1] / "demo" / "sample-bom-v32.csv"


def _upload_sample_bom() -> int:
    sample_path = _sample_bom_path()
    with sample_path.open("rb") as f:
        resp = client.post(
            "/api/bom/upload",
            files={"file": (sample_path.name, f, "text/csv")},
            data={"project_name": "v3.3收件箱影响扫描BOM"},
        )
    assert resp.status_code == 200
    return resp.json()["upload_id"]


def test_submit_raw_market_notice_extracts_event_and_scans_history_bom():
    _upload_sample_bom()

    resp = client.post("/api/market-inbox/submit", json={
        "title": "TDK高容MLCC缺货涨价通知",
        "raw_text": "TDK 高容MLCC C3225X5R1A226M250AC 缺货，预计涨价 10%-20%，交期延长至 16 周，即日起执行。",
        "source_type": "email",
        "source_name": "TDK代理商邮件",
        "source_url": "mail://tdk-notice-001",
        "sender": "supplier@example.com",
        "auto_scan": True,
    })

    assert resp.status_code == 200
    data = resp.json()
    assert data["notice"]["parse_status"] == "parsed"
    assert data["signals"][0]["brand"] == "TDK"
    assert data["signals"][0]["category"] == "high_cap_mlcc"
    assert data["signals"][0]["mpn"] == "C3225X5R1A226M250AC"
    assert data["signals"][0]["review_status"] == "auto_confirmed"
    assert data["events_created"] == 1
    assert data["scan_summary"]["projects_scanned"] >= 1
    assert data["scan_summary"]["affected_projects"] >= 1
    assert data["scan_summary"]["top_impacted_items"]

    db = SessionLocal()
    try:
        assert db.query(RawMarketNotice).count() == 1
        assert db.query(ExtractedMarketSignal).count() == 1
        assert db.query(MarketEvent).count() == 1
    finally:
        db.close()


def test_panasonic_film_capacitor_price_notice_scans_matching_history_bom():
    db = SessionLocal()
    try:
        project = BomProject(
            filename="panasonic-film.xlsx",
            project_name="松下薄膜电容BOM",
            status="active",
            total_items=1,
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        item = BomItem(
            bom_upload_id=project.id,
            row_number=1,
            raw_part_number="ECW-FD2W105K",
            raw_brand="Panasonic",
            normalized_brand="松下/Panasonic",
            raw_category="Film",
            raw_spec="薄膜电容 1uF 450V",
            normalized_category=None,
            risk_level="green",
            risk_score=0,
        )
        db.add(item)
        db.commit()
    finally:
        db.close()

    resp = client.post("/api/market-inbox/submit", json={
        "title": "松下薄膜电容涨价通知",
        "raw_text": "松下薄膜电容自2026年7月起，全线涨价，涨幅预期10%以上。",
        "source_type": "manual",
        "source_name": "行情收件箱",
        "auto_scan": True,
    })

    assert resp.status_code == 200
    data = resp.json()
    assert data["signals"][0]["brand"] == "松下"
    assert data["signals"][0]["category"] == "film_capacitor"
    assert data["events_created"] == 1
    assert data["scan_summary"]["affected_projects"] == 1
    assert data["scan_summary"]["top_impacted_items"][0]["mpn"] == "ECW-FD2W105K"

    db = SessionLocal()
    try:
        item = db.query(BomItem).filter(BomItem.raw_part_number == "ECW-FD2W105K").first()
        assert item.risk_level.value in {"yellow", "red"}
        assert "price_increase" in item.risk_reason or "涨价" in item.risk_reason
        assert item.matched_event_ids
    finally:
        db.close()


def test_panasonic_film_capacitor_notice_does_not_hit_other_brand_film_capacitor():
    db = SessionLocal()
    try:
        project = BomProject(
            filename="tdk-film.xlsx",
            project_name="其他品牌薄膜电容BOM",
            status="active",
            total_items=1,
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        item = BomItem(
            bom_upload_id=project.id,
            row_number=1,
            raw_part_number="B32674D105K",
            raw_brand="TDK",
            normalized_brand="TDK",
            raw_category="Film",
            raw_spec="薄膜电容 1uF 450V",
            normalized_category=None,
            risk_level="green",
            risk_score=0,
        )
        db.add(item)
        db.commit()
    finally:
        db.close()

    resp = client.post("/api/market-inbox/submit", json={
        "title": "松下薄膜电容涨价通知",
        "raw_text": "松下薄膜电容自2026年7月起，全线涨价，涨幅预期10%以上。",
        "source_type": "manual",
        "source_name": "行情收件箱",
        "auto_scan": True,
    })

    assert resp.status_code == 200
    data = resp.json()
    assert data["signals"][0]["brand"] == "松下"
    assert data["signals"][0]["category"] == "film_capacitor"
    assert data["scan_summary"]["affected_projects"] == 0

    db = SessionLocal()
    try:
        item = db.query(BomItem).filter(BomItem.raw_part_number == "B32674D105K").first()
        assert item.risk_level.value == "green"
        assert not item.matched_event_ids
    finally:
        db.close()


def test_low_confidence_wechat_notice_is_saved_but_not_promoted_to_event():
    resp = client.post("/api/market-inbox/submit", json={
        "title": "微信群消息",
        "raw_text": "群里说MLCC可能要涨价，大家关注一下，暂时没看到原厂通知。",
        "source_type": "wechat",
        "source_name": "微信群",
        "auto_scan": False,
    })

    assert resp.status_code == 200
    data = resp.json()
    assert data["notice"]["parse_status"] in {"need_review", "parsed"}
    assert data["signals"][0]["review_status"] in {"need_review", "observation"}
    assert data["events_created"] == 0

    db = SessionLocal()
    try:
        assert db.query(RawMarketNotice).count() == 1
        assert db.query(ExtractedMarketSignal).count() == 1
        assert db.query(MarketEvent).count() == 0
    finally:
        db.close()


def test_review_queue_includes_raw_notice_context_for_audit():
    resp = client.post("/api/market-inbox/submit", json={
        "title": "微信群MLCC涨价线索",
        "raw_text": "微信群里转发：TDK MLCC 可能下月涨价，但暂未看到原厂正式通知，需要采购复核。",
        "source_type": "wechat",
        "source_name": "采购微信群",
        "sender": "采购同事A",
        "auto_scan": False,
    })
    assert resp.status_code == 200

    queue_resp = client.get("/api/market-inbox/review-queue")

    assert queue_resp.status_code == 200
    data = queue_resp.json()
    assert data["total"] == 1
    signal = data["signals"][0]
    assert signal["raw_notice_title"] == "微信群MLCC涨价线索"
    assert signal["raw_notice_source_type"] == "wechat"
    assert signal["raw_notice_source_name"] == "采购微信群"
    assert signal["raw_notice_sender"] == "采购同事A"
    assert "暂未看到原厂正式通知" in signal["raw_notice_excerpt"]
