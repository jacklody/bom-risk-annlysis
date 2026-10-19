from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class IntelligenceEventInput:
    source_type: str
    title: str
    category: str | None = None
    brand: str | None = None
    mpn: str | None = None
    increase_max_pct: float | None = None
    original_source_url: str | None = None
    cross_validation_count: int = 0
    confirmed_by_user: bool = False
    shortage_confirmed: bool = False
    lead_time_weeks: int | None = None


@dataclass(frozen=True)
class IntelligenceScoreResult:
    confidence_score: int
    source_score: int
    field_completeness_score: int
    cross_validation_score: int
    review_recommendation: str  # auto_confirm / manual_confirm / observe
    can_trigger_high_risk: bool
    reason: str
    tags: list[str] = field(default_factory=list)


_SOURCE_CREDIBILITY = {
    "official": 95,
    "manufacturer": 95,
    "supplier_notice": 90,
    "manual": 80,
    "authorized_distributor": 82,
    "industry_media": 68,
    "wechat": 45,
    "kol": 38,
    "unknown": 25,
}

_HIGH_RISK_CATEGORIES = {"high_cap_mlcc", "mlcc", "power_ic", "mcu", "pcb"}


def _field_completeness(event: IntelligenceEventInput) -> int:
    fields = [
        bool(event.category),
        bool(event.brand or event.mpn),
        event.increase_max_pct is not None or event.shortage_confirmed or event.lead_time_weeks is not None,
        bool(event.original_source_url),
    ]
    return int(sum(fields) / len(fields) * 100)


def _cross_validation_score(count: int) -> int:
    if count <= 0:
        return 0
    if count == 1:
        return 65
    if count == 2:
        return 85
    return 100


def score_intelligence_event(event: IntelligenceEventInput) -> IntelligenceScoreResult:
    source_type = (event.source_type or "unknown").lower()
    source_score = _SOURCE_CREDIBILITY.get(source_type, _SOURCE_CREDIBILITY["unknown"])
    field_score = _field_completeness(event)
    cross_score = _cross_validation_score(event.cross_validation_count)

    if event.confirmed_by_user:
        source_score = max(source_score, 90)
        cross_score = max(cross_score, 70)

    confidence = round(source_score * 0.35 + field_score * 0.35 + cross_score * 0.20)

    if event.increase_max_pct is not None and event.increase_max_pct >= 10:
        confidence += 7
    if event.shortage_confirmed:
        confidence += 8
    if event.category == "high_cap_mlcc":
        confidence += 5
    confidence = max(0, min(100, confidence))

    tags: list[str] = []
    reason_parts: list[str] = []

    single_wechat_rumor = (
        source_type == "wechat"
        and event.cross_validation_count == 0
        and not event.brand
        and not event.mpn
        and not event.original_source_url
        and event.increase_max_pct is None
    )
    if single_wechat_rumor:
        tags.append("single_wechat_rumor")
        reason_parts.append("单一公众号且缺少品牌、型号、原始出处和交叉验证")

    fact_confirmed = bool(
        event.increase_max_pct is not None
        or event.shortage_confirmed
        or (event.lead_time_weeks is not None and event.lead_time_weeks >= 12)
    )
    category_can_high = (event.category or "") in _HIGH_RISK_CATEGORIES
    can_trigger_high = confidence >= 70 and category_can_high and fact_confirmed and not single_wechat_rumor

    if confidence >= 80 and (event.confirmed_by_user or source_type in {"official", "manufacturer", "supplier_notice"}):
        recommendation = "auto_confirm"
    elif confidence >= 50:
        recommendation = "manual_confirm"
    else:
        recommendation = "observe"

    if single_wechat_rumor:
        recommendation = "observe"
        can_trigger_high = False
    elif not can_trigger_high and confidence >= 50:
        reason_parts.append("信息具备参考价值，但事实字段或交叉验证不足，不直接触发高风险")

    if not reason_parts:
        reason_parts.append("来源、字段完整度和交叉验证达到当前建议等级")

    return IntelligenceScoreResult(
        confidence_score=confidence,
        source_score=source_score,
        field_completeness_score=field_score,
        cross_validation_score=cross_score,
        review_recommendation=recommendation,
        can_trigger_high_risk=can_trigger_high,
        reason="；".join(reason_parts),
        tags=tags,
    )
