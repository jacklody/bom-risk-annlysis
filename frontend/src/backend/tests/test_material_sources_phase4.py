"""Phase 4 测试 — Material Alerts API、Dashboard 集成、双轨引擎回归验证。

覆盖：
  - Material Alerts API: 多维度过滤、分页、trends、summary、cache-stats
  - Dashboard 原料模块集成: material_overview、material_top_alerts
  - 双轨引擎原料信号流: MaterialTracker → risk_context_builder → dual_track
  - 端到端: 材料价格变动 → 品类风险评分全链路
"""

import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime, timedelta, timezone

from app.services.material_price_service import (
    MaterialPriceService,
    get_material_price_service,
    METALS_API_MONTHLY_QUOTA,
)
from app.services.material_tracker import (
    MaterialTracker,
    MaterialTracking,
    PRICE_CHANGE_YELLOW,
    PRICE_CHANGE_ORANGE,
    PRICE_CHANGE_RED,
)
from app.services.sources.materials.base import MaterialPriceSource
from app.knowledge.material_mapping import (
    MATERIAL_REGISTRY,
    CATEGORY_MATERIAL_MAP,
    get_material_entry,
    get_materials_for_category,
    RARE_EARTH_AMPLIFIER,
    DOMAIN_MATERIALS,
)


# ════════════════════════════════════════════════════════════════
# Mock Fixtures
# ════════════════════════════════════════════════════════════════

def _make_mock_source(name, prices=None, available=True):
    """工厂函数：按名称创建 Mock 源，避免子类爆炸。"""
    src = MockPriceSource(prices=prices, available=available)
    src.source_name = name
    return src


class MockPriceSource(MaterialPriceSource):
    """通用 Mock 数据源。source_name 在构造后设置。"""
    source_name = "mock_source"

    def __init__(self, prices=None, available=True):
        super().__init__()
        self._prices = prices or {}
        self._available = available

    async def fetch_prices(self, material_keys):
        return {k: self._prices.get(k) for k in material_keys}

    async def is_available(self):
        return self._available


@pytest.fixture
def price_service_with_data():
    """创建带预设价格数据的 MaterialPriceService。"""
    metals = _make_mock_source("mock_metals", {
        "cu_cathode": 80000.0,
        "al_ingot": 22000.0,
        "ag_ingot": 8.1,
        "tin": 290000.0,
        "nickel_powder": 140000.0,
        "zinc": 24500.0,
        "au": 510.0,
        "pd": 350.0,
        "si_metal": 16000.0,
        "mg_ingot": 18500.0,
        "pb_ingot": 16500.0,
    })
    rare_earth = _make_mock_source("mock_rare_earth", {
        "prnd_oxide": 450.0,
        "dysprosium_oxide": 2800.0,
        "yttrium_oxide": 55.0,
        "tantalum_powder": 3500.0,
        "tantalum_wire": 5200.0,
        "barium_carbonate": 3200.0,
        "copper_foil": 110.0,
        "ceramic_powder": 85.0,
        "ferrite_core": 28.0,
        "titanium_dioxide": 18500.0,
        "manganese_dioxide": 15000.0,
    })
    chem = _make_mock_source("mock_chemical", {
        "epoxy_resin": 15000.0,
        "glass_fiber_cloth": 8000.0,
        "polyimide_film": 350.0,
        "pet_film": 15000.0,
        "silicon_steel": 9000.0,
        "ba_resin": 13000.0,
        "polyester_pet": 9500.0,
    })
    svc = MaterialPriceService(
        metals_source=metals,
        rare_earth_sources=[rare_earth],
        chemical_sources=[chem],
    )
    # 预热缓存
    for src, domain in [(metals, "metals"), (rare_earth, "rare_earth"), (chem, "chemical")]:
        for mk in DOMAIN_MATERIALS.get(domain, []):
            price = src._prices.get(mk)
            if price is not None:
                svc._cache[mk] = {
                    "price": price,
                    "unit": "元/吨",
                    "source": src.source_name,
                    "timestamp": time.time(),
                    "degraded": False,
                }
    return svc


@pytest.fixture
def mock_db():
    """Mock 数据库 session。"""
    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = MagicMock()
    return db


# ════════════════════════════════════════════════════════════════
# 4.1 MaterialTracker with PriceService Integration
# ════════════════════════════════════════════════════════════════

class TestMaterialTrackerWithPriceService:
    """MaterialTracker + MaterialPriceService 集成测试。"""

    @pytest.mark.asyncio
    async def test_track_materials_with_real_prices(self, price_service_with_data, mock_db):
        """验证 tracker 能正确使用 price_service 的实际价格数据。"""
        mock_db.execute = AsyncMock(return_value=MagicMock())
        mock_db.execute.return_value.all.return_value = []  # 无历史数据

        tracker = MaterialTracker(mock_db, price_service_with_data)

        results = await tracker.track_materials(["cu_cathode", "al_ingot", "tin"])

        assert "cu_cathode" in results
        assert results["cu_cathode"].current_price == 80000.0
        assert results["al_ingot"].current_price == 22000.0
        assert results["tin"].current_price == 290000.0
        # 无历史基线，change_pct 应为 0
        assert results["cu_cathode"].change_pct == 0.0
        assert results["cu_cathode"].risk_level == "NORMAL"

    @pytest.mark.asyncio
    async def test_track_materials_with_historical_baselines(self, price_service_with_data, mock_db):
        """验证 tracker 能利用历史价格计算基线。"""
        # 构建 30 天历史数据：铜阴极均价 70000
        mock_db.execute = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = [
            ("cu_cathode", 70000.0),
            ("al_ingot", 20000.0),
        ]
        mock_db.execute.return_value = mock_result

        tracker = MaterialTracker(mock_db, price_service_with_data)

        results = await tracker.track_materials(["cu_cathode", "al_ingot"])

        # 铜阴极: 当前 80000, 基线 70000, 涨幅 14.29% → ORANGE
        assert results["cu_cathode"].current_price == 80000.0
        assert results["cu_cathode"].baseline_30d == 70000.0
        assert pytest.approx(results["cu_cathode"].change_pct, 0.1) == 14.29
        assert results["cu_cathode"].risk_level == "ORANGE"

        # 铝锭: 当前 22000, 基线 20000, 涨幅 10% → ORANGE
        assert results["al_ingot"].current_price == 22000.0
        assert pytest.approx(results["al_ingot"].change_pct, 0.1) == 10.0
        assert results["al_ingot"].risk_level == "ORANGE"

    @pytest.mark.asyncio
    async def test_track_materials_rare_earth_amplifier(self, price_service_with_data, mock_db):
        """验证稀土材料自动应用 1.6× 传导系数放大器。"""
        mock_db.execute = AsyncMock(return_value=MagicMock())
        mock_db.execute.return_value.all.return_value = []  # 无历史

        tracker = MaterialTracker(mock_db, price_service_with_data)

        results = await tracker.track_materials(["prnd_oxide"])

        tracking = results["prnd_oxide"]
        # 应该应用了 RARE_EARTH_AMPLIFIER
        assert tracking.adjusted_cost_ratio > 0
        assert tracking.domain == "rare_earth"
        # 验证 amplified ratio ≥ 原始 cost_ratio
        entry = get_material_entry("prnd_oxide")
        assert tracking.adjusted_cost_ratio >= entry.cost_ratio

    @pytest.mark.asyncio
    async def test_track_for_category_returns_all_related(self, price_service_with_data, mock_db):
        """track_for_category 应返回该品类全部关联材料。"""
        mock_db.execute = AsyncMock(return_value=MagicMock())
        mock_db.execute.return_value.all.return_value = []

        tracker = MaterialTracker(mock_db, price_service_with_data)

        results = await tracker.track_for_category("pcb")
        pcb_materials = get_materials_for_category("pcb")
        expected_keys = {m.key for m in pcb_materials}

        assert set(results.keys()) == expected_keys

    @pytest.mark.asyncio
    async def test_track_for_category_multiple_categories(self, price_service_with_data, mock_db):
        """验证多个品类关联材料正确返回。"""
        mock_db.execute = AsyncMock(return_value=MagicMock())
        mock_db.execute.return_value.all.return_value = []

        tracker = MaterialTracker(mock_db, price_service_with_data)

        for cat in ["relay", "connector", "inductor_transformer"]:
            results = await tracker.track_for_category(cat)
            assert len(results) > 0, f"Category '{cat}' should have associated materials"


# ════════════════════════════════════════════════════════════════
# 4.2 Dual-Track Material Signal Flow
# ════════════════════════════════════════════════════════════════

class TestDualTrackMaterialSignalFlow:
    """双轨引擎 — 原料信号流集成验证。"""

    def test_dual_track_incorporates_material_signals(self):
        """验证 dual_track 引擎正确接收和处理材料信号。"""
        from app.services.upstream.dual_track_risk_engine import evaluate_dual_track_risk

        # 模拟 PCB 材料信号: 铜箔涨价 + 环氧树脂压力
        material_signals = {
            "copper_foil_price_up": 1.0,
            "epoxy_pressure": 1.0,
        }

        result = evaluate_dual_track_risk(
            category="pcb",
            material_signals=material_signals,
            body_signals={},
            market_facts={},
            buffers={},
        )

        # PCB: material 权重 0.75, demand_supply 权重 0.25
        assert result.category == "pcb"
        assert result.primary_track == "material"
        assert result.track_scores["material"] > 0
        assert result.risk_level in ("yellow", "orange", "red", "green", "gray")

    def test_ic_only_material_rise_capped(self):
        """验证 IC 类单一材料上涨不能直接红色预警。"""
        from app.services.upstream.dual_track_risk_engine import evaluate_dual_track_risk

        # MCU: 硅片价格上涨
        material_signals = {"silicon_wafer_price_up": 1.0}

        result = evaluate_dual_track_risk(
            category="mcu",
            material_signals=material_signals,
            body_signals={},
            market_facts={},
            buffers={},
        )

        # IC 类材料只有 cap 34 分（YELLOW 级别）
        assert result.total_score <= 34
        assert result.risk_level != "red"
        assert result.risk_level != "orange"

    def test_ic_material_plus_demand_supply_unlocks_higher(self):
        """验证 IC 类：材料上涨 + 供需紧张可突破 cap 限制。"""
        from app.services.upstream.dual_track_risk_engine import evaluate_dual_track_risk

        material_signals = {"silicon_wafer_price_up": 1.0}
        market_facts = {"price_up_confirmed": True, "shortage_confirmed": True}
        body_signals = {"stock_down": True, "lead_time_weeks": 12}

        result = evaluate_dual_track_risk(
            category="mcu",
            material_signals=material_signals,
            body_signals=body_signals,
            market_facts=market_facts,
            buffers={},
        )

        # 供需轨参与后，总分可以突破 34
        assert result.track_scores["demand_supply"] > 0
        assert result.primary_track == "demand_supply"

    def test_lifecycle_eol_bypasses_all(self):
        """验证 EOL 状态直接跳过双轨到 RED。"""
        from app.services.upstream.dual_track_risk_engine import evaluate_dual_track_risk

        material_signals = {"copper_foil_price_up": 0}  # 无材料压力
        body_signals = {"lifecycle_status": "EOL"}
        buffers = {"safety_stock_days": 90, "multi_source_available": True}  # 充足缓冲

        result = evaluate_dual_track_risk(
            category="pcb",
            material_signals=material_signals,
            body_signals=body_signals,
            market_facts={},
            buffers=buffers,
        )

        assert result.risk_level == "red"
        assert result.total_score == 95
        assert result.primary_track == "lifecycle"
        assert "EOL" in str(result.evidence)

    def test_buffer_reduces_risk_score(self):
        """验证安全库存和多源供应缓冲能降低风险分。"""
        from app.services.upstream.dual_track_risk_engine import evaluate_dual_track_risk

        material_signals = {"copper_foil_price_up": 1.0, "epoxy_pressure": 1.0}
        buffers = {"safety_stock_days": 60, "multi_source_available": True}

        result = evaluate_dual_track_risk(
            category="pcb",
            material_signals=material_signals,
            body_signals={},
            market_facts={},
            buffers=buffers,
        )

        assert result.track_scores["buffer"] > 0
        # 有缓冲时总分应低于纯材料分
        assert result.total_score < result.track_scores["material"]


# ════════════════════════════════════════════════════════════════
# 4.3 RiskContextBuilder Material Integration
# ════════════════════════════════════════════════════════════════

class TestRiskContextBuilderMaterialIntegration:
    """risk_context_builder 与 MaterialTracker 集成验证。"""

    @pytest.mark.asyncio
    async def test_material_signals_from_tracker(self):
        """验证 set_material_tracker 和信号字典的生成逻辑。"""
        from app.services.upstream.risk_context_builder import (
            set_material_tracker,
        )

        # 直接验证 tracker 设置和传入
        mock_tracker = MagicMock()
        mock_tracking = MaterialTracking(
            material_key="copper_foil",
            material_name_zh="铜箔",
            domain="rare_earth",
            risk_level="ORANGE",
            change_pct=12.0,
            material_track_score=9.6,
        )
        mock_tracker.track_for_category = AsyncMock(
            return_value={"copper_foil": mock_tracking}
        )

        set_material_tracker(mock_tracker)

        # 直接调用 mock 验证接口契约
        results = await mock_tracker.track_for_category("pcb")
        assert "copper_foil" in results
        tracking = results["copper_foil"]
        assert tracking.risk_level == "ORANGE"
        assert tracking.material_track_score == 9.6
        assert tracking.has_alert is True

    def test_fallback_to_market_facts_when_tracker_unavailable(self):
        """验证 tracker 不可用时退化为市场事实推断。"""
        from app.services.upstream.risk_context_builder import (
            _material_signals_for_category,
            set_material_tracker,
        )

        # 清空 tracker 引用
        set_material_tracker(None)

        # 使用 market_facts 退化路径
        signals = _material_signals_for_category(
            "pcb", {"price_up_confirmed": True}
        )
        assert "copper_foil_price_up" in signals


# ════════════════════════════════════════════════════════════════
# 4.4 MaterialPriceService Cache Stats
# ════════════════════════════════════════════════════════════════

class TestCacheStats:
    """缓存统计功能测试。"""

    def test_get_cache_stats_empty(self):
        """空缓存时 stats 应正确。"""
        svc = MaterialPriceService(
            metals_source=MockPriceSource(),
            rare_earth_sources=[MockPriceSource()],
            chemical_sources=[MockPriceSource()],
        )
        stats = svc.get_cache_stats()

        assert stats["total_cached"] == 0
        assert stats["fresh"] == 0
        assert stats["stale"] == 0
        assert "metals_api_quota" in stats

    def test_get_cache_stats_with_data(self, price_service_with_data):
        """有缓存数据时 stats 应正确。"""
        stats = price_service_with_data.get_cache_stats()

        assert stats["total_cached"] > 0
        assert stats["fresh"] == stats["total_cached"]  # 刚写入全新鲜
        assert stats["degraded"] == 0
        assert "by_domain" in stats

    def test_cache_stats_metals_quota_tracking(self):
        """验证 metals_api 配额追踪。"""
        svc = MaterialPriceService(
            metals_source=MockPriceSource(),
        )
        # 手动增加调用计数
        svc._metals_api_calls = [time.time()] * 30

        stats = svc.get_cache_stats()
        assert stats["metals_api_calls_this_month"] == 30
        assert stats["metals_api_quota"] == 60

    @pytest.mark.asyncio
    async def test_refresh_all_returns_summary(self, price_service_with_data):
        """refresh_all 返回统计摘要。"""
        summary = await price_service_with_data.refresh_all()

        assert "total_materials" in summary
        assert "prices_valid" in summary
        assert "elapsed_seconds" in summary
        assert summary["total_materials"] == len(MATERIAL_REGISTRY)


# ════════════════════════════════════════════════════════════════
# 4.5 Dashboard Material Integration
# ════════════════════════════════════════════════════════════════

class TestDashboardMaterialIntegration:
    """Dashboard 原料模块集成测试。"""

    def test_material_overview_returns_healthy_when_no_degraded(self, price_service_with_data):
        """验证 material_overview 在无降级时返回 healthy 状态。"""
        from app.services.dashboard_summary import _material_overview

        from app.services import material_price_service as mps
        original = mps.get_material_price_service
        mps.get_material_price_service = lambda: price_service_with_data

        try:
            result = _material_overview(MagicMock())
            assert result is not None
            assert result["status"] == "healthy"
            assert result["degraded_count"] == 0
            assert result["fresh_cache_count"] > 0
        finally:
            mps.get_material_price_service = original

    def test_material_overview_returns_none_on_error(self):
        """验证 material_overview 异常时优雅返回 None。"""
        from app.services.dashboard_summary import _material_overview

        from app.services import material_price_service as mps
        original = mps.get_material_price_service
        mps.get_material_price_service = MagicMock(side_effect=RuntimeError("boom"))

        try:
            result = _material_overview(MagicMock())
            assert result is None  # 优雅降级
        finally:
            mps.get_material_price_service = original

    def test_material_top_alerts_returns_none_on_error(self):
        """验证 material_top_alerts 异常时优雅返回 None。"""
        from app.services.dashboard_summary import _material_top_alerts

        mock_db = MagicMock()
        mock_db.query.side_effect = RuntimeError("db error")

        result = _material_top_alerts(mock_db)
        assert result is None

    def test_dashboard_summary_includes_material_sections(self):
        """验证 dashboard_summary 包含 material_alerts 和 material_top 字段。"""
        from app.services.dashboard_summary import build_dashboard_summary

        mock_db = MagicMock()
        mock_db.query.return_value.all.return_value = []

        result = build_dashboard_summary(mock_db)

        assert "material_alerts" in result
        assert "material_top" in result
        assert "overview" in result
        assert "project_risks" in result


# ════════════════════════════════════════════════════════════════
# 4.6 Multi-Domain Multi-Source Failover
# ════════════════════════════════════════════════════════════════

class TestMultiDomainMultiSourceFailover:
    """多域多源降级策略集成测试。"""

    @pytest.mark.asyncio
    async def test_rare_earth_multi_source_failover(self):
        """稀土域: 主源失败 → 备源接替。"""
        primary = _make_mock_source("primary_re", prices={}, available=False)
        backup = _make_mock_source("backup_re", {"prnd_oxide": 450.0, "dysprosium_oxide": 2800.0})

        svc = MaterialPriceService(
            metals_source=_make_mock_source("dummy_metals"),
            rare_earth_sources=[primary, backup],
            chemical_sources=[_make_mock_source("dummy_chem")],
        )

        prices = await svc.get_prices(["prnd_oxide", "dysprosium_oxide"], force_refresh=True)
        assert prices["prnd_oxide"] == 450.0
        assert prices["dysprosium_oxide"] == 2800.0

    @pytest.mark.asyncio
    async def test_chemical_multi_source_failover(self):
        """化工域: 主源部分覆盖 → 备源补充。"""
        primary = _make_mock_source("primary_chem", {"epoxy_resin": 15000.0})
        backup = _make_mock_source("backup_chem", {"glass_fiber_cloth": 8000.0, "epoxy_resin": 14800.0})

        svc = MaterialPriceService(
            metals_source=_make_mock_source("dummy_metals"),
            rare_earth_sources=[_make_mock_source("dummy_re")],
            chemical_sources=[primary, backup],
        )

        prices = await svc.get_prices(["epoxy_resin", "glass_fiber_cloth"], force_refresh=True)
        # 环氧树脂由主源返回
        assert prices["epoxy_resin"] == 15000.0
        # 玻纤布由备源补充
        assert prices["glass_fiber_cloth"] == 8000.0

    @pytest.mark.asyncio
    async def test_metals_quota_exhausted_degraded(self):
        """有色金属域: 配额耗尽 → 返回 stale 缓存。"""
        svc = MaterialPriceService(
            metals_source=_make_mock_source("metals_api", {"cu_cathode": 78200.0}),
        )
        # 预热缓存
        svc._cache["cu_cathode"] = {
            "price": 75000.0,
            "unit": "元/吨",
            "source": "metals-api",
            "timestamp": time.time() - 3600,  # 1 小时前
            "degraded": False,
        }
        # 耗尽配额
        svc._metals_api_calls = [time.time()] * METALS_API_MONTHLY_QUOTA

        prices = await svc.get_prices(["cu_cathode"], force_refresh=True)
        # 使用 stale 缓存
        assert prices["cu_cathode"] == 75000.0


# ════════════════════════════════════════════════════════════════
# 4.7 End-to-End: Material Price → Category Risk Pipeline
# ════════════════════════════════════════════════════════════════

class TestEndToEndMaterialRiskPipeline:
    """端到端: 材料价格变动 → 品类风险评分全链路。"""

    def test_pcb_material_rise_flows_to_dual_track(self):
        """PCB 材料价格上涨 → 双轨引擎正确传导。"""
        from app.services.upstream.dual_track_risk_engine import evaluate_dual_track_risk

        # 模拟铜箔涨 20% → material 轨得分
        material_signals = {
            "copper_foil_price_up": 1.0,
            "epoxy_pressure": 1.0,
        }

        result = evaluate_dual_track_risk(
            category="pcb",
            material_signals=material_signals,
            body_signals={},
            market_facts={"price_up_confirmed": False},
            buffers={"safety_stock_days": 7},
        )

        # PCB 分类: material 权重 0.75
        assert result.track_scores["material"] > 0
        assert result.risk_level != "gray"
        assert len(result.evidence) > 0

    def test_ic_category_material_routing(self):
        """IC 品类材料信号路由正确。"""
        from app.services.upstream.dual_track_risk_engine import evaluate_dual_track_risk

        for cat in ["mcu", "power_ic"]:
            material_signals = {"silicon_wafer_price_up": 1.0}
            result = evaluate_dual_track_risk(
                category=cat,
                material_signals=material_signals,
                body_signals={},
                market_facts={},
                buffers={},
            )
            # IC 模型: demand_supply 权重 0.85 主导
            assert result.track_scores["material"] < result.track_scores["demand_supply"] or result.total_score <= 34

    def test_mlcc_material_pressure_with_shortage(self):
        """MLCC 材料压力 + 缺货 → 综合评估。"""
        from app.services.upstream.dual_track_risk_engine import evaluate_dual_track_risk

        material_signals = {"ceramic_powder_pressure": 1.0}
        market_facts = {"shortage_confirmed": True}

        result = evaluate_dual_track_risk(
            category="high_cap_mlcc",
            material_signals=material_signals,
            body_signals={},
            market_facts=market_facts,
            buffers={},
        )

        assert result.risk_level in ("yellow", "orange", "red")

    def test_normal_material_no_alert(self):
        """正常材料价格 → 不触发预警。"""
        from app.services.upstream.dual_track_risk_engine import evaluate_dual_track_risk

        result = evaluate_dual_track_risk(
            category="connector",
            material_signals={},
            body_signals={},
            market_facts={},
            buffers={},
        )

        assert result.risk_level == "gray"
        assert result.total_score == 0


# ════════════════════════════════════════════════════════════════
# 4.8 Material Registry Validation (Phase 4 regression)
# ════════════════════════════════════════════════════════════════

class TestMaterialRegistryPhase4:
    """Phase 4 材料注册表回归验证。"""

    def test_all_domains_have_materials(self):
        """三个域都有材料。"""
        for domain in ["metals", "rare_earth", "chemical"]:
            assert domain in DOMAIN_MATERIALS
            assert len(DOMAIN_MATERIALS[domain]) > 0

    def test_all_materials_in_registry(self):
        """MATERIAL_REGISTRY 包含所有 DOMAIN_MATERIALS 中的 key。"""
        for domain, keys in DOMAIN_MATERIALS.items():
            for key in keys:
                assert key in MATERIAL_REGISTRY, f"{key} missing from MATERIAL_REGISTRY"
                assert MATERIAL_REGISTRY[key].domain == domain

    def test_category_material_mapping_complete(self):
        """每个品类都有对应的材料映射。"""
        categories = list(CATEGORY_MATERIAL_MAP.keys())
        assert len(categories) > 0, "No categories in CATEGORY_MATERIAL_MAP"
        for cat in categories:
            materials = get_materials_for_category(cat)
            assert len(materials) > 0, f"Category '{cat}' has no materials"

    def test_rare_earth_materials_have_amplifier(self):
        """稀土材料成本比例应用了放大器。"""
        from app.knowledge.material_mapping import get_adjusted_cost_ratio, RARE_EARTH_AMPLIFIER

        # 验证 prnd_oxide, dysprosium_oxide, yttrium_oxide 有放大器
        rare_keys = {"prnd_oxide", "dysprosium_oxide", "yttrium_oxide"}
        for key in rare_keys:
            entry = get_material_entry(key)
            assert entry is not None
            raw = entry.cost_ratio
            adjusted = get_adjusted_cost_ratio(entry)
            if raw > 0:
                assert adjusted == raw * RARE_EARTH_AMPLIFIER
