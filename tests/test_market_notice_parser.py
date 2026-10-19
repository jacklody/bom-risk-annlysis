from app.services.upstream.market_notice_parser import parse_market_notice


def test_parse_panasonic_film_capacitor_price_increase_notice_extracts_category():
    signals = parse_market_notice(
        raw_text="松下薄膜电容自2026年7月起，全线涨价，涨幅预期10%以上。",
        title="松下薄膜电容涨价通知",
        source_type="manual",
        source_name="行情收件箱",
    )

    assert len(signals) == 1
    signal = signals[0]
    assert signal.brand == "松下"
    assert signal.category == "film_capacitor"
    assert signal.event_type == "price_increase"
    assert signal.increase_max_pct == 10.0
    assert signal.review_status == "auto_confirmed"


def test_parse_common_category_price_shortage_and_lead_time_notices():
    cases = [
        ("尼吉康铝电解电容价格上调8%", "aluminum_electrolytic_capacitor", "price_increase"),
        ("KEMET 钽电容供需紧张，交期延长至20周", "tantalum", "lead_time"),
        ("英飞凌 MOSFET 缺货，预计涨价12%", "mosfet", "price_increase"),
        ("三菱 IGBT 功率模块 allocation，交期延长至26周", "power_module", "lead_time"),
        ("PCB 覆铜板成本上涨，线路板价格上调5%", "pcb", "price_increase"),
        ("ST MCU 供应紧张，交期延长至18周", "mcu", "lead_time"),
        ("美光 DRAM 内存缺货，价格上调10%", "dram", "price_increase"),
        ("华邦 NAND Flash 缺货，交期延长至16周", "nand", "lead_time"),
    ]

    for raw_text, expected_category, expected_type in cases:
        signal = parse_market_notice(raw_text, title="行情通知", source_type="manual")[0]
        assert signal.category == expected_category
        assert signal.event_type == expected_type
        assert signal.review_status in {"auto_confirmed", "need_review"}


def test_parse_high_cap_mlcc_notice_extracts_actionable_signal():
    signals = parse_market_notice(
        raw_text="TDK 高容MLCC C3225X5R1A226M250AC 缺货，预计涨价 10%-20%，交期延长至 16 周，即日起执行。",
        title="TDK高容MLCC缺货涨价通知",
        source_type="supplier_notice",
        source_name="TDK",
    )

    assert len(signals) == 1
    signal = signals[0]
    assert signal.brand == "TDK"
    assert signal.category == "high_cap_mlcc"
    assert signal.mpn == "C3225X5R1A226M250AC"
    assert signal.event_type == "price_increase"
    assert signal.increase_min_pct == 10
    assert signal.increase_max_pct == 20
    assert signal.lead_time_weeks == 16
    assert signal.shortage_confirmed is True
    assert signal.confidence >= 0.8
    assert signal.review_status == "auto_confirmed"
    assert "明确品牌" in signal.confidence_reason


def test_parse_wechat_rumor_is_not_auto_confirmed():
    signals = parse_market_notice(
        raw_text="群里说MLCC可能要涨价，大家关注一下，暂时没看到原厂通知。",
        title="微信群消息",
        source_type="wechat",
        source_name="微信群",
    )

    assert len(signals) == 1
    signal = signals[0]
    assert signal.category == "MLCC"
    assert signal.confidence < 0.8
    assert signal.review_status in {"need_review", "observation"}
    assert signal.event_type == "price_increase"
