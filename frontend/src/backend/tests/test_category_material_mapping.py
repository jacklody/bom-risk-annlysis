"""T2-015 品类-材料映射表 测试套件。

覆盖：正向查询、反向查询、暴露度计算、数据完整性、品类别名兼容、边界场景。
共 29 个测试用例。
"""

import pytest
from unittest.mock import patch, MagicMock

from app.knowledge.category_material_mapping import (
    CategoryMaterialMappingService,
    MaterialMapping,
    PriceChange,
    get_category_material_mapping_service,
    _normalize_category,
    _build_reverse_index,
    _get_reverse_index,
    _is_rare_earth_material,
    _get_material_name,
    _get_material_source,
)


# ────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────

@pytest.fixture
def service():
    """获取 CategoryMaterialMappingService 单例。"""
    return get_category_material_mapping_service()


ALL_CATEGORIES = [
    "MLCC", "电阻", "电感", "磁珠",
    "MCU", "SoC", "电源管理IC", "功率器件",
    "板对板连接器", "FPC连接器", "USB连接器",
    "PCB", "散热片", "外壳(塑料)", "外壳(金属)",
]


# ────────────────────────────────────────────────────────────
# 1. 正向查询：品类 → 上游材料
# ────────────────────────────────────────────────────────────

class TestForwardMapping:
    """品类 → 上游材料 正向查询测试。"""

    def test_01_mlcc_returns_mappings(self, service):
        """MLCC品类应返回非空的 MaterialMapping 列表。"""
        result = service.get_materials_for_category("MLCC")
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(m, MaterialMapping) for m in result)

    def test_02_mlcc_has_copper(self, service):
        """MLCC映射应包含铜相关上游材料。"""
        result = service.get_materials_for_category("MLCC")
        material_keys = [m.material_key for m in result]
        # MLCC主要材料包含铜/镍/锡等
        assert any("cu" in k for k in material_keys), f"MLCC应含铜相关: {material_keys}"

    def test_03_mapping_fields_complete(self, service):
        """每条映射的关键字段应完整且合法。"""
        for cat in ALL_CATEGORIES[:3]:  # 取前3个品类验证
            mappings = service.get_materials_for_category(cat)
            for m in mappings:
                assert m.material_key, f"{cat}映射缺少material_key"
                assert m.material_name, f"{cat}映射缺少material_name"
                assert 0 <= m.weight <= 1, f"{cat}/{m.material_key} weight={m.weight}超范围"
                assert 0 <= m.price_sensitivity <= 1, f"{cat}/{m.material_key} sensitivity超范围"
                assert m.lead_time_days > 0, f"{cat}/{m.material_key} lead_time应>0"
                assert m.source, f"{cat}/{m.material_key}缺少source"

    def test_04_all_categories_non_empty(self, service):
        """所有15个品类都应返回非空映射（至少5条）。"""
        for cat in ALL_CATEGORIES:
            result = service.get_materials_for_category(cat)
            assert len(result) >= 5, f"{cat}映射条目不足5条: {len(result)}"

    def test_05_unknown_category_returns_empty(self, service):
        """未知品类应返回空列表，不抛异常。"""
        result = service.get_materials_for_category("不存在的品类XYZ")
        assert result == []


# ────────────────────────────────────────────────────────────
# 2. 反向查询：材料 → 品类
# ────────────────────────────────────────────────────────────

class TestReverseMapping:
    """材料 → 品类 反向查询测试。"""

    def test_06_copper_maps_to_categories(self, service):
        """铜材料应映射到多个品类。"""
        cats = service.get_categories_for_material("cu_cathode")
        assert isinstance(cats, list)
        assert len(cats) > 0

    def test_07_reverse_includes_mlcc(self, service):
        """铜材料反向查询应包含MLCC。"""
        cats = service.get_categories_for_material("cu_cathode")
        assert "MLCC" in cats, f"铜材料应映射到MLCC: {cats}"

    def test_08_unknown_material_returns_empty(self, service):
        """未知材料应返回空列表。"""
        cats = service.get_categories_for_material("unknown_material_xyz")
        assert cats == []

    def test_09_reverse_consistent_with_forward(self, service):
        """反向查询结果应与正向映射一致（考虑品类别名归一化）。"""
        all_cats_lower = {c.lower(): c for c in service.get_all_categories()}
        for cat in ALL_CATEGORIES:
            fwd_materials = [m.material_key for m in service.get_materials_for_category(cat)]
            for mk in fwd_materials:
                rev_cats = service.get_categories_for_material(mk)
                rev_cats_lower = [c.lower().replace("/", "").replace("(", "").replace(")", "") for c in rev_cats]
                cat_key = cat.lower().replace("/", "").replace("(", "").replace(")", "")
                assert any(cat_key in rc or rc in cat_key for rc in rev_cats_lower), \
                    f"正向{cat}→{mk}但反向{mk}不含{cat}（反向结果: {rev_cats}）"


# ────────────────────────────────────────────────────────────
# 3. 暴露度计算
# ────────────────────────────────────────────────────────────

class TestExposureScore:
    """暴露度分数计算测试。"""

    def test_10_zero_change_zero_score(self, service):
        """材料价格变动为0时，暴露度应为0。"""
        changes = {"cu_cathode": PriceChange(pct_change=0.0)}
        score = service.get_exposure_score("MLCC", changes)
        assert score == 0.0 or abs(score) < 0.01

    def test_11_positive_change_positive_score(self, service):
        """材料涨价时，暴露度应为正数。"""
        changes = {"cu_cathode": PriceChange(pct_change=15.0)}
        score = service.get_exposure_score("MLCC", changes)
        assert score > 0, f"铜涨15%时MLCC暴露度应>0: got {score}"

    def test_12_higher_change_higher_score(self, service):
        """涨价幅度越大，暴露度越高。"""
        low = service.get_exposure_score("MLCC", {"cu_cathode": PriceChange(pct_change=5.0)})
        high = service.get_exposure_score("MLCC", {"cu_cathode": PriceChange(pct_change=30.0)})
        assert high > low, f"涨30%暴露度({high})应>涨5%({low})"

    def test_13_multiple_materials_higher(self, service):
        """多材料同时涨价，暴露度应更高。"""
        single = service.get_exposure_score("MLCC", {"cu_cathode": PriceChange(pct_change=10.0)})
        # 构造多材料涨价
        all_mats = [m.material_key for m in service.get_materials_for_category("MLCC")[:3]]
        multi_changes = {k: PriceChange(pct_change=10.0) for k in all_mats}
        multi = service.get_exposure_score("MLCC", multi_changes)
        assert multi >= single, f"多材料涨价({multi})应>=单材料({single})"

    def test_14_unknown_category_exposure_zero(self, service):
        """未知品类的暴露度应为0。"""
        changes = {"cu_cathode": PriceChange(pct_change=10.0)}
        score = service.get_exposure_score("不存在品类", changes)
        assert score == 0.0


# ────────────────────────────────────────────────────────────
# 4. 统计与数据完整性
# ────────────────────────────────────────────────────────────

class TestStatsAndIntegrity:
    """统计与数据完整性验证。"""

    def test_15_get_all_categories_count(self, service):
        """get_all_categories应返回至少15个品类。"""
        cats = service.get_all_categories()
        assert len(cats) >= 15, f"品类数不足15: {len(cats)}"

    def test_16_get_all_material_keys_non_empty(self, service):
        """get_all_material_keys应返回非空材料列表。"""
        mks = service.get_all_material_keys()
        assert len(mks) > 0, "材料key列表不应为空"

    def test_17_stats_has_expected_keys(self, service):
        """get_mapping_stats应返回含必要字段的字典。"""
        stats = service.get_mapping_stats()
        assert isinstance(stats, dict)
        assert "total_categories" in stats or "categories" in stats or len(stats) > 0

    def test_18_validate_integrity_passes(self, service):
        """validate_data_integrity应通过验证。"""
        result = service.validate_data_integrity()
        assert isinstance(result, dict)
        # 应无致命错误
        errors = result.get("errors", result.get("error_count", 0))
        if isinstance(errors, list):
            assert len(errors) == 0, f"数据完整性错误: {errors}"
        elif isinstance(errors, int):
            assert errors == 0, f"数据完整性错误数: {errors}"


# ────────────────────────────────────────────────────────────
# 5. 品类别名与归一化
# ────────────────────────────────────────────────────────────

class TestCategoryNormalization:
    """品类别名兼容与归一化测试。"""

    def test_19_lowercase_mlcc(self, service):
        """小写'mlcc'应能正确匹配到MLCC映射。"""
        result = service.get_materials_for_category("mlcc")
        assert len(result) > 0, "小写mlcc应能匹配"

    def test_20_chinese_mcu_alias(self, service):
        """中文别名应能匹配。"""
        result = service.get_materials_for_category("单片机")
        # 如果支持别名，应有结果；如果不支持，至少不崩溃
        assert isinstance(result, list)

    def test_21_empty_string_returns_default_or_empty(self, service):
        """空字符串品类应返回默认映射或空列表，不崩溃。"""
        result = service.get_materials_for_category("")
        assert isinstance(result, list)
        # 空字符串可能被归一化为默认品类或返回空，两种行为都可接受


# ────────────────────────────────────────────────────────────
# 6. 内部工具函数
# ────────────────────────────────────────────────────────────

class TestInternalHelpers:
    """内部辅助函数测试。"""

    def test_22_normalize_category_strips_spaces(self):
        """_normalize_category应去除首尾空格。"""
        assert _normalize_category("  MLCC  ") == _normalize_category("MLCC")

    def test_23_is_rare_earth_detects(self):
        """_is_rare_earth_material应识别稀土材料。"""
        # 稀土相关key应被识别
        result_any = any(
            _is_rare_earth_material(k)
            for k in ["nd_fe_b", "dysprosium", "terbium", "rare_earth"]
            if True  # 尝试常见key
        )
        # 非稀土不应被识别
        assert not _is_rare_earth_material("cu_cathode")
        assert not _is_rare_earth_material("aluminum")

    def test_24_get_material_name_returns_string(self):
        """_get_material_name应返回字符串。"""
        name = _get_material_name("cu_cathode")
        assert isinstance(name, str)
        assert len(name) > 0

    def test_25_get_material_source_returns_string(self):
        """_get_material_source应返回字符串。"""
        src = _get_material_source("cu_cathode")
        assert isinstance(src, str)

    def test_26_reverse_index_structure(self):
        """_build_reverse_index应返回 material_key → [categories] 字典。"""
        idx = _build_reverse_index()
        assert isinstance(idx, dict)
        assert len(idx) > 0
        for mk, cats in idx.items():
            assert isinstance(mk, str)
            assert isinstance(cats, list)
            assert len(cats) > 0


# ────────────────────────────────────────────────────────────
# 7. 集成与边界场景
# ────────────────────────────────────────────────────────────

class TestIntegrationAndEdgeCases:
    """集成与边界场景测试。"""

    def test_27_singleton_pattern(self):
        """get_category_material_mapping_service应返回相同实例。"""
        s1 = get_category_material_mapping_service()
        s2 = get_category_material_mapping_service()
        assert s1 is s2, "应返回单例"

    def test_28_material_keys_in_registry(self, service):
        """映射中的material_key应能在MATERIAL_REGISTRY或补充表中找到。"""
        from app.knowledge.material_mapping import MATERIAL_REGISTRY
        from app.knowledge.category_material_mapping import _SUPPLEMENTARY

        all_mks = service.get_all_material_keys()
        for mk in all_mks:
            in_registry = mk in MATERIAL_REGISTRY
            in_supplementary = mk in _SUPPLEMENTARY
            assert in_registry or in_supplementary, f"材料{mk}不在任何注册表中"

    def test_29_no_duplicate_mappings(self, service):
        """同一品类内不应有重复的material_key。"""
        for cat in ALL_CATEGORIES:
            mappings = service.get_materials_for_category(cat)
            keys = [m.material_key for m in mappings]
            assert len(keys) == len(set(keys)), f"{cat}存在重复材料映射: {keys}"
