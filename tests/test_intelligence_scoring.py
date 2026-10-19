from app.services.upstream.intelligence_scoring import (
    IntelligenceEventInput,
    score_intelligence_event,
)


def test_single_wechat_rumor_without_fields_is_observation_only():
    event = IntelligenceEventInput(
        source_type="wechat",
        title="某类芯片即将涨价",
        category="ic",
        brand=None,
        increase_max_pct=None,
        original_source_url=None,
        cross_validation_count=0,
    )

    result = score_intelligence_event(event)

    assert result.review_recommendation == "observe"
    assert result.can_trigger_high_risk is False
    assert result.confidence_score < 50
    assert "单一公众号" in result.reason


def test_oem_price_notice_is_high_confidence():
    event = IntelligenceEventInput(
        source_type="official",
        title="原厂涨价通知",
        category="high_cap_mlcc",
        brand="Yageo",
        increase_max_pct=15,
        original_source_url="https://example.com/notice.pdf",
        cross_validation_count=1,
    )

    result = score_intelligence_event(event)

    assert result.review_recommendation in ["auto_confirm", "manual_confirm"]
    assert result.can_trigger_high_risk is True
    assert result.confidence_score >= 70


def test_media_report_with_partial_fields_requires_manual_confirm():
    event = IntelligenceEventInput(
        source_type="industry_media",
        title="高容MLCC供应趋紧，部分品牌交期拉长",
        category="high_cap_mlcc",
        brand="Murata",
        increase_max_pct=None,
        original_source_url="https://example.com/news",
        cross_validation_count=1,
    )

    result = score_intelligence_event(event)

    assert result.review_recommendation == "manual_confirm"
    assert result.can_trigger_high_risk is False
    assert 50 <= result.confidence_score < 80


def test_manual_confirmed_event_can_trigger_high_risk_when_complete():
    event = IntelligenceEventInput(
        source_type="manual",
        title="采购上传供应商高容MLCC缺货涨价通知",
        category="high_cap_mlcc",
        brand="TDK",
        increase_max_pct=20,
        original_source_url="file://notice.pdf",
        cross_validation_count=0,
        confirmed_by_user=True,
        shortage_confirmed=True,
    )

    result = score_intelligence_event(event)

    assert result.review_recommendation == "auto_confirm"
    assert result.can_trigger_high_risk is True
    assert result.confidence_score >= 80
