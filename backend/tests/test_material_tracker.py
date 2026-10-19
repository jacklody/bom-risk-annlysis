"""MaterialTracker 追踪器测试。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, timezone

from app.services.material_tracker import (
    MaterialTracker,
    MaterialTracking,
    PRICE_CHANGE_YELLOW,
    PRICE_CHANGE_ORANGE,
    PRICE_CHANGE_RED,
    PRICE_DROP_GREEN,
)
from app.knowledge.material_mapping import RARE_EARTH_AMPLIFIER


class TestChangePctCalculation:
    """百分比变化计算测试。"""

    @pytest.mark.parametrize("current,baseline,expected", [
        (110, 100, 10.0),    # 涨 10%
        (120, 100, 20.0),    # 涨 20%
        (105, 100, 5.0),     # 涨 5%
        (90, 100, -10.0),    # 跌 10%
        (100, 100, 0.0),     # 不变
        (200, 100, 100.0),   # 翻倍
        (50, 100, -50.0),    # 腰斩
    ])
    def test_calc_change_pct(self, current, baseline, expected):
        result = MaterialTracker._calc_change_pct(current, baseline)
        assert result == pytest.approx(expected)

    def test_calc_change_none_current(self):
        result = MaterialTracker._calc_change_pct(None, 100)
        assert result == 0.0

    def test_calc_change_none_baseline(self):
        result = MaterialTracker._calc_change_pct(110, None)
        assert result == 0.0

    def test_calc_change_zero_baseline(self):
        result = MaterialTracker._calc_change_pct(110, 0)
        assert result == 0.0


class TestRiskLevelDetermination:
    """风险等级判定测试。"""

    @pytest.mark.parametrize("change_pct,expected_level", [
        (25.0, "RED"),      # ≥20%
        (20.0, "RED"),      # 边界
        (19.9, "ORANGE"),   # 刚好低于 RED
        (15.0, "ORANGE"),   # ≥10%
        (10.0, "ORANGE"),   # 边界
        (9.9, "YELLOW"),    # 刚好低于 ORANGE
        (6.0, "YELLOW"),    # ≥5%
        (5.0, "YELLOW"),    # 边界
        (4.9, "NORMAL"),    # 正常
        (0.0, "NORMAL"),    # 不变
        (-5.0, "NORMAL"),   # 小跌
        (-9.9, "NORMAL"),   # 接近阈值
        (-10.0, "GREEN"),   # 采购窗口
        (-15.0, "GREEN"),   # 采购窗口
    ])
    def test_risk_level(self, change_pct, expected_level):
        level = MaterialTracker._determine_risk_level(change_pct)
        assert level == expected_level


class TestMaterialTrackingDataclass:
    """MaterialTracking 数据类测试。"""

    def test_has_alert_red(self):
        mt = MaterialTracking(material_key="cu", risk_level="RED")
        assert mt.has_alert is True

    def test_has_alert_orange(self):
        mt = MaterialTracking(material_key="cu", risk_level="ORANGE")
        assert mt.has_alert is True

    def test_has_alert_yellow(self):
        mt = MaterialTracking(material_key="cu", risk_level="YELLOW")
        assert mt.has_alert is True

    def test_has_alert_green(self):
        mt = MaterialTracking(material_key="cu", risk_level="GREEN")
        assert mt.has_alert is True

    def test_has_alert_normal(self):
        mt = MaterialTracking(material_key="cu", risk_level="NORMAL")
        assert mt.has_alert is False

    def test_default_values(self):
        mt = MaterialTracking(material_key="test_key")
        assert mt.risk_level == "NORMAL"
        assert mt.current_price is None
        assert mt.change_pct == 0.0
        assert mt.degraded is False
        assert mt.affected_categories == []


class TestMaterialTrackerIntegration:
    """MaterialTracker 集成测试（使用 Mock DB）。"""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        # 模拟批量查询返回空结果（无历史数据）
        result = MagicMock()
        result.all.return_value = []
        db.execute.return_value = result
        return db

    @pytest.fixture
    def mock_price_service(self):
        svc = AsyncMock()
        svc.get_prices.return_value = {
            "cu_cathode": 78200.0,
            "al_ingot": 21500.0,
            "ag_ingot": 7.8,
            "nickel_powder": 135000.0,
        }
        return svc

    @pytest.mark.asyncio
    async def test_calculate_baselines_supports_sync_session(self, mock_price_service):
        """FastAPI 依赖注入的同步 Session 也应能查询基线，避免材料链路接口 500。"""
        sync_db = MagicMock()
        result = MagicMock()
        result.all.return_value = [("cu_cathode", 68000.0)]
        sync_db.execute.return_value = result

        tracker = MaterialTracker(sync_db, mock_price_service)
        baselines = await tracker._calculate_baselines(["cu_cathode"], datetime.now(timezone.utc) - timedelta(days=30))

        assert baselines == {"cu_cathode": 68000.0}

    @pytest.mark.asyncio
    async def test_normal_risk_material_is_counted_as_normal_alert_state(self, mock_db, mock_price_service):
        """无涨跌风险的材料应明确归入 NORMAL，供材料链路页面汇总卡片展示。"""
        tracker = MaterialTracker(mock_db, mock_price_service)
        results = await tracker.track_materials(["cu_cathode"])

        assert results["cu_cathode"].risk_level == "NORMAL"
        assert results["cu_cathode"].has_alert is False

    @pytest.mark.asyncio
    async def test_track_with_no_history(self, mock_db, mock_price_service):
        """无历史基线时，change_pct 为 0，risk_level 为 NORMAL。"""
        tracker = MaterialTracker(mock_db, mock_price_service)
        results = await tracker.track_materials(["cu_cathode", "al_ingot"])

        assert len(results) == 2
        cu = results["cu_cathode"]
        assert cu.current_price == 78200.0
        assert cu.change_pct == 0.0  # 无历史基线，变化为 0
        assert cu.risk_level == "NORMAL"
        assert cu.material_name_zh == "电解铜"

    @pytest.mark.asyncio
    async def test_track_rare_earth_amplification(self, mock_db, mock_price_service):
        """稀土材料的传导系数应被放大。"""
        mock_price_service.get_prices.return_value = {
            "dysprosium_oxide": 260.0,  # 万元/吨
        }

        tracker = MaterialTracker(mock_db, mock_price_service)
        results = await tracker.track_materials(["dysprosium_oxide"])

        dy = results["dysprosium_oxide"]
        # cost_ratio=0.06 × RARE_EARTH_AMPLIFIER=1.6 × price_multiplier=1.0 = 0.096
        expected_ratio = 0.06 * RARE_EARTH_AMPLIFIER
        assert dy.adjusted_cost_ratio == pytest.approx(expected_ratio)

    @pytest.mark.asyncio
    async def test_track_unknown_material_skipped(self, mock_db, mock_price_service):
        """未知材料 key 应被忽略。"""
        tracker = MaterialTracker(mock_db, mock_price_service)
        results = await tracker.track_materials(["nonexistent_key"])
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_track_without_price_service(self, mock_db):
        """无 price_service 时，所有价格为 None。"""
        tracker = MaterialTracker(mock_db, price_service=None)
        results = await tracker.track_materials(["cu_cathode"])
        cu = results["cu_cathode"]
        assert cu.current_price is None
        assert cu.risk_level == "NORMAL"

    @pytest.mark.asyncio
    async def test_get_alert_signals_only_active(self, mock_db, mock_price_service):
        """get_alert_signals 仅返回非 NORMAL 材料的信号。"""
        # 注入有历史数据的基线，制造涨 15% 的场景
        from app.models.material_price import MaterialPrice
        baseline = datetime.now(timezone.utc) - timedelta(days=10)

        mock_row = MagicMock()
        mock_row.material_key = "cu_cathode"
        mock_row._mapping = {"material_key": "cu_cathode", "avg_price": 68000.0}

        result = MagicMock()
        result.all.return_value = [(mock_row._mapping["material_key"], mock_row._mapping["avg_price"])]
        mock_db.execute.return_value = result

        tracker = MaterialTracker(mock_db, mock_price_service)
        signals = await tracker.get_alert_signals("relay")

        # cu_cathode: current=78200, baseline=68000 → change=15% → ORANGE → score=15×0.12=1.8
        assert "cu_cathode_score" in signals
        assert signals["cu_cathode_score"] == pytest.approx(1.8)

    @pytest.mark.asyncio
    async def test_track_for_category(self, mock_db, mock_price_service):
        """track_for_category 应按品类返回全部关联材料。"""
        tracker = MaterialTracker(mock_db, mock_price_service)
        results = await tracker.track_for_category("aluminum_heat_sink")
        assert len(results) == 1
        assert "al_ingot" in results


# ═══════════════════════════════════════════════════════════════════════
# T2-017 数据新鲜度监控模块测试
# ═══════════════════════════════════════════════════════════════════════

from app.services.material_tracker import (
    FreshnessMonitor,
    get_source_threshold,
    SOURCE_FRESHNESS_THRESHOLDS,
    DEFAULT_FRESHNESS_THRESHOLD,
)
from app.models.material_price import (
    MaterialPrice,
    FreshnessResult,
    FreshnessAlert,
    SourceHealth,
    MaterialPriceRecord,
)


class TestSourceThreshold:
    """数据源阈值配置测试。"""

    def test_smm_threshold(self):
        assert get_source_threshold("smm") == 24.0

    def test_mysteel_threshold(self):
        assert get_source_threshold("mysteel") == 24.0

    def test_lme_threshold(self):
        assert get_source_threshold("lme") == 48.0

    def test_unknown_source_default(self):
        assert get_source_threshold("unknown_source") == 72.0

    def test_threshold_case_insensitive(self):
        assert get_source_threshold("SMM") == 24.0
        assert get_source_threshold("LME") == 48.0

    def test_threshold_partial_match(self):
        assert get_source_threshold("smm_api_v2") == 24.0
        assert get_source_threshold("lme_data") == 48.0


class TestFreshnessResultModel:
    """FreshnessResult 模型测试。"""

    def test_create_ok_result(self):
        result = FreshnessResult(
            material_key="cu_cathode",
            source="smm",
            hours_since_update=10.0,
            threshold_hours=24.0,
            is_stale=False,
            severity="ok",
        )
        assert result.severity == "ok"
        assert result.is_stale is False

    def test_create_warning_result(self):
        result = FreshnessResult(
            material_key="cu_cathode",
            source="smm",
            hours_since_update=30.0,
            threshold_hours=24.0,
            is_stale=True,
            severity="warning",
        )
        assert result.severity == "warning"
        assert result.is_stale is True


class TestFreshnessAlertModel:
    """FreshnessAlert 模型测试。"""

    def test_create_warning_alert(self):
        alert = FreshnessAlert(
            material_key="al_ingot",
            source="mysteel",
            hours_since_update=30.0,
            threshold_hours=24.0,
            severity="warning",
        )
        assert alert.severity == "warning"

    def test_create_critical_alert(self):
        alert = FreshnessAlert(
            material_key="cu_cathode",
            source="smm",
            hours_since_update=60.0,
            threshold_hours=24.0,
            severity="critical",
        )
        assert alert.severity == "critical"
        assert alert.hours_since_update == 60.0


class TestSourceHealthModel:
    """SourceHealth 模型测试。"""

    def test_healthy_source(self):
        health = SourceHealth(
            source="smm",
            total_materials=10,
            fresh_count=10,
            stale_count=0,
            avg_freshness_hours=8.5,
            degraded=False,
        )
        assert health.degraded is False
        assert health.fresh_count == 10

    def test_degraded_source(self):
        health = SourceHealth(
            source="lme",
            total_materials=5,
            fresh_count=0,
            stale_count=5,
            avg_freshness_hours=72.0,
            degraded=True,
        )
        assert health.degraded is True


class TestMaterialPriceRecordModel:
    """MaterialPriceRecord 模型测试。"""

    def test_create_record(self):
        record = MaterialPriceRecord(
            material_key="cu_cathode",
            price=78200.0,
            unit="元/吨",
            source="smm",
            updated_at=datetime.now(timezone.utc),
            freshness_hours=5.0,
            is_stale=False,
        )
        assert record.price == 78200.0
        assert record.is_stale is False


class TestFreshnessMonitor:
    """FreshnessMonitor 服务层测试。"""

    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        return db

    @pytest.fixture
    def monitor(self, mock_db):
        return FreshnessMonitor(mock_db)

    def _make_price_record(self, material_key, source, hours_ago):
        """创建模拟价格记录。"""
        record = MagicMock(spec=MaterialPrice)
        record.material_key = material_key
        record.source_name = source
        record.price_value = 78200.0
        record.price_unit = "元/吨"
        record.fetch_timestamp = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        return record

    def test_check_freshness_fresh_data(self, monitor, mock_db):
        """检查新鲜数据（未过期）。"""
        record = self._make_price_record("cu_cathode", "smm", 10)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = record
        mock_db.execute.return_value = result_mock

        result = monitor.check_freshness("cu_cathode")
        assert result.severity == "ok"
        assert result.is_stale is False
        assert result.source == "smm"

    def test_check_freshness_warning_data(self, monitor, mock_db):
        """检查即将过期数据（warning级别）。"""
        record = self._make_price_record("cu_cathode", "smm", 30)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = record
        mock_db.execute.return_value = result_mock

        result = monitor.check_freshness("cu_cathode")
        assert result.severity == "warning"
        assert result.is_stale is True

    def test_check_freshness_critical_data(self, monitor, mock_db):
        """检查严重过期数据（critical级别，超过2倍阈值）。"""
        record = self._make_price_record("cu_cathode", "smm", 50)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = record
        mock_db.execute.return_value = result_mock

        result = monitor.check_freshness("cu_cathode")
        assert result.severity == "critical"
        assert result.is_stale is True

    def test_check_freshness_no_data(self, monitor, mock_db):
        """检查无数据情况。"""
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = result_mock

        result = monitor.check_freshness("nonexistent_key")
        assert result.severity == "critical"
        assert result.is_stale is True
        assert result.source == "none"

    def test_check_freshness_lme_48h_threshold(self, monitor, mock_db):
        """LME 数据源应使用 48h 阈值。"""
        record = self._make_price_record("cu_cathode", "lme", 30)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = record
        mock_db.execute.return_value = result_mock

        result = monitor.check_freshness("cu_cathode")
        assert result.threshold_hours == 48.0
        assert result.is_stale is False  # 30h < 48h

    def test_get_all_freshness_empty(self, monitor, mock_db):
        """无数据时返回空列表。"""
        result_mock = MagicMock()
        result_mock.all.return_value = []
        mock_db.execute.return_value = result_mock

        results = monitor.get_all_freshness()
        assert results == []

    def test_get_all_freshness_multiple(self, monitor, mock_db):
        """多个材料的新鲜度检查。"""
        now = datetime.now(timezone.utc)
        rows = [
            ("cu_cathode", "smm", now - timedelta(hours=10)),
            ("al_ingot", "mysteel", now - timedelta(hours=30)),
        ]
        result_mock = MagicMock()
        result_mock.all.return_value = rows
        mock_db.execute.return_value = result_mock

        results = monitor.get_all_freshness()
        assert len(results) == 2
        assert results[0].material_key == "cu_cathode"
        assert results[0].severity == "ok"
        assert results[1].material_key == "al_ingot"
        assert results[1].severity == "warning"

    def test_get_stale_alerts_no_stale(self, monitor, mock_db):
        """全部新鲜时无预警。"""
        now = datetime.now(timezone.utc)
        rows = [
            ("cu_cathode", "smm", now - timedelta(hours=5)),
            ("al_ingot", "mysteel", now - timedelta(hours=10)),
        ]
        result_mock = MagicMock()
        result_mock.all.return_value = rows
        mock_db.execute.return_value = result_mock

        alerts = monitor.get_stale_alerts()
        assert alerts == []

    def test_get_stale_alerts_with_stale(self, monitor, mock_db):
        """存在过期数据时生成预警。"""
        now = datetime.now(timezone.utc)
        rows = [
            ("cu_cathode", "smm", now - timedelta(hours=30)),   # warning: 30h > 24h, 30h < 48h(2*24)
            ("al_ingot", "mysteel", now - timedelta(hours=50)),  # critical: 50h > 48h(2*24)
        ]
        result_mock = MagicMock()
        result_mock.all.return_value = rows
        mock_db.execute.return_value = result_mock

        alerts = monitor.get_stale_alerts()
        assert len(alerts) == 2
        # cu_cathode: 30h > 24h but 30h < 48h (2*24), so warning
        cu_alert = [a for a in alerts if a.material_key == "cu_cathode"][0]
        assert cu_alert.severity == "warning"
        # al_ingot: mysteel threshold=24h, 50h > 48h (2*24), so critical
        al_alert = [a for a in alerts if a.material_key == "al_ingot"][0]
        assert al_alert.severity == "critical"

    def test_get_stale_alerts_critical(self, monitor, mock_db):
        """严重过期数据生成 critical 预警。"""
        now = datetime.now(timezone.utc)
        rows = [
            ("cu_cathode", "smm", now - timedelta(hours=50)),  # critical: 50h > 2*24h
        ]
        result_mock = MagicMock()
        result_mock.all.return_value = rows
        mock_db.execute.return_value = result_mock

        alerts = monitor.get_stale_alerts()
        assert len(alerts) == 1
        assert alerts[0].severity == "critical"

    def test_update_price_success(self, monitor, mock_db):
        """手动更新价格成功。"""
        result = monitor.update_price("cu_cathode", 78200.0, "smm")
        assert result is True
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    def test_update_price_failure(self, monitor, mock_db):
        """手动更新价格失败（数据库异常）。"""
        mock_db.add.side_effect = Exception("DB error")
        result = monitor.update_price("cu_cathode", 78200.0, "smm")
        assert result is False

    def test_get_source_health_summary_empty(self, monitor, mock_db):
        """无数据时健康汇总为空。"""
        result_mock = MagicMock()
        result_mock.all.return_value = []
        mock_db.execute.return_value = result_mock

        health = monitor.get_source_health_summary()
        assert health == {}

    def test_get_source_health_summary_healthy(self, monitor, mock_db):
        """全部健康的数据源汇总。"""
        now = datetime.now(timezone.utc)
        rows = [
            ("cu_cathode", "smm", now - timedelta(hours=5)),
            ("al_ingot", "smm", now - timedelta(hours=8)),
        ]
        result_mock = MagicMock()
        result_mock.all.return_value = rows
        mock_db.execute.return_value = result_mock

        health = monitor.get_source_health_summary()
        assert "smm" in health
        assert health["smm"].total_materials == 2
        assert health["smm"].fresh_count == 2
        assert health["smm"].stale_count == 0
        assert health["smm"].degraded is False

    def test_get_source_health_summary_degraded(self, monitor, mock_db):
        """全部过期时标记为降级。"""
        now = datetime.now(timezone.utc)
        rows = [
            ("cu_cathode", "lme", now - timedelta(hours=100)),
            ("al_ingot", "lme", now - timedelta(hours=120)),
        ]
        result_mock = MagicMock()
        result_mock.all.return_value = rows
        mock_db.execute.return_value = result_mock

        health = monitor.get_source_health_summary()
        assert "lme" in health
        assert health["lme"].degraded is True
        assert health["lme"].stale_count == 2

    def test_get_source_health_summary_mixed(self, monitor, mock_db):
        """混合状态的数据源汇总。"""
        now = datetime.now(timezone.utc)
        rows = [
            ("cu_cathode", "smm", now - timedelta(hours=5)),    # fresh
            ("al_ingot", "smm", now - timedelta(hours=30)),      # stale
            ("ni_cathode", "mysteel", now - timedelta(hours=10)),  # fresh
        ]
        result_mock = MagicMock()
        result_mock.all.return_value = rows
        mock_db.execute.return_value = result_mock

        health = monitor.get_source_health_summary()
        assert "smm" in health
        assert health["smm"].total_materials == 2
        assert health["smm"].fresh_count == 1
        assert health["smm"].stale_count == 1
        assert health["smm"].degraded is False  # 部分正常不算降级

        assert "mysteel" in health
        assert health["mysteel"].total_materials == 1
        assert health["mysteel"].degraded is False

    def test_check_freshness_naive_timestamp(self, monitor, mock_db):
        """处理无时区信息的时间戳。"""
        record = self._make_price_record("cu_cathode", "smm", 10)
        # 移除时区信息
        record.fetch_timestamp = datetime.now() - timedelta(hours=10)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = record
        mock_db.execute.return_value = result_mock

        result = monitor.check_freshness("cu_cathode")
        assert result.severity == "ok"
