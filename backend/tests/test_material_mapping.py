"""材料映射字典测试。"""
import pytest
from app.knowledge.material_mapping import (
    MATERIAL_REGISTRY,
    CATEGORY_MATERIAL_MAP,
    RARE_EARTH_AMPLIFIER,
    MaterialEntry,
    get_materials_for_category,
    get_categories_for_material,
    get_material_keys_for_domain,
    get_adjusted_cost_ratio,
    DOMAIN_MATERIALS,
)


class TestMaterialRegistry:
    """MATERIAL_REGISTRY 完整性测试。"""

    def test_total_33_materials(self):
        assert len(MATERIAL_REGISTRY) == 33, f"Expected 33 unique materials, got {len(MATERIAL_REGISTRY)}"

    def test_every_entry_has_all_fields(self):
        for key, entry in MATERIAL_REGISTRY.items():
            assert entry.key == key
            assert entry.name_zh, f"{key}: name_zh is empty"
            assert entry.domain in ("metals", "rare_earth", "chemical"), f"{key}: invalid domain {entry.domain}"
            assert 0.0 <= entry.cost_ratio <= 1.0, f"{key}: cost_ratio {entry.cost_ratio} out of range"
            assert entry.primary_source, f"{key}: primary_source is empty"
            assert entry.fetch_frequency in ("daily", "weekly", "monthly"), f"{key}: invalid frequency"

    def test_metals_domain_materials(self):
        metals = get_material_keys_for_domain("metals")
        # Cu × 4 + Al × 4 + Ag × 2 + Sn × 1 + Ni × 2 + Zn × 1 + enameled_cu_wire = 15
        assert len(metals) == 15, f"Expected 15 metals materials, got {len(metals)}"

    def test_rare_earth_materials(self):
        re_keys = get_material_keys_for_domain("rare_earth")
        assert len(re_keys) == 8

    def test_chemical_materials(self):
        chem_keys = get_material_keys_for_domain("chemical")
        assert len(chem_keys) == 10


class TestCategoryMapping:
    """品类→材料映射测试。"""

    def test_nine_categories_covered(self):
        """验证 9 大品类均有映射。"""
        expected = {
            "relay", "pcb", "mlcc", "high_cap_mlcc",
            "aluminum_electrolytic_capacitor", "tantalum_capacitor",
            "film_capacitor", "aluminum_heat_sink", "connector",
            "inductor_transformer", "inductor",
        }
        assert set(CATEGORY_MATERIAL_MAP.keys()) == expected

    def test_relay_materials(self):
        mats = get_materials_for_category("relay")
        keys = {m.key for m in mats}
        assert keys == {"cu_cathode", "ag_ingot", "engineering_plastics"}

    def test_pcb_materials(self):
        mats = get_materials_for_category("pcb")
        keys = {m.key for m in mats}
        assert keys == {"cu_foil", "glass_fiber_cloth", "epoxy_resin", "cu_ball"}

    def test_mlcc_materials(self):
        mats = get_materials_for_category("mlcc")
        keys = {m.key for m in mats}
        assert keys == {
            "titanium_dioxide", "barium_carbonate", "dysprosium_oxide",
            "yttrium_oxide", "nickel_powder", "cu_terminal",
        }

    def test_aluminum_heat_sink_single_material(self):
        mats = get_materials_for_category("aluminum_heat_sink")
        assert len(mats) == 1
        assert mats[0].key == "al_ingot"

    def test_tantalum_capacitor_materials(self):
        mats = get_materials_for_category("tantalum_capacitor")
        keys = {m.key for m in mats}
        assert keys == {"tantalum_powder", "tantalum_wire", "ag_paste", "manganese_dioxide"}


class TestReverseLookup:
    """反向查找测试。"""

    def test_cu_cathode_affects_multiple_categories(self):
        cats = get_categories_for_material("cu_cathode")
        assert "relay" in cats
        assert "connector" in cats

    def test_al_ingot_affects_heat_sink(self):
        cats = get_categories_for_material("al_ingot")
        assert "aluminum_heat_sink" in cats

    def test_unknown_material_returns_empty(self):
        assert get_categories_for_material("nonexistent") == []


class TestAdjustedCostRatio:
    """传导系数调整测试。"""

    def test_rare_earth_amplifier_applied(self):
        """稀土材料传导系数应乘以 1.6。"""
        dy_entry = MATERIAL_REGISTRY["dysprosium_oxide"]
        assert dy_entry.is_rare_earth
        ratio = get_adjusted_cost_ratio(dy_entry)
        assert ratio == pytest.approx(0.06 * RARE_EARTH_AMPLIFIER)

    def test_price_multiplier_applied(self):
        """铜箔(PCB)应有 1.12 加工溢价。"""
        cu_foil = MATERIAL_REGISTRY["cu_foil"]
        assert cu_foil.price_multiplier == 1.12
        ratio = get_adjusted_cost_ratio(cu_foil)
        assert ratio == pytest.approx(0.15 * 1.12)

    def test_rare_earth_with_price_multiplier(self):
        """稀土放大器 + 加工溢价应叠加。"""
        # 稀土材料通常没有 price_multiplier (默认 1.0)
        dy_entry = MATERIAL_REGISTRY["dysprosium_oxide"]
        ratio = get_adjusted_cost_ratio(dy_entry)
        expected = 0.06 * RARE_EARTH_AMPLIFIER * 1.0
        assert ratio == pytest.approx(expected)

    def test_standard_material_no_amplification(self):
        """非稀土、无加工溢价的材料。"""
        al_entry = MATERIAL_REGISTRY["al_ingot"]
        assert not al_entry.is_rare_earth
        assert al_entry.price_multiplier == 1.0
        ratio = get_adjusted_cost_ratio(al_entry)
        assert ratio == pytest.approx(0.40)


class TestDomainSources:
    """数据域源配置测试。"""

    def test_all_metals_have_primary_source(self):
        from app.knowledge.material_mapping import DOMAIN_SOURCES
        assert DOMAIN_SOURCES["metals"]["primary"] == "metals_api"

    def test_cost_ratios_sum_to_sane_values(self):
        """各品类传导系数合计应合理 (≤1.0)。"""
        for cat, mats in CATEGORY_MATERIAL_MAP.items():
            total = sum(m.cost_ratio for m in mats)
            assert total <= 1.0, f"{cat}: cost_ratio sum {total} exceeds 1.0"
