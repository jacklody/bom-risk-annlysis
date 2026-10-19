from app.services.upstream.risk_context_builder import build_v32_context


class FakeItem:
    row_number = 1
    raw_part_number = "C3216X5R1A476M160AC"
    raw_brand = "TDK"
    normalized_brand = "TDK"
    raw_category = "capacitor"
    normalized_category = "high_cap_mlcc"
    raw_spec = "47uF 10V X5R 1206 MLCC"
    raw_qty = 10


class FakeEventType:
    value = "price_increase"


class FakeEvent:
    id = 9
    event_type = FakeEventType()
    source_name = "manual"
    raw_title = "TDK高容MLCC涨价缺货"
    raw_text = "TDK高容MLCC缺货涨价，交期16周"
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


def test_build_v32_context_for_high_cap_mlcc_item():
    context = build_v32_context(
        item=FakeItem(),
        events=[FakeEvent()],
        realtime_data={"total_stock": 0, "supplier_count": 1, "lead_time_days": 112},
        commonality={"has_multi_source": False},
    )

    assert context["v32_category"] == "high_cap_mlcc"
    assert context["v32_category_display"] == "高容MLCC"
    assert context["v32_risk_level"] in ["orange", "red"]
    assert context["v32_primary_track"] == "demand_supply"
    assert context["v32_risk_score"] > 0
    assert context["v32_track_scores"]["demand_supply"] > 0
    assert context["v32_evidence_chain"]
    assert "高容MLCC" in context["v32_evidence_summary"]


def test_build_v32_context_uses_normalized_category_when_raw_fields_are_empty():
    class NormalizedOnlyFilmItem:
        row_number = 2
        raw_part_number = "ECW-FD2W105K"
        raw_brand = "Panasonic"
        normalized_brand = "松下/Panasonic"
        raw_category = ""
        normalized_category = "Film"
        raw_spec = ""
        raw_qty = 5

    context = build_v32_context(
        item=NormalizedOnlyFilmItem(),
        events=[],
        realtime_data={},
        commonality={},
    )

    assert context["v32_category"] == "film_capacitor"
    assert context["v32_category_display"] == "薄膜电容"
    assert any(node["type"] == "category" and node["category"] == "film_capacitor" for node in context["v32_evidence_chain"])
