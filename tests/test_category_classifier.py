from app.services.upstream.category_classifier import classify_component_category


def test_classifies_film_capacitor_from_chinese_and_english_aliases():
    cn = classify_component_category("薄膜电容 0.47uF 450V", manufacturer="松下")
    assert cn.category == "film_capacitor"
    assert cn.display_name == "薄膜电容"
    assert "plastic_film" in cn.upstream_materials

    en = classify_component_category("Film Capacitor ECW series", manufacturer="Panasonic")
    assert en.category == "film_capacitor"


def test_high_cap_mlcc_category_uses_mlcc_classifier():
    result = classify_component_category("22uF 25V X7R 0805 MLCC", manufacturer="Murata")

    assert result.category == "high_cap_mlcc"
    assert result.display_name == "高容MLCC"
    assert result.driver_type == "hybrid"
    assert result.confidence >= 0.85
    assert "high_capacitance" in result.tags


def test_mcu_category_from_description_and_brand():
    result = classify_component_category("STM32F103C8T6 32-bit MCU", manufacturer="ST")

    assert result.category == "mcu"
    assert result.driver_type == "demand_supply"
    assert result.display_name == "MCU/微控制器"


def test_pcb_category_is_cost_driven():
    result = classify_component_category("FR4 PCB 4-layer ENIG", manufacturer="")

    assert result.category == "pcb"
    assert result.driver_type == "material_cost"
    assert "copper_foil" in result.upstream_materials


def test_relay_category_has_copper_and_silver_materials():
    result = classify_component_category("12V SPDT power relay 10A", manufacturer="Omron")

    assert result.category == "relay"
    assert result.driver_type == "material_cost"
    assert "copper" in result.upstream_materials
    assert "silver" in result.upstream_materials


def test_unknown_category_returns_information_insufficient():
    result = classify_component_category("ABC123 custom module", manufacturer="Unknown")

    assert result.category == "unknown"
    assert result.confidence < 0.5
    assert "information_insufficient" in result.tags
