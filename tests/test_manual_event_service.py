from app.services.upstream.manual_event_service import (
    build_market_event_from_manual_payload,
    extract_market_facts_from_events,
)


def test_manual_high_cap_mlcc_shortage_price_event_becomes_high_confidence_market_event():
    payload = {
        "title": "采购上传TDK高容MLCC缺货涨价通知",
        "category": "high_cap_mlcc",
        "brand": "TDK",
        "event_type": "price_increase",
        "increase_max_pct": 20,
        "shortage_confirmed": True,
        "source_url": "file://tdk-notice.pdf",
        "confirmed_by_user": True,
    }

    event_data = build_market_event_from_manual_payload(payload)

    assert event_data["source_name"] == "manual"
    assert event_data["category"] == "high_cap_mlcc"
    assert event_data["brand"] == "TDK"
    assert event_data["event_type"] == "price_increase"
    assert event_data["severity"] == "high"
    assert event_data["confidence"] >= 0.8
    assert event_data["estimated_price_impact_pct"] == 20
    assert "缺货" in event_data["raw_text"]
    assert event_data["review_recommendation"] == "auto_confirm"


def test_single_wechat_like_manual_payload_without_confirmation_is_observation_only():
    payload = {
        "source_type": "wechat",
        "title": "某类芯片即将涨价",
        "category": "ic",
    }

    event_data = build_market_event_from_manual_payload(payload)

    assert event_data["confidence"] < 0.5
    assert event_data["review_recommendation"] == "observe"
    assert event_data["can_trigger_high_risk"] is False


class FakeEventType:
    value = "price_increase"


class FakeEvent:
    event_type = FakeEventType()
    estimated_price_impact_pct = 15
    estimated_lead_time_impact_weeks = 16
    raw_text = "高容MLCC缺货涨价"


def test_extract_market_facts_from_manual_events():
    facts = extract_market_facts_from_events([FakeEvent()])

    assert facts["price_up_confirmed"] is True
    assert facts["shortage_confirmed"] is True
    assert facts["lead_time_weeks"] == 16
