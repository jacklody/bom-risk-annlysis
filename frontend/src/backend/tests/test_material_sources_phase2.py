"""稀土 & 小金属数据源测试。

测试范围:
- RareEarthAssociationSource: HTML 解析、价格提取、校验、降级
- AsianMetalSource: 钽粉/钽丝 HTML 解析、校验、降级
- BaiinfoSource: 碳酸钡 HTML 解析、降级
- MaterialPriceService 多源降级集成 (rare_earth 域)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from app.services.sources.materials.rare_earth_source import (
    RareEarthAssociationSource,
    _RE_SUPPORTED_KEYS,
    _FALLBACK_REFERENCE_PRICES,
)
from app.services.sources.materials.small_metal_source import (
    AsianMetalSource,
    BaiinfoSource,
    _SM_SUPPORTED_KEYS,
    _SM_FALLBACK_PRICES,
)


# ═══════════════════════════════════════════════════════════════
# RareEarthAssociationSource 测试
# ═══════════════════════════════════════════════════════════════

class TestRareEarthSourceHTMLParsing:
    """HTML 解析单元测试。"""

    def test_parse_html_with_standard_format(self):
        src = RareEarthAssociationSource()

        html = """
        <html><body>
        <table>
        <tr><td>产品名称</td><td>价格(万元/吨)</td></tr>
        <tr><td>氧化镨钕</td><td>38.5万</td></tr>
        <tr><td>氧化镝Dy2O3</td><td>185.0万</td></tr>
        <tr><td>氧化钇Y2O3</td><td>4.2万</td></tr>
        </table>
        </body></html>
        """

        prices = src._parse_html(html)
        assert prices["prnd_oxide"] == 38.5
        assert prices["dysprosium_oxide"] == 185.0
        assert prices["yttrium_oxide"] == 4.2

    def test_parse_html_no_wan_suffix(self):
        """价格不带"万"字，靠纯数字匹配。"""
        src = RareEarthAssociationSource()

        html = """
        <html><body>
        <p>氧化镨钕 38.50</p>
        <p>氧化镝 185.00</p>
        </body></html>
        """

        prices = src._parse_html(html)
        assert prices["prnd_oxide"] == 38.5
        assert prices["dysprosium_oxide"] == 185.0

    def test_parse_html_partial_materials(self):
        """部分材料缺失的 HTML 只返回存在的。"""
        src = RareEarthAssociationSource()

        html = "<html><body><p>氧化镨钕 38.5万</p></body></html>"

        prices = src._parse_html(html)
        assert prices.get("prnd_oxide") == 38.5
        assert prices.get("dysprosium_oxide") is None

    def test_parse_html_no_materials(self):
        """HTML 中没有稀土材料关键词。"""
        src = RareEarthAssociationSource()

        html = "<html><body><p>没有相关数据</p></body></html>"

        prices = src._parse_html(html)
        assert all(v is None for v in prices.values())

    def test_parse_html_with_script_and_style_tags(self):
        """script/style 标签中的内容应被忽略。"""
        src = RareEarthAssociationSource()

        html = """
        <html><head>
        <script>var price="氧化镨钕 99.9万"; // should be ignored</script>
        <style>.price { content: "氧化镨钕 99.9"; }</style>
        </head><body>
        <p>氧化镨钕 38.5万</p>
        </body></html>
        """

        prices = src._parse_html(html)
        assert prices["prnd_oxide"] == 38.5  # script 中的 99.9 被忽略


class TestRareEarthSourceValidation:
    """价格校验测试。"""

    def test_price_in_range_valid(self):
        src = RareEarthAssociationSource()
        assert src._validate_price("prnd_oxide", 38.5) is True
        assert src._validate_price("dysprosium_oxide", 185.0) is True
        assert src._validate_price("yttrium_oxide", 4.2) is True

    def test_price_too_low_invalid(self):
        src = RareEarthAssociationSource()
        assert src._validate_price("prnd_oxide", 10.0) is False

    def test_price_too_high_invalid(self):
        src = RareEarthAssociationSource()
        assert src._validate_price("dysprosium_oxide", 500.0) is False

    def test_unknown_key_valid(self):
        src = RareEarthAssociationSource()
        assert src._validate_price("unknown_material", 999.0) is True


class TestRareEarthSourceFetch:
    """集成：fetch_prices 端到端。"""

    @pytest.mark.asyncio
    async def test_fetch_prices_with_valid_html(self):
        src = RareEarthAssociationSource()
        html = "<p>氧化镨钕 38.5万 | 氧化镝 185.0万 | 氧化钇 4.2万</p>"

        with patch.object(src, '_fetch_html', AsyncMock(return_value=html)):
            prices = await src.fetch_prices(["prnd_oxide", "dysprosium_oxide", "yttrium_oxide"])
            assert prices["prnd_oxide"] == 38.5
            assert prices["dysprosium_oxide"] == 185.0
            assert prices["yttrium_oxide"] == 4.2

    @pytest.mark.asyncio
    async def test_fetch_prices_unsupported_keys(self):
        src = RareEarthAssociationSource()
        prices = await src.fetch_prices(["cu_cathode", "al_ingot"])
        assert prices["cu_cathode"] is None
        assert prices["al_ingot"] is None

    @pytest.mark.asyncio
    async def test_fetch_prices_html_failure_fallback(self):
        """HTML 获取失败时返回参考价格。"""
        src = RareEarthAssociationSource()

        with patch.object(src, '_fetch_html', AsyncMock(return_value=None)):
            prices = await src.fetch_prices(["prnd_oxide", "dysprosium_oxide", "yttrium_oxide"])
            assert prices["prnd_oxide"] == _FALLBACK_REFERENCE_PRICES["prnd_oxide"]
            assert prices["dysprosium_oxide"] == _FALLBACK_REFERENCE_PRICES["dysprosium_oxide"]
            assert prices["yttrium_oxide"] == _FALLBACK_REFERENCE_PRICES["yttrium_oxide"]

    @pytest.mark.asyncio
    async def test_fetch_prices_invalid_price_uses_fallback(self):
        """解析出异常价格时使用参考价格。"""
        src = RareEarthAssociationSource()
        html = "<p>氧化镨钕 999.0万</p>"  # 超出合理范围

        with patch.object(src, '_fetch_html', AsyncMock(return_value=html)):
            prices = await src.fetch_prices(["prnd_oxide"])
            assert prices["prnd_oxide"] == _FALLBACK_REFERENCE_PRICES["prnd_oxide"]

    @pytest.mark.asyncio
    async def test_fetch_prices_mixed(self):
        """部分解析成功、部分失败的情况。"""
        src = RareEarthAssociationSource()
        html = "<p>氧化镨钕 38.5万</p>"  # 只有氧化镨钕

        with patch.object(src, '_fetch_html', AsyncMock(return_value=html)):
            prices = await src.fetch_prices(["prnd_oxide", "dysprosium_oxide", "yttrium_oxide"])
            assert prices["prnd_oxide"] == 38.5
            assert prices["dysprosium_oxide"] == _FALLBACK_REFERENCE_PRICES["dysprosium_oxide"]
            assert prices["yttrium_oxide"] == _FALLBACK_REFERENCE_PRICES["yttrium_oxide"]

    @pytest.mark.asyncio
    async def test_is_available_true(self):
        src = RareEarthAssociationSource()
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch.object(src, '_get_client', AsyncMock()) as mock_client:
            mock_client.return_value.head = AsyncMock(return_value=mock_resp)
            assert await src.is_available() is True

    @pytest.mark.asyncio
    async def test_is_available_false_on_exception(self):
        src = RareEarthAssociationSource()

        with patch.object(src, '_get_client', AsyncMock()) as mock_client:
            mock_client.return_value.head = AsyncMock(side_effect=Exception("Conn error"))
            assert await src.is_available() is False

    def test_supported_keys(self):
        assert "prnd_oxide" in _RE_SUPPORTED_KEYS
        assert "dysprosium_oxide" in _RE_SUPPORTED_KEYS
        assert "yttrium_oxide" in _RE_SUPPORTED_KEYS
        assert len(_RE_SUPPORTED_KEYS) == 3


# ═══════════════════════════════════════════════════════════════
# AsianMetalSource 测试
# ═══════════════════════════════════════════════════════════════

class TestAsianMetalSourceParsing:
    """亚洲金属网 HTML 解析测试。"""

    def test_parse_html_tantalum_powder(self):
        src = AsianMetalSource()

        html = """
        <html><body>
        <table>
        <tr><td>金属钽Ta</td><td>4500元/公斤</td></tr>
        <tr><td>钽丝</td><td>3200元/公斤</td></tr>
        </table>
        </body></html>
        """

        prices = src._parse_html(html)
        assert prices["tantalum_powder"] == 4500.0
        assert prices["tantalum_wire"] == 3200.0

    def test_parse_html_cny_format(self):
        """CNY 格式价格。"""
        src = AsianMetalSource()

        html = "<html><body><p>钽粉 4500 CNY/公斤 钽丝 3200 CNY</p></body></html>"

        prices = src._parse_html(html)
        assert prices["tantalum_powder"] == 4500.0
        assert prices["tantalum_wire"] == 3200.0

    def test_parse_html_no_materials(self):
        src = AsianMetalSource()

        html = "<html><body><p>暂无报价</p></body></html>"

        prices = src._parse_html(html)
        assert all(v is None for v in prices.values())

    def test_price_with_comma(self):
        """千分位逗号格式。"""
        src = AsianMetalSource()
        # 测试 _PRICE_NUM_RE 的逗号处理
        text = "钽粉 4,500 元/公斤"
        price = src._extract_price(text, "钽粉")
        assert price == 4500.0


class TestAsianMetalSourceFetch:
    """集成测试。"""

    @pytest.mark.asyncio
    async def test_fetch_prices_success(self):
        src = AsianMetalSource()
        html = "<p>钽粉 4500元/公斤 钽丝 3200元/公斤</p>"

        with patch.object(src, '_fetch_html', AsyncMock(return_value=html)):
            prices = await src.fetch_prices(["tantalum_powder", "tantalum_wire"])
            assert prices["tantalum_powder"] == 4500.0
            assert prices["tantalum_wire"] == 3200.0

    @pytest.mark.asyncio
    async def test_fetch_prices_fallback(self):
        src = AsianMetalSource()

        with patch.object(src, '_fetch_html', AsyncMock(return_value=None)):
            prices = await src.fetch_prices(["tantalum_powder", "tantalum_wire"])
            assert prices["tantalum_powder"] == _SM_FALLBACK_PRICES["tantalum_powder"]
            assert prices["tantalum_wire"] == _SM_FALLBACK_PRICES["tantalum_wire"]

    @pytest.mark.asyncio
    async def test_fetch_prices_unsupported_keys(self):
        src = AsianMetalSource()
        prices = await src.fetch_prices(["cu_cathode", "nickel_powder"])
        assert prices["cu_cathode"] is None
        assert prices["nickel_powder"] is None

    @pytest.mark.asyncio
    async def test_fetch_prices_out_of_range_price(self):
        """解析出异常价格使用降级值。"""
        src = AsianMetalSource()
        html = "<p>钽粉 50元/公斤</p>"  # 低于有效范围

        with patch.object(src, '_fetch_html', AsyncMock(return_value=html)):
            prices = await src.fetch_prices(["tantalum_powder"])
            assert prices["tantalum_powder"] == _SM_FALLBACK_PRICES["tantalum_powder"]

    def test_supported_keys(self):
        assert "tantalum_powder" in _SM_SUPPORTED_KEYS
        assert "tantalum_wire" in _SM_SUPPORTED_KEYS
        assert "barium_carbonate" in _SM_SUPPORTED_KEYS

    @pytest.mark.asyncio
    async def test_is_available_true(self):
        src = AsianMetalSource()
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch.object(src, '_get_client', AsyncMock()) as mock_client:
            mock_client.return_value.head = AsyncMock(return_value=mock_resp)
            assert await src.is_available() is True


# ═══════════════════════════════════════════════════════════════
# BaiinfoSource 测试
# ═══════════════════════════════════════════════════════════════

class TestBaiinfoSource:
    """百川盈孚数据源测试。"""

    @pytest.mark.asyncio
    async def test_fetch_prices_barium_carbonate(self):
        src = BaiinfoSource()
        html = "<p>碳酸钡 3200元/吨</p>"

        with patch.object(src, '_fetch_html', AsyncMock(return_value=html)):
            prices = await src.fetch_prices(["barium_carbonate"])
            assert prices["barium_carbonate"] == 3200.0

    @pytest.mark.asyncio
    async def test_fetch_prices_fallback(self):
        src = BaiinfoSource()

        with patch.object(src, '_fetch_html', AsyncMock(return_value=None)):
            prices = await src.fetch_prices(["barium_carbonate"])
            assert prices["barium_carbonate"] == _SM_FALLBACK_PRICES["barium_carbonate"]

    @pytest.mark.asyncio
    async def test_fetch_prices_unsupported(self):
        src = BaiinfoSource()
        prices = await src.fetch_prices(["cu_cathode", "al_ingot"])
        assert prices["cu_cathode"] is None
        assert prices["al_ingot"] is None

    @pytest.mark.asyncio
    async def test_parse_html(self):
        src = BaiinfoSource()
        html = "<p>碳酸钡 BaCO3 3200 元/吨</p>"
        prices = src._parse_html(html)
        assert prices["barium_carbonate"] == 3200.0


# ═══════════════════════════════════════════════════════════════
# MaterialPriceService 稀土域多源集成测试
# ═══════════════════════════════════════════════════════════════

class TestMaterialPriceServiceRareEarthIntegration:
    """MaterialPriceService 稀土域多源降级集成测试。"""

    @pytest.mark.asyncio
    async def test_rare_earth_domain_multi_source(self):
        """稀土域应使用多源列表，主源处理稀土氧化物，AsianMetal 处理钽。"""
        from app.services.material_price_service import MaterialPriceService
        from app.services.sources.materials.base import MaterialPriceSource

        class MockReSource(MaterialPriceSource):
            source_name = "mock_re"
            async def fetch_prices(self, keys):
                return {"prnd_oxide": 38.5, "dysprosium_oxide": 185.0, "yttrium_oxide": 4.2}
            async def is_available(self):
                return True

        class MockTaSource(MaterialPriceSource):
            source_name = "mock_ta"
            async def fetch_prices(self, keys):
                return {"tantalum_powder": 4500.0, "tantalum_wire": 3200.0}
            async def is_available(self):
                return True

        svc = MaterialPriceService(rare_earth_sources=[MockReSource(), MockTaSource()])

        prices = await svc.get_prices([
            "prnd_oxide", "dysprosium_oxide", "yttrium_oxide",
            "tantalum_powder", "tantalum_wire",
        ])

        assert prices["prnd_oxide"] == 38.5
        assert prices["dysprosium_oxide"] == 185.0
        assert prices["yttrium_oxide"] == 4.2
        assert prices["tantalum_powder"] == 4500.0
        assert prices["tantalum_wire"] == 3200.0

    @pytest.mark.asyncio
    async def test_rare_earth_fallback_chain(self):
        """主源失败时备源应接替。"""
        from app.services.material_price_service import MaterialPriceService
        from app.services.sources.materials.base import MaterialPriceSource

        class FailingSource(MaterialPriceSource):
            source_name = "mock_failing"
            async def fetch_prices(self, keys):
                raise RuntimeError("simulated failure")
            async def is_available(self):
                return True

        class WorkingSource(MaterialPriceSource):
            source_name = "mock_working"
            async def fetch_prices(self, keys):
                return {"prnd_oxide": 38.5, "yttrium_oxide": 4.2}
            async def is_available(self):
                return True

        svc = MaterialPriceService(rare_earth_sources=[FailingSource(), WorkingSource()])

        prices = await svc.get_prices(["prnd_oxide", "yttrium_oxide"])
        assert prices["prnd_oxide"] == 38.5
        assert prices["yttrium_oxide"] == 4.2

    @pytest.mark.asyncio
    async def test_rare_earth_all_sources_fail(self):
        """所有稀土源失败时返回 None。"""
        from app.services.material_price_service import MaterialPriceService
        from app.services.sources.materials.base import MaterialPriceSource

        class FailingSource(MaterialPriceSource):
            source_name = "mock_fail"
            async def fetch_prices(self, keys):
                raise RuntimeError("fail")
            async def is_available(self):
                return True

        svc = MaterialPriceService(rare_earth_sources=[FailingSource()])

        prices = await svc.get_prices(["prnd_oxide", "tantalum_powder"])
        assert prices["prnd_oxide"] is None
        assert prices["tantalum_powder"] is None

        # 应标记为 degraded
        stats = svc.get_cache_stats()
        assert stats["degraded"] >= 2

    @pytest.mark.asyncio
    async def test_mixed_domains_with_rare_earth(self):
        """有色金属域 + 稀土域 并行查询。"""
        from app.services.material_price_service import MaterialPriceService
        from app.services.sources.materials.base import MaterialPriceSource

        class MockMetals(MaterialPriceSource):
            source_name = "mock_metals"
            async def fetch_prices(self, keys):
                return {"cu_cathode": 78200.0, "al_ingot": 21500.0}
            async def is_available(self):
                return True

        class MockReSource(MaterialPriceSource):
            source_name = "mock_re"
            async def fetch_prices(self, keys):
                return {"prnd_oxide": 38.5}
            async def is_available(self):
                return True

        svc = MaterialPriceService(
            metals_source=MockMetals(),
            rare_earth_sources=[MockReSource()],
        )

        prices = await svc.get_prices(["cu_cathode", "prnd_oxide"])
        assert prices["cu_cathode"] == 78200.0
        assert prices["prnd_oxide"] == 38.5

    def test_default_rare_earth_sources_created(self):
        """未传 rare_earth_sources 时自动创建三个默认源。"""
        from app.services.material_price_service import MaterialPriceService
        svc = MaterialPriceService()
        assert len(svc._rare_earth_sources) == 3
        names = [s.source_name for s in svc._rare_earth_sources]
        assert "re_association" in names
        assert "asian_metal" in names
        assert "baiinfo" in names
