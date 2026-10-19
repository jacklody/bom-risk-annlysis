from __future__ import annotations

from typing import Any

from app.services.upstream.intelligence_scoring import (
    IntelligenceEventInput,
    score_intelligence_event,
)


def _event_type_value(event: Any) -> str:
    event_type = getattr(event, "event_type", None)
    if hasattr(event_type, "value"):
        return event_type.value
    return str(event_type or "")


def _raw_text_from_payload(payload: dict) -> str:
    parts = [
        payload.get("title") or payload.get("raw_title") or "人工行情事件",
        payload.get("raw_text") or "",
    ]
    if payload.get("shortage_confirmed"):
        parts.append("缺货确认")
    if payload.get("increase_max_pct") is not None:
        parts.append(f"涨价幅度最高{payload.get('increase_max_pct')}%")
    if payload.get("lead_time_weeks") is not None:
        parts.append(f"交期约{payload.get('lead_time_weeks')}周")
    return "；".join(str(p) for p in parts if p)


def _severity_from_score_and_fact(confidence_score: int, payload: dict) -> str:
    if payload.get("shortage_confirmed") and payload.get("increase_max_pct", 0) >= 10:
        return "high"
    if confidence_score >= 80:
        return "high"
    if confidence_score >= 50:
        return "medium"
    return "low"


def build_market_event_from_manual_payload(payload: dict) -> dict:
    """把人工/媒体事件输入归一化为 MarketEvent 可入库字段。

    返回 dict 保持与现有 EventCollector._save_event(event_data) 兼容。
    额外附加 review_recommendation/can_trigger_high_risk，供 API 返回和审计使用。
    """
    source_type = payload.get("source_type") or "manual"
    increase_max_pct = payload.get("increase_max_pct")
    if increase_max_pct is None:
        increase_max_pct = payload.get("estimated_price_impact_pct")

    lead_time_weeks = payload.get("lead_time_weeks")
    if lead_time_weeks is None:
        lead_time_weeks = payload.get("estimated_lead_time_impact_weeks")

    score = score_intelligence_event(
        IntelligenceEventInput(
            source_type=source_type,
            title=payload.get("title") or payload.get("raw_title") or "人工行情事件",
            category=payload.get("category"),
            brand=payload.get("brand"),
            mpn=payload.get("mpn"),
            increase_max_pct=increase_max_pct,
            original_source_url=payload.get("source_url") or payload.get("original_source_url"),
            cross_validation_count=int(payload.get("cross_validation_count") or 0),
            confirmed_by_user=bool(payload.get("confirmed_by_user")),
            shortage_confirmed=bool(payload.get("shortage_confirmed")),
            lead_time_weeks=lead_time_weeks,
        )
    )

    event_type = payload.get("event_type") or "other"
    if payload.get("shortage_confirmed") and event_type == "other":
        event_type = "shortage"
    if increase_max_pct is not None:
        event_type = "price_increase"

    return {
        "source_name": "manual" if source_type == "manual" else source_type,
        "source_url": payload.get("source_url") or payload.get("original_source_url") or "",
        "raw_title": payload.get("title") or payload.get("raw_title") or "人工行情事件",
        "raw_text": _raw_text_from_payload({**payload, "increase_max_pct": increase_max_pct, "lead_time_weeks": lead_time_weeks}),
        "brand": payload.get("brand"),
        "category": payload.get("category"),
        "event_type": event_type,
        "severity": _severity_from_score_and_fact(score.confidence_score, {**payload, "increase_max_pct": increase_max_pct}),
        "confidence": round(score.confidence_score / 100, 3),
        "estimated_price_impact_pct": increase_max_pct,
        "estimated_lead_time_impact_weeks": lead_time_weeks,
        "review_recommendation": score.review_recommendation,
        "can_trigger_high_risk": score.can_trigger_high_risk,
        "confidence_reason": score.reason,
    }


def extract_market_facts_from_events(events: list[Any]) -> dict:
    """从命中事件中提取双轨风险引擎需要的市场事实。"""
    price_up_confirmed = False
    shortage_confirmed = False
    lead_time_weeks = None

    for event in events or []:
        event_type = _event_type_value(event)
        price_pct = getattr(event, "estimated_price_impact_pct", None)
        lead_time = getattr(event, "estimated_lead_time_impact_weeks", None)
        raw_text = (getattr(event, "raw_text", "") or "").lower()

        if event_type == "price_increase" or (price_pct is not None and price_pct > 0):
            price_up_confirmed = True
        if event_type == "shortage" or "缺货" in raw_text or "shortage" in raw_text:
            shortage_confirmed = True
        if lead_time is not None:
            lead_time_weeks = max(lead_time_weeks or 0, int(lead_time))

    result = {
        "price_up_confirmed": price_up_confirmed,
        "shortage_confirmed": shortage_confirmed,
    }
    if lead_time_weeks is not None:
        result["lead_time_weeks"] = lead_time_weeks
    return result
