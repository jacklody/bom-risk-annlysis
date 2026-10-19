from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.upstream.propagation_rules import (
    DEMAND_SUPPLY_SIGNAL_WEIGHTS,
    MATERIAL_SIGNAL_WEIGHTS,
    get_category_model,
)


@dataclass(frozen=True)
class DualTrackRiskResult:
    category: str
    risk_level: str
    total_score: int
    primary_track: str
    track_scores: dict[str, int]
    reason: str
    evidence: list[str] = field(default_factory=list)


def _material_score(material_signals: dict[str, Any]) -> tuple[int, list[str]]:
    score = 0
    evidence: list[str] = []
    for key, weight in MATERIAL_SIGNAL_WEIGHTS.items():
        if material_signals.get(key):
            score += weight
            evidence.append(key)
    return min(score, 100), evidence


def _demand_supply_score(body_signals: dict[str, Any], market_facts: dict[str, Any]) -> tuple[int, list[str]]:
    score = 0
    evidence: list[str] = []

    if body_signals.get("stock_down"):
        score += DEMAND_SUPPLY_SIGNAL_WEIGHTS["stock_down"]
        evidence.append("stock_down")
    if market_facts.get("price_up_confirmed"):
        score += DEMAND_SUPPLY_SIGNAL_WEIGHTS["price_up_confirmed"]
        evidence.append("price_up_confirmed")
    if market_facts.get("shortage_confirmed"):
        score += DEMAND_SUPPLY_SIGNAL_WEIGHTS["shortage_confirmed"]
        evidence.append("shortage_confirmed")

    lead_time_weeks = body_signals.get("lead_time_weeks")
    if isinstance(lead_time_weeks, (int, float)):
        if lead_time_weeks >= 12:
            score += DEMAND_SUPPLY_SIGNAL_WEIGHTS["lead_time_long"]
            evidence.append("lead_time_long")
        elif lead_time_weeks >= 8:
            score += DEMAND_SUPPLY_SIGNAL_WEIGHTS["lead_time_medium"]
            evidence.append("lead_time_medium")

    return min(score, 100), evidence


def _buffer_score(buffers: dict[str, Any]) -> tuple[int, list[str]]:
    safety_stock_days = buffers.get("safety_stock_days", 0) or 0
    evidence: list[str] = []
    score = 0
    if safety_stock_days >= 90:
        score += 22
        evidence.append("safety_stock_90d")
    elif safety_stock_days >= 30:
        score += 10
        evidence.append("safety_stock_30d")
    if buffers.get("multi_source_available"):
        score += 10
        evidence.append("multi_source_available")
    # v3.3: supplier_count 缓冲因子
    supplier_count = buffers.get("supplier_count", 0) or 0
    if supplier_count >= 3:
        score += 15
        evidence.append("multi_supplier_3plus")
    elif supplier_count == 0:
        score -= 10
        evidence.append("single_supplier_risk")
    return min(score, 35), evidence


def _level(score: int) -> str:
    if score >= 80:
        return "red"
    if score >= 60:
        return "orange"
    if score >= 35:
        return "yellow"
    if score > 0:
        return "green"
    return "gray"


def evaluate_dual_track_risk(
    category: str,
    body_signals: dict[str, Any] | None = None,
    market_facts: dict[str, Any] | None = None,
    material_signals: dict[str, Any] | None = None,
    buffers: dict[str, Any] | None = None,
) -> DualTrackRiskResult:
    body_signals = body_signals or {}
    market_facts = market_facts or {}
    material_signals = material_signals or {}
    buffers = buffers or {}

    # ── v3.3: 生命周期状态直接升级 ──
    lifecycle = body_signals.get("lifecycle_status", "Unknown")
    if lifecycle and str(lifecycle).upper() in ("EOL", "END_OF_LIFE"):
        return DualTrackRiskResult(
            category=category,
            risk_level="red",
            total_score=95,
            primary_track="lifecycle",
            track_scores={"lifecycle_eol": 95},
            reason=f"物料生命周期状态为 EOL/End-of-Life，直接判定极高风险",
            evidence=[f"lifecycle={lifecycle}"],
        )
    if lifecycle and str(lifecycle).upper() in ("NRND", "NOT_RECOMMENDED", "OBSOLETE"):
        return DualTrackRiskResult(
            category=category,
            risk_level="orange",
            total_score=80,
            primary_track="lifecycle",
            track_scores={"lifecycle_obsolete": 80},
            reason=f"物料生命周期状态为 {lifecycle}，建议立即切换替代料",
            evidence=[f"lifecycle={lifecycle}"],
        )

    model = get_category_model(category)
    material_raw, material_evidence = _material_score(material_signals)
    demand_raw, demand_evidence = _demand_supply_score(body_signals, market_facts)
    buffer, buffer_evidence = _buffer_score(buffers)

    material_weighted = round(material_raw * model["material"])
    demand_weighted = round(demand_raw * model["demand_supply"])
    total = max(0, min(100, material_weighted + demand_weighted - buffer))

    track_scores = {
        "material": material_weighted,
        "demand_supply": demand_weighted,
        "buffer": buffer,
    }

    if material_raw == 0 and demand_raw == 0:
        return DualTrackRiskResult(
            category=category,
            risk_level="gray",
            total_score=0,
            primary_track="information_insufficient",
            track_scores=track_scores,
            reason="信息不足：未发现材料传导或供需事实信号",
            evidence=[],
        )

    primary_track = "material" if material_weighted > demand_weighted else "demand_supply"
    reason_parts: list[str] = []
    display = model["display"]

    # IC类材料传导弱约束：单一硅片涨价不能直接红色预警，且不以材料轨为主。
    ic_material_only = (
        category in {"mcu", "power_ic"}
        and bool(material_evidence)
        and not market_facts.get("price_up_confirmed")
        and not market_facts.get("shortage_confirmed")
        and not body_signals.get("stock_down")
    )
    if ic_material_only:
        total = min(total, 34)
        primary_track = "demand_supply" if demand_weighted > 0 else "information_insufficient"
        reason_parts.append("IC类不能仅凭材料上涨直接红色预警")

    if primary_track == "material":
        reason_parts.append(f"{display}材料传导信号占主导")
    elif primary_track == "demand_supply":
        reason_parts.append(f"{display}供需信号占主导")

    if category == "high_cap_mlcc" and (market_facts.get("price_up_confirmed") or market_facts.get("shortage_confirmed")):
        reason_parts.append("高容MLCC已纳入涨价缺货重点风险品类")

    if buffer > 0:
        reason_parts.append("存在安全库存或多源供应缓冲，已降低风险分")

    if not reason_parts:
        reason_parts.append("双轨信号已形成风险评分")

    evidence = material_evidence + demand_evidence + buffer_evidence

    return DualTrackRiskResult(
        category=category,
        risk_level=_level(total),
        total_score=total,
        primary_track=primary_track,
        track_scores=track_scores,
        reason="；".join(reason_parts),
        evidence=evidence,
    )
