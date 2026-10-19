"""化工&非金属数据源测试。

测试范围:
- Chemical100ppiSource: 生意社 HTML 解析、6 种化工材料价格提取、校验、降级
- Sci99Source: 卓创资讯钛白粉 HTML 解析、降级
- MaterialPriceService 化工域多源集成
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.sources.materials.chemical_source import (
    Chemical100ppiSource,
    Sci99Source,
    _CHEM_SUPPORTED_KEYS,
    _CHEM_FALLBACK_PRICES,
)


# ═══════════════════════════════════════════════════════════════
# Chemical100ppiSource 测试
# ═══════════════════════════════════════════════════════════════

class TestChemicalSourceHTMLParsing:
    """生意社 HTML 解析单元测试。"""

    def test_parse_html_all_six_materials(self):
        """解析包含全部 6 种化工材料的 HTML。"""
        src = Chemical100ppiSource()

        html = """
        <html><body>
        <table>
        <tr><td>双酚A</td><td>13000元/吨</td></tr>
        <tr><td>环氧树脂</td><td>15000元/吨</td></tr>
        <tr><td>聚丙烯PP粒料</td><td>8000元/吨</td></tr>
        <tr><td>PET切片</td><td>9000元/吨</td></tr>
        <tr><td>钛白粉TiO2</td><td>16000元/吨</td></tr>
        <tr><td>二氧化锰</td><td>12000元/吨</td></tr>
        </table>
        </body></html>
        """

        prices = src._parse_html(html)
        assert prices["ba_resin"] == 13000.0
        assert prices["epoxy_resin"] == 15000.0
        assert prices["polypropylene"] == 8000.0
        assert prices["polyester_pet"] == 9000.0
        assert prices["titanium_dioxide"] == 16000.0
        assert prices["manganese_dioxide"] == 12000.0

    def test_parse_html_partial_materials(self):
        """部分材料缺失。"""
        src = Chemical100ppiSource()

        html = "<p>双酚A 13000元/吨 环氧树脂 15000元/吨</p>"

        prices = src._parse_html(html)
        assert prices["ba_resin"] == 13000.0
        assert prices["epoxy_resin"] == 15000.0
        assert prices.get("polypropylene") is None

    def test_parse_html_no_materials(self):
        """HTML 中没有化工材料关键词。"""
        src = Chemical100ppiSource()

        html = "<p>暂无化工报价</p>"

        prices = src._parse_html(html)
        assert all(v is None for v in prices.values())

    def test_parse_price_with_comma(self):
        """千分位逗号格式价格。"""
        src = Chemical100ppiSource()

        html = "<p>环氧树脂 15,000元/吨</p>"

        prices = src._parse_html(html)
        assert prices["epoxy_resin"] == 15000.0

    def test_parse_alternate_keywords(self):
        """测试备选关键词匹配。"""
        src = Chemical100ppiSource()

        # 双酚A 的其他写法
        html1 = "<p>BPA 13000元/吨</p>"
        prices = src._parse_html(html1)
        assert prices["ba_resin"] == 13000.0

        # 聚酯的不同写法
        html2 = "<p>PET树脂 9000元/吨</p>"
        prices = src._parse_html(html2)
        assert prices["polyester_pet"] == 9000.0

    def test_parse_html_script_tags_ignored(self):
        """script 标签中的价格不应被提取。"""
        src = Chemical100ppiSource()

        html = """
        <script>var price="双酚A 99999元/吨";</script>
        <p>双酚A 13000元/吨</p>
        """

        prices = src._parse_html(html)
        assert prices["ba_resin"] == 13000.0

    def test_parse_price_multiple_keywords_same_text(self):
        """多个材料关键词在同一文本中, 各自应提取正确价格。"""
        src = Chemical100ppiSource()

        html = "<p>双酚A 13000 环氧树脂 15000 聚丙烯 8000 PET 9000 钛白粉 16000 二氧化锰 12000 元/吨</p>"

        prices = src._parse_html(html)
        assert prices["ba_resin"] == 13000.0
        assert prices["epoxy_resin"] == 15000.0
        assert prices["polypropylene"] == 8000.0
        assert prices["polyester_pet"] == 9000.0
        assert prices["titanium_dioxide"] == 16000.0
        assert prices["manganese_dioxide"] == 12000.0


class TestChemicalSourceValidation:
    """价格校验测试。"""

    def test_price_in_range_valid(self):
        src = Chemical100ppiSource()
        assert src._validate_price("ba_resin", 13000.0) is True
        assert src._validate_price("polypropylene", 8000.0) is True
        assert src._validate_price("titanium_dioxide", 16000.0) is True

    def test_price_too_low_invalid(self):
        src = Chemical100ppiSource()
        assert src._validate_price("ba_resin", 1000.0) is False

    def test_price_too_high_invalid(self):
        src = Chemical100ppiSource()
        assert src._validate_price("polypropylene", 50000.0) is False


class TestChemicalSourceFetch:
    """集成：fetch_prices 端到端。"""

    @pytest.mark.asyncio
    async def test_fetch_prices_success(self):
        src = Chemical100ppiSource()
        html = "<p>双酚A 13000 环氧树脂 15000 聚丙烯 8000 PET 9000 钛白粉 16000 二氧化锰 12000 元/吨</p>"

        with patch.object(src, '_fetch_html', AsyncMock(return_value=html)):
            prices = await src.fetch_prices([
                "ba_resin", "epoxy_resin", "polypropylene",
                "polyester_pet", "titanium_dioxide", "manganese_dioxide",
            ])
            assert prices["ba_resin"] == 13000.0
            assert prices["epoxy_resin"] == 15000.0
            assert prices["polypropylene"] == 8000.0
            assert prices["polyester_pet"] == 9000.0
            assert prices["titanium_dioxide"] == 16000.0
            assert prices["manganese_dioxide"] == 12000.0

    @pytest.mark.asyncio
    async def test_fetch_prices_fallback(self):
        src = Chemical100ppiSource()

        with patch.object(src, '_fetch_html', AsyncMock(return_value=None)):
            prices = await src.fetch_prices(["ba_resin", "epoxy_resin"])
            assert prices["ba_resin"] == _CHEM_FALLBACK_PRICES["ba_resin"]
            assert prices["epoxy_resin"] == _CHEM_FALLBACK_PRICES["epoxy_resin"]

    @pytest.mark.asyncio
    async def test_fetch_prices_unsupported_keys(self):
        src = Chemical100ppiSource()
        prices = await src.fetch_prices(["cu_cathode", "prnd_oxide"])
        assert prices["cu_cathode"] is None
        assert prices["prnd_oxide"] is None

    @pytest.mark.asyncio
    async def test_fetch_prices_out_of_range_fallback(self):
        """解析出异常价格使用降级值。"""
        src = Chemical100ppiSource()
        html = "<p>双酚A 99999元/吨</p>"

        with patch.object(src, '_fetch_html', AsyncMock(return_value=html)):
            prices = await src.fetch_prices(["ba_resin"])
            assert prices["ba_resin"] == _CHEM_FALLBACK_PRICES["ba_resin"]

    def test_supported_keys(self):
        assert "ba_resin" in _CHEM_SUPPORTED_KEYS
        assert "epoxy_resin" in _CHEM_SUPPORTED_KEYS
        assert "polypropylene" in _CHEM_SUPPORTED_KEYS
        assert "polyester_pet" in _CHEM_SUPPORTED_KEYS
        assert "titanium_dioxide" in _CHEM_SUPPORTED_KEYS
        assert "manganese_dioxide" in _CHEM_SUPPORTED_KEYS
        assert len(_CHEM_SUPPORTED_KEYS) == 6

    @pytest.mark.asyncio
    async def test_is_available_true(self):
        src = Chemical100ppiSource()
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch.object(src, '_get_client', AsyncMock()) as mock_client:
            mock_client.return_value.head = AsyncMock(return_value=mock_resp)
            assert await src.is_available() is True


# ═══════════════════════════════════════════════════════════════
# Sci99Source 测试
# ═══════════════════════════════════════════════════════════════

class TestSci99Source:
    """卓创资讯数据源测试。"""

    @pytest.mark.asyncio
    async def test_fetch_prices_titanium_dioxide(self):
        src = Sci99Source()
        html = "<p>钛白粉 16000元/吨</p>"

        with patch.object(src, '_fetch_html', AsyncMock(return_value=html)):
            prices = await src.fetch_prices(["titanium_dioxide"])
            assert prices["titanium_dioxide"] == 16000.0

    @pytest.mark.asyncio
    async def test_fetch_prices_fallback(self):
        src = Sci99Source()

        with patch.object(src, '_fetch_html', AsyncMock(return_value=None)):
            prices = await src.fetch_prices(["titanium_dioxide"])
            assert prices["titanium_dioxide"] == _CHEM_FALLBACK_PRICES["titanium_dioxide"]

    @pytest.mark.asyncio
    async def test_fetch_prices_unsupported(self):
        src = Sci99Source()
        prices = await src.fetch_prices(["ba_resin", "epoxy_resin"])
        assert prices["ba_resin"] is None
        assert prices["epoxy_resin"] is None

    def test_parse_html(self):
        src = Sci99Source()
        html = "<p>钛白粉 16000元/吨</p>"
        prices = src._parse_html(html)
        assert prices["titanium_dioxide"] == 16000.0


# ═══════════════════════════════════════════════════════════════
# MaterialPriceService 化工域集成测试
# ═══════════════════════════════════════════════════════════════

class TestMaterialPriceServiceChemicalIntegration:
    """MaterialPriceService 化工域多源集成测试。"""

    @pytest.mark.asyncio
    async def test_chemical_domain_all_materials(self):
        """化工域 6 种材料完整查询。"""
        from app.services.material_price_service import MaterialPriceService
        from app.services.sources.materials.base import MaterialPriceSource

        class MockChemSource(MaterialPriceSource):
            source_name = "mock_chem"
            async def fetch_prices(self, keys):
                return {
                    "ba_resin": 13000.0,
                    "epoxy_resin": 15000.0,
                    "polypropylene": 8000.0,
                    "polyester_pet": 9000.0,
                    "titanium_dioxide": 16000.0,
                    "manganese_dioxide": 12000.0,
                }
            async def is_available(self):
                return True

        svc = MaterialPriceService(chemical_sources=[MockChemSource()])

        # 只测 chemical 域材料 (titanium_dioxide/manganese_dioxide 在 rare_earth 域)
        prices = await svc.get_prices([
            "ba_resin", "epoxy_resin", "polypropylene", "polyester_pet",
        ])

        assert prices["ba_resin"] == 13000.0
        assert prices["epoxy_resin"] == 15000.0
        assert prices["polypropylene"] == 8000.0
        assert prices["polyester_pet"] == 9000.0

    @pytest.mark.asyncio
    async def test_chemical_fallback_chain(self):
        """主源失败, 备源接替。"""
        from app.services.material_price_service import MaterialPriceService
        from app.services.sources.materials.base import MaterialPriceSource

        class FailingChemSource(MaterialPriceSource):
            source_name = "mock_fail"
            async def fetch_prices(self, keys):
                raise RuntimeError("fail")
            async def is_available(self):
                return True

        class WorkingChemSource(MaterialPriceSource):
            source_name = "mock_ok"
            async def fetch_prices(self, keys):
                return {"ba_resin": 13000.0, "polyester_pet": 9000.0}
            async def is_available(self):
                return True

        svc = MaterialPriceService(chemical_sources=[FailingChemSource(), WorkingChemSource()])

        # 用 chemical 域材料测试 fallback
        prices = await svc.get_prices(["ba_resin", "polyester_pet"])
        # FailingChemSource 抛异常, WorkingChemSource 接管
        assert prices["ba_resin"] == 13000.0
        assert prices["polyester_pet"] == 9000.0

    def test_default_chemical_sources_created(self):
        """未传 chemical_sources 时自动创建 2 个默认源。"""
        from app.services.material_price_service import MaterialPriceService
        svc = MaterialPriceService()
        assert len(svc._chemical_sources) == 2
        names = [s.source_name for s in svc._chemical_sources]
        assert "chem_100ppi" in names
        assert "sci99" in names
