"""T2-016 SMM/Mysteel/LME 数据源骨架 测试。

覆盖：
- 未配置时 is_available 返回 False
- 未配置时 fetch_prices 返回全 None（不抛异常）
- health_check 行为
- 降级逻辑
- 与现有服务集成
"""

import asyncio
import sys
import unittest
from unittest.mock import MagicMock, patch, AsyncMock

sys.path.insert(0, "/app/data/所有对话/主对话/BOM系统v4改造/backend")

from app.services.sources.materials.smm_source import SMMSource
from app.services.sources.materials.mysteel_source import MysteelSource
from app.services.sources.materials.lme_source import LMESource


def run_async(coro):
    """运行异步协程。"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestSMMSource(unittest.TestCase):
    """T2-016 SMM 上海有色网数据源测试。"""

    def test_01_not_configured_by_default(self):
        """默认未配置时 is_configured 为 False。"""
        src = SMMSource(api_key="", enabled=False)
        self.assertFalse(src.is_configured)

    def test_02_not_available_when_unconfigured(self):
        """未配置时 is_available 返回 False。"""
        src = SMMSource(api_key="", enabled=False)
        result = run_async(src.is_available())
        self.assertFalse(result)

    def test_03_fetch_prices_returns_none_when_unconfigured(self):
        """未配置时 fetch_prices 返回全 None，不抛异常。"""
        src = SMMSource(api_key="", enabled=False)
        result = run_async(src.fetch_prices(["cu_cathode", "al_ingot"]))
        self.assertEqual(result, {"cu_cathode": None, "al_ingot": None})

    def test_04_configured_with_api_key(self):
        """配置 API Key 后 is_configured 为 True。"""
        src = SMMSource(api_key="test-key", enabled=True)
        self.assertTrue(src.is_configured)

    def test_05_fetch_uncovered_materials(self):
        """查询非 SMM 覆盖品种时返回全 None。"""
        src = SMMSource(api_key="test-key", enabled=True)
        result = run_async(src.fetch_prices(["unknown_material"]))
        self.assertEqual(result, {"unknown_material": None})

    def test_06_source_name(self):
        """数据源名称为 smm。"""
        src = SMMSource()
        self.assertEqual(src.source_name, "smm")

    def test_07_close_without_client(self):
        """未初始化客户端时 close 不抛异常。"""
        src = SMMSource()
        run_async(src.close())  # 应不报错


class TestMysteelSource(unittest.TestCase):
    """T2-016 Mysteel 我的钢铁网数据源测试。"""

    def test_01_not_configured_by_default(self):
        """默认未配置。"""
        src = MysteelSource(api_key="", enabled=False)
        self.assertFalse(src.is_configured)

    def test_02_not_available_when_unconfigured(self):
        """未配置时不可用。"""
        src = MysteelSource(api_key="", enabled=False)
        result = run_async(src.is_available())
        self.assertFalse(result)

    def test_03_fetch_prices_returns_none(self):
        """未配置时 fetch_prices 返回全 None。"""
        src = MysteelSource(api_key="", enabled=False)
        result = run_async(src.fetch_prices(["cold_rolled", "hot_rolled"]))
        self.assertEqual(result, {"cold_rolled": None, "hot_rolled": None})

    def test_04_configured_with_api_key(self):
        """配置后 is_configured 为 True。"""
        src = MysteelSource(api_key="test-key", enabled=True)
        self.assertTrue(src.is_configured)

    def test_05_fetch_uncovered_materials(self):
        """非覆盖品种返回 None。"""
        src = MysteelSource(api_key="test-key", enabled=True)
        result = run_async(src.fetch_prices(["cu_cathode"]))
        self.assertEqual(result, {"cu_cathode": None})

    def test_06_source_name(self):
        """数据源名称为 mysteel。"""
        src = MysteelSource()
        self.assertEqual(src.source_name, "mysteel")


class TestLMESource(unittest.TestCase):
    """T2-016 LME 伦敦金属交易所数据源测试。"""

    def test_01_not_enabled_by_default(self):
        """默认未启用。"""
        src = LMESource(enabled=False)
        self.assertFalse(src.is_configured)

    def test_02_not_available_when_disabled(self):
        """未启用时不可用。"""
        src = LMESource(enabled=False)
        result = run_async(src.is_available())
        self.assertFalse(result)

    def test_03_fetch_prices_returns_none_when_disabled(self):
        """未启用时 fetch_prices 返回全 None。"""
        src = LMESource(enabled=False)
        result = run_async(src.fetch_prices(["cu_cathode", "al_ingot"]))
        self.assertEqual(result, {"cu_cathode": None, "al_ingot": None})

    def test_04_enabled_state(self):
        """启用后 is_configured 为 True。"""
        src = LMESource(enabled=True)
        self.assertTrue(src.is_configured)

    def test_05_source_name(self):
        """数据源名称为 lme。"""
        src = LMESource()
        self.assertEqual(src.source_name, "lme")

    def test_06_default_data_url(self):
        """默认数据 URL 正确。"""
        src = LMESource()
        self.assertIn("lme.com", src._data_url)


class TestMaterialSourcesIntegration(unittest.TestCase):
    """T2-016 数据源集成测试：与现有服务协同。"""

    def test_10_all_sources_importable(self):
        """三个数据源可从 materials 包导入。"""
        from app.services.sources.materials import SMMSource, MysteelSource, LMESource
        self.assertIsNotNone(SMMSource)
        self.assertIsNotNone(MysteelSource)
        self.assertIsNotNone(LMESource)

    def test_11_all_sources_are_material_price_source(self):
        """三个数据源均继承 MaterialPriceSource。"""
        from app.services.sources.materials.base import MaterialPriceSource
        self.assertTrue(issubclass(SMMSource, MaterialPriceSource))
        self.assertTrue(issubclass(MysteelSource, MaterialPriceSource))
        self.assertTrue(issubclass(LMESource, MaterialPriceSource))

    def test_12_unconfigured_sources_dont_crash(self):
        """所有数据源未配置时系统正常运行。"""
        sources = [
            SMMSource(api_key="", enabled=False),
            MysteelSource(api_key="", enabled=False),
            LMESource(enabled=False),
        ]
        for src in sources:
            result = run_async(src.fetch_prices(["cu_cathode"]))
            self.assertEqual(result, {"cu_cathode": None})

    def test_13_config_has_new_fields(self):
        """config.py 包含 T2-016 新增配置项。"""
        from app.config import settings
        self.assertFalse(settings.smm_enabled)
        self.assertFalse(settings.mysteel_enabled)
        self.assertFalse(settings.lme_enabled)
        self.assertEqual(settings.smm_api_key, "")
        self.assertEqual(settings.mysteel_api_key, "")


if __name__ == "__main__":
    unittest.main()
