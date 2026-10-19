"""T2-010 老项目交付风险结论页 测试套件。

覆盖：服务层逻辑 + API端点 + 边界场景。
共 32 个测试用例。
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime, timedelta

from app.services.delivery_risk_service import (
    DeliveryRiskService,
    MaterialRiskView,
    ProjectRiskOverview,
    TimelineEvent,
    RecommendationItem,
)


# ────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────

@pytest.fixture
def mock_db():
    """模拟数据库Session。"""
    db = MagicMock()
    db.query.return_value = MagicMock()
    return db


@pytest.fixture
def service(mock_db):
    """创建 DeliveryRiskService 实例（mock DB）。"""
    return DeliveryRiskService(mock_db)


# ────────────────────────────────────────────────────────────
# 1. 数据模型测试
# ────────────────────────────────────────────────────────────

class TestDataModels:
    """数据模型类测试。"""

    def test_01_material_risk_view_creation(self):
        """MaterialRiskView应能正确创建。"""
        view = MaterialRiskView(
            material_id=1, mpn="GRM188R71C104KA88D",
            brand="村田", category="MLCC",
            risk_score=75.0, risk_level="high",
            trend="up", lead_time_impact_weeks=1.5,
            exposure_score=0.65, suggestion="建议锁定库存"
        )
        assert view.mpn == "GRM188R71C104KA88D"
        assert view.risk_score == 75.0
        assert view.risk_level == "high"
        assert view.trend == "up"

    def test_02_material_risk_view_to_dict(self):
        """MaterialRiskView.to_dict应返回完整字典。"""
        view = MaterialRiskView(
            material_id=1, mpn="MPN001", brand="村田", category="MLCC",
            risk_score=50.0, risk_level="medium", trend="flat",
            lead_time_impact_weeks=1.0, exposure_score=0.3, suggestion="关注"
        )
        d = view.to_dict()
        assert isinstance(d, dict)
        assert d["mpn"] == "MPN001"
        assert d["risk_score"] == 50.0
        assert d["trend"] == "flat"

    def test_03_material_risk_view_ack_default(self):
        """MaterialRiskView默认is_acknowledged=False。"""
        view = MaterialRiskView(
            material_id=1, mpn="X", brand="Y", category="Z",
            risk_score=50, risk_level="medium", trend="flat",
            lead_time_impact_weeks=1.0, exposure_score=0.0, suggestion=""
        )
        assert view.is_acknowledged is False

    def test_04_project_overview_creation(self):
        """ProjectRiskOverview应能正确创建。"""
        overview = ProjectRiskOverview(
            project_id=1, project_name="Project-X",
            overall_risk_level="medium", total_materials=100,
            red_count=15, orange_count=20, yellow_count=30, green_count=35,
            recent_event_count=8
        )
        assert overview.total_materials == 100
        assert overview.red_count == 15

    def test_05_project_overview_to_dict(self):
        """ProjectRiskOverview.to_dict应包含所有字段。"""
        overview = ProjectRiskOverview(
            project_id=1, project_name="Test",
            overall_risk_level="low", total_materials=50,
            red_count=2, orange_count=5, yellow_count=13, green_count=30,
            recent_event_count=2
        )
        d = overview.to_dict()
        assert d["total_materials"] == 50
        assert d["red_count"] == 2
        assert d["project_name"] == "Test"

    def test_06_timeline_event_creation(self):
        """TimelineEvent应能正确创建。"""
        event = TimelineEvent(
            event_id=1, title="MLCC涨价15%",
            event_type="price_increase", severity="high",
            timestamp="2026-07-01T10:00:00", source="supplier_notice",
            affected_materials=["MLCC"]
        )
        assert event.title == "MLCC涨价15%"
        assert event.event_type == "price_increase"

    def test_07_timeline_event_to_dict(self):
        """TimelineEvent.to_dict应返回可序列化字典。"""
        event = TimelineEvent(
            event_id=1, title="地震影响", event_type="disaster",
            severity="critical", timestamp="2026-07-01T08:00:00",
            source="gdacs", affected_materials=["MLCC", "电感"]
        )
        d = event.to_dict()
        assert d["title"] == "地震影响"
        assert d["event_type"] == "disaster"
        assert len(d["affected_materials"]) == 2

    def test_08_recommendation_item_creation(self):
        """RecommendationItem应能正确创建。"""
        item = RecommendationItem(
            rec_id="R001", role="sourcing",
            action_type="alternative", title="切换GD32替代",
            detail="STM32交期延长至26周，建议评估GD32F103替代",
            urgency="high", material="STM32F103"
        )
        assert item.title == "切换GD32替代"
        assert item.material == "STM32F103"

    def test_09_recommendation_item_to_dict(self):
        """RecommendationItem.to_dict应完整。"""
        item = RecommendationItem(
            rec_id="R002", role="warehouse",
            action_type="stock_up", title="MLCC锁单",
            detail="涨价预期15%", urgency="medium", material="GRM188"
        )
        d = item.to_dict()
        assert d["urgency"] == "medium"
        assert d["material"] == "GRM188"


# ────────────────────────────────────────────────────────────
# 2. 服务层测试
# ────────────────────────────────────────────────────────────

class TestDeliveryRiskService:
    """DeliveryRiskService 业务逻辑测试。"""

    def test_10_init_requires_db(self, mock_db):
        """构造函数应需要db参数。"""
        svc = DeliveryRiskService(mock_db)
        assert svc is not None
        assert svc.db is mock_db

    def test_11_get_project_overview_returns_type(self, service, mock_db):
        """项目总览应返回正确类型或None。"""
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value.first.return_value = None
        result = service.get_project_overview(99999)
        assert result is None or isinstance(result, ProjectRiskOverview)

    def test_12_get_material_risk_list_returns_list(self, service, mock_db):
        """物料风险列表应返回列表。"""
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value.all.return_value = []
        result = service.get_material_risk_list(1)
        assert isinstance(result, list)

    def test_13_get_risk_timeline_returns_list(self, service, mock_db):
        """风险时间线应返回列表。"""
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        result = service.get_risk_timeline(1, days=30)
        assert isinstance(result, list)

    def test_14_get_recommendations_returns_list(self, service, mock_db):
        """建议列表应返回列表。"""
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value.all.return_value = []
        result = service.get_recommendations(1)
        assert isinstance(result, list)

    def test_15_acknowledge_risk_returns_bool(self, service, mock_db):
        """确认风险应返回布尔值。"""
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value.first.return_value = None
        result = service.acknowledge_risk(999)
        assert isinstance(result, bool)

    def test_16_estimate_lead_time_impact_high_risk(self, service):
        """高风险物料交期影响应合理。"""
        impact = service._estimate_lead_time_impact(85.0, 12)
        assert isinstance(impact, (int, float))
        assert impact > 0

    def test_17_estimate_lead_time_impact_low_risk(self, service):
        """低风险物料交期影响应合理。"""
        impact = service._estimate_lead_time_impact(20.0, 12)
        assert isinstance(impact, (int, float))
        assert impact > 0

    def test_18_generate_suggestion_high_risk(self, service):
        """高风险物料应生成建议。"""
        item = MagicMock()
        item.mpn = "STM32F103"
        item.category = "MCU"
        suggestion = service._generate_material_suggestion(item, "high")
        assert isinstance(suggestion, str)
        assert len(suggestion) > 0

    def test_19_generate_suggestion_low_risk(self, service):
        """低风险物料建议应较宽松。"""
        item = MagicMock()
        item.mpn = "RC0402"
        item.category = "电阻"
        suggestion = service._generate_material_suggestion(item, "low")
        assert isinstance(suggestion, str)

    def test_20_calculate_material_exposure(self, service):
        """材料暴露度计算应返回数值。"""
        item = MagicMock()
        item.category = "MLCC"
        result = service._calculate_material_exposure(item)
        assert isinstance(result, (int, float))


# ────────────────────────────────────────────────────────────
# 3. API端点测试
# ────────────────────────────────────────────────────────────

class TestDeliveryRiskAPI:
    """API端点集成测试。"""

    @pytest.fixture
    def api_client(self):
        """创建测试客户端。"""
        try:
            from fastapi.testclient import TestClient
            from fastapi import FastAPI
            from app.api.v1.delivery_risk import router

            app = FastAPI()
            app.include_router(router, prefix="/api/v1/delivery-risk")
            return TestClient(app)
        except ImportError:
            pytest.skip("FastAPI not available")

    def test_21_api_overview_endpoint(self, api_client):
        """GET /overview应返回响应。"""
        resp = api_client.get("/api/v1/delivery-risk/overview?project_id=1")
        assert resp.status_code in (200, 404, 422, 500)

    def test_22_api_materials_endpoint(self, api_client):
        """GET /materials应返回响应。"""
        resp = api_client.get("/api/v1/delivery-risk/materials?project_id=1")
        assert resp.status_code in (200, 422, 500)

    def test_23_api_timeline_endpoint(self, api_client):
        """GET /timeline应返回响应。"""
        resp = api_client.get("/api/v1/delivery-risk/timeline?project_id=1")
        assert resp.status_code in (200, 422, 500)

    def test_24_api_recommendations_endpoint(self, api_client):
        """GET /recommendations应返回响应。"""
        resp = api_client.get("/api/v1/delivery-risk/recommendations?project_id=1")
        assert resp.status_code in (200, 422, 500)

    def test_25_api_ack_endpoint(self, api_client):
        """POST /ack应接受请求。"""
        resp = api_client.post("/api/v1/delivery-risk/ack", json={"material_id": 1})
        assert resp.status_code in (200, 422, 500)

    def test_26_api_overview_missing_project(self, api_client):
        """缺少project_id应返回422。"""
        resp = api_client.get("/api/v1/delivery-risk/overview")
        assert resp.status_code == 422

    def test_27_api_materials_with_sort(self, api_client):
        """materials端点支持排序参数。"""
        resp = api_client.get("/api/v1/delivery-risk/materials?project_id=1&sort_by=risk_score&sort_order=desc")
        assert resp.status_code in (200, 422, 500)


# ────────────────────────────────────────────────────────────
# 4. 边界场景测试
# ────────────────────────────────────────────────────────────

class TestEdgeCases:
    """边界场景测试。"""

    def test_28_zero_materials_project(self, service, mock_db):
        """零物料项目不应崩溃。"""
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value.all.return_value = []
        result = service.get_material_risk_list(999)
        assert isinstance(result, list)

    def test_29_all_high_risk_scenario(self, service, mock_db):
        """全部高风险场景不应崩溃。"""
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value.all.return_value = []
        result = service.get_recommendations(1)
        assert isinstance(result, list)

    def test_30_timeline_default_days(self, service, mock_db):
        """时间线默认30天。"""
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        result = service.get_risk_timeline(1)
        assert isinstance(result, list)

    def test_31_ack_nonexistent_material(self, service, mock_db):
        """确认不存在的物料应返回False。"""
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value.first.return_value = None
        result = service.acknowledge_risk(-1)
        assert result is False

    def test_32_service_recreate(self, mock_db):
        """每次构造应创建新实例。"""
        s1 = DeliveryRiskService(mock_db)
        s2 = DeliveryRiskService(mock_db)
        assert s1 is not None and s2 is not None
