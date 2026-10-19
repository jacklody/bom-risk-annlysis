from app.services.upstream.dual_track_risk_engine import evaluate_dual_track_risk


def test_high_cap_mlcc_shortage_becomes_orange_or_red():
    result = evaluate_dual_track_risk(
        category="high_cap_mlcc",
        body_signals={"stock_down": True, "lead_time_weeks": 16},
        market_facts={"price_up_confirmed": True, "shortage_confirmed": True},
        material_signals={"ceramic_powder_pressure": True},
        buffers={"safety_stock_days": 0},
    )

    assert result.risk_level in ["orange", "red"]
    assert result.primary_track == "demand_supply"
    assert "高容MLCC" in result.reason
    assert "demand_supply" in result.track_scores
    assert "material" in result.track_scores


def test_mcu_silicon_price_only_does_not_become_red():
    result = evaluate_dual_track_risk(
        category="mcu",
        body_signals={"stock_down": False, "lead_time_weeks": 8},
        market_facts={"price_up_confirmed": False},
        material_signals={"silicon_wafer_price_up": True},
        buffers={"safety_stock_days": 0},
    )

    assert result.risk_level != "red"
    assert result.primary_track != "material"
    assert "不能仅凭材料上涨直接红色预警" in result.reason


def test_pcb_copper_pressure_uses_material_track():
    result = evaluate_dual_track_risk(
        category="pcb",
        body_signals={"stock_down": False, "lead_time_weeks": 6},
        market_facts={"price_up_confirmed": False},
        material_signals={"copper_foil_price_up": True, "fiberglass_price_up": True},
        buffers={"safety_stock_days": 0},
    )

    assert result.primary_track == "material"
    assert result.risk_level in ["yellow", "orange"]
    assert "材料传导" in result.reason


def test_safety_stock_buffer_reduces_risk_level():
    without_buffer = evaluate_dual_track_risk(
        category="high_cap_mlcc",
        body_signals={"stock_down": True, "lead_time_weeks": 16},
        market_facts={"price_up_confirmed": True, "shortage_confirmed": True},
        material_signals={"ceramic_powder_pressure": True},
        buffers={"safety_stock_days": 0},
    )
    with_buffer = evaluate_dual_track_risk(
        category="high_cap_mlcc",
        body_signals={"stock_down": True, "lead_time_weeks": 16},
        market_facts={"price_up_confirmed": True, "shortage_confirmed": True},
        material_signals={"ceramic_powder_pressure": True},
        buffers={"safety_stock_days": 90},
    )

    assert with_buffer.total_score < without_buffer.total_score
    assert "缓冲" in with_buffer.reason


def test_no_signal_returns_information_insufficient_gray():
    result = evaluate_dual_track_risk(
        category="unknown",
        body_signals={},
        market_facts={},
        material_signals={},
        buffers={},
    )

    assert result.risk_level == "gray"
    assert result.primary_track == "information_insufficient"
