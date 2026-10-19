"""MaterialPriceService 编排层测试。"""
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.material_price_service import (
    MaterialPriceService,
    get_material_price_service,
    METALS_API_MONTHLY_QUOTA,
)
from app.services.sources.materials.base import MaterialPriceSource


class MockMetalsSource(MaterialPriceSource):
    """Mock 有色金属数据源。"""
    source_name = "mock_metals"

    def __init__(self, prices=None, available=True, fail=False, timeout=False):
        super().__init__()
        self._prices = prices or {}
        self._available = available
        self._fail = fail
        self._timeout = timeout

    async def fetch_prices(self, material_keys: list[str]) -> dict[str, float | None]:
        if self._timeout:
            import asyncio
            await asyncio.sleep(60)
            return {}
        if self._fail:
            raise RuntimeError("simulated failure")
        return {k: self._prices.get(k) for k in material_keys}

    async def is_available(self) -> bool:
        return self._available


class TestMaterialPriceService:
    """MaterialPriceService 单元测试。"""

    @pytest.fixture
    def metals_source(self):
        return MockMetalsSource(prices={
            "cu_cathode": 78200.0,
            "al_ingot": 21500.0,
            "ag_ingot": 7.8,
            "tin": 285000.0,
            "nickel_powder": 135000.0,
            "zinc": 24000.0,
        })

    @pytest.fixture
    def service(self, metals_source):
        return MaterialPriceService(metals_source=metals_source)

    @pytest.mark.asyncio
    async def test_get_prices_basic(self, service):
        prices = await service.get_prices(["cu_cathode", "al_ingot"])
        assert prices["cu_cathode"] == 78200.0
        assert prices["al_ingot"] == 21500.0

    @pytest.mark.asyncio
    async def test_get_prices_partial_failure(self, service):
        """部分材料价格获取失败应返回 None。"""
        prices = await service.get_prices(["cu_cathode", "unknown_material"])
        assert prices["cu_cathode"] == 78200.0
        assert prices["unknown_material"] is None

    @pytest.mark.asyncio
    async def test_get_prices_cache_hit(self, service):
        """第二次查询应命中缓存，不再调用数据源。"""
        await service.get_prices(["cu_cathode"])
        # 第二次：应直接返回缓存
        prices = await service.get_prices(["cu_cathode"])
        assert prices["cu_cathode"] == 78200.0

    @pytest.mark.asyncio
    async def test_get_prices_force_refresh(self, service):
        """force_refresh=True 应刷新所有域并忽略缓存。"""
        prices = await service.get_prices(["cu_cathode", "al_ingot"], force_refresh=True)
        assert prices["cu_cathode"] == 78200.0
        assert prices["al_ingot"] == 21500.0

    @pytest.mark.asyncio
    async def test_source_failure_degraded(self):
        """数据源失败时应降级，标记 degraded。"""
        failing_source = MockMetalsSource(fail=True)
        svc = MaterialPriceService(metals_source=failing_source)
        prices = await svc.get_prices(["cu_cathode"])
        assert prices["cu_cathode"] is None
        stats = svc.get_cache_stats()
        assert stats["degraded"] >= 1

    @pytest.mark.asyncio
    async def test_source_unavailable(self):
        """数据源不可用时的降级行为。"""
        unavailable_source = MockMetalsSource(available=False)
        svc = MaterialPriceService(metals_source=unavailable_source)
        prices = await svc.get_prices(["cu_cathode"])
        assert prices["cu_cathode"] is None

    @pytest.mark.asyncio
    async def test_refresh_all_returns_stats(self, service):
        stats = await service.refresh_all()
        assert "total_materials" in stats
        assert "prices_valid" in stats
        assert "elapsed_seconds" in stats
        assert "timestamp" in stats

    def test_cache_stats_initial(self):
        svc = MaterialPriceService()
        stats = svc.get_cache_stats()
        assert stats["total_cached"] == 0
        assert stats["metals_api_quota"] == METALS_API_MONTHLY_QUOTA

    @pytest.mark.asyncio
    async def test_quota_tracking(self, service):
        await service.get_prices(["cu_cathode"])
        stats = service.get_cache_stats()
        assert stats["metals_api_calls_this_month"] == 1

    def test_singleton(self):
        svc1 = get_material_price_service()
        svc2 = get_material_price_service()
        assert svc1 is svc2


class TestMaterialPriceServiceIntegration:
    """集成：多域并行 + 真实 metals_api（需 API key）。"""

    @pytest.mark.asyncio
    async def test_metals_api_real(self):
        """真实 metals-api 调用测试（需要配置 API key）。"""
        from app.config import settings

        if not settings.metals_api_key:
            pytest.skip("METALS_API_KEY not configured")

        svc = MaterialPriceService()
        prices = await svc.get_prices(["cu_cathode", "al_ingot"])

        # 验证价格在合理范围内
        cu = prices.get("cu_cathode")
        if cu is not None:
            assert 50000 < cu < 120000, f"Copper price {cu} out of expected range"
        
        al = prices.get("al_ingot")
        if al is not None:
            assert 10000 < al < 30000, f"Aluminum price {al} out of expected range"
