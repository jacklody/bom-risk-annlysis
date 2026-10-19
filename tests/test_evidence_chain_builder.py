from app.services.upstream.category_classifier import classify_component_category
from app.services.upstream.dual_track_risk_engine import evaluate_dual_track_risk
from app.services.upstream.evidence_chain_builder import build_evidence_chain


class FakeItem:
    row_number = 1
    raw_part_number = "C3216X5R1A476M160AC"
    raw_brand = "TDK"
    raw_spec = "47uF 10V X5R 1206 MLCC"
    raw_category = "capacitor"


class FakeEvent:
    id = 7
    source_name = "manual"
    raw_title = "TDK高容MLCC涨价缺货"
    brand = "TDK"
    category = "high_cap_mlcc"
    estimated_price_impact_pct = 20
    estimated_lead_time_impact_weeks = 16

    def to_dict(self):
        return {
            "id": self.id,
            "source_name": self.source_name,
            "raw_title": self.raw_title,
            "brand": self.brand,
            "category": self.category,
            "estimated_price_impact_pct": self.estimated_price_impact_pct,
            "estimated_lead_time_impact_weeks": self.estimated_lead_time_impact_weeks,
        }


def test_build_evidence_chain_for_high_cap_mlcc_risk():
    category = classify_component_category(FakeItem.raw_spec, manufacturer="TDK")
    risk = evaluate_dual_track_risk(
        category="high_cap_mlcc",
        body_signals={"stock_down": True, "lead_time_weeks": 16},
        market_facts={"price_up_confirmed": True, "shortage_confirmed": True},
        material_signals={"ceramic_powder_pressure": True},
        buffers={"safety_stock_days": 0},
    )

    result = build_evidence_chain(
        item=FakeItem(),
        category_result=category,
        matched_events=[FakeEvent()],
        dual_track_result=risk,
        realtime_data={"total_stock": 0, "lead_time_days": 112},
        buffers={"safety_stock_days": 0},
    )

    assert result.summary
    assert any(node["type"] == "category" for node in result.chain)
    assert any(node["type"] == "market_event" for node in result.chain)
    assert any(node["type"] == "dual_track" for node in result.chain)
    assert any(node["type"] == "supply_snapshot" for node in result.chain)
    assert "高容MLCC" in result.summary
    assert result.action_suggestion


def test_information_insufficient_chain_has_gray_summary():
    category = classify_component_category("ABC123 custom module", manufacturer="Unknown")
    risk = evaluate_dual_track_risk(
        category="unknown",
        body_signals={},
        market_facts={},
        material_signals={},
        buffers={},
    )

    result = build_evidence_chain(
        item=FakeItem(),
        category_result=category,
        matched_events=[],
        dual_track_result=risk,
        realtime_data={},
        buffers={},
    )

    assert result.risk_level == "gray"
    assert "信息不足" in result.summary
    assert any(node["type"] == "information_status" for node in result.chain)
