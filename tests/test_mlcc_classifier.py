from app.services.upstream.mlcc_classifier import classify_mlcc


def test_identifies_high_cap_mlcc_22uf_25v_0805():
    result = classify_mlcc("22uF 25V X7R 0805 MLCC")

    assert result.is_mlcc is True
    assert result.high_capacitance_flag is True
    assert result.capacitance == "22uF"
    assert result.voltage == "25V"
    assert result.dielectric == "X7R"
    assert result.package_size == "0805"
    assert result.category == "high_cap_mlcc"


def test_identifies_high_cap_mlcc_47uf_10v_0603_without_mlcc_word():
    result = classify_mlcc("47uF 10V X5R 0603")

    assert result.is_mlcc is True
    assert result.high_capacitance_flag is True
    assert result.category == "high_cap_mlcc"


def test_does_not_mark_100nf_as_high_cap_mlcc():
    result = classify_mlcc("100nF 50V X7R 0603")

    assert result.is_mlcc is True
    assert result.high_capacitance_flag is False
    assert result.category == "mlcc"


def test_c0g_small_capacitance_is_ordinary_mlcc():
    result = classify_mlcc("10nF 50V C0G 0402")

    assert result.is_mlcc is True
    assert result.high_capacitance_flag is False
    assert result.dielectric == "C0G"


def test_non_ceramic_capacitor_is_not_mlcc():
    result = classify_mlcc("100uF 25V Aluminum Electrolytic Capacitor")

    assert result.is_mlcc is False
    assert result.high_capacitance_flag is False
