"""T2-009 新项目选型评审 测试。

覆盖:
- 服务层: ProjectReviewService 核心逻辑
- API层: 4个端点的请求/响应
- 边界场景: 空数据、筛选、分页、审批不存在的物料
"""

import sys
import unittest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass

sys.path.insert(0, "/app/data/所有对话/主对话/BOM系统v4改造/backend")

from app.services.project_review_service import (
    ProjectReviewService,
    ReviewItem,
    ReviewSummary,
    get_project_review_service,
)

# ═══════════════════════════════════════════════════════════════════════════════
# 辅助数据
# ═══════════════════════════════════════════════════════════════════════════════

def _make_bom_items(n=5):
    """生成测试用BOM物料列表。"""
    categories = ["MCU", "MLCC", "MOSFET", "电阻", "连接器"]
    items = []
    for i in range(n):
        items.append({
            "bom_item_id": f"item-{i+1:03d}",
            "mpn": f"MPN-{i+1:03d}",
            "category": categories[i % len(categories)],
            "manufacturer": f"MFR-{i % 3 + 1}",
            "quantity": (i + 1) * 10,
            "project_count": i + 1,
        })
    return items


@dataclass
class MockRiskResult:
    total_score: float = 65.0
    risk_level: str = "orange"


@dataclass
class MockExposureResult:
    exposure_score: float = 45.0


@dataclass
class MockEscalationResult:
    final_level: str = "red"
    triggered_rules: list = None

    def __post_init__(self):
        if self.triggered_rules is None:
            self.triggered_rules = ["R1"]


@dataclass
class MockRecResult:
    success: bool = True
    degraded: bool = False
    data: dict = None

    def __post_init__(self):
        if self.data is None:
            self.data = {
                "procurement_recommendations": [{"detail": "建议锁价8周"}],
                "rd_recommendations": [{"detail": "验证GD32替代"}],
            }


def _make_service_with_mocks():
    """创建带mock引擎的service实例。"""
    risk_engine = MagicMock()
    risk_engine.evaluate.return_value = MockRiskResult()

    exposure_engine = MagicMock()
    exposure_engine.calculate.return_value = MockExposureResult()

    escalation_engine = MagicMock()
    escalation_engine.check.return_value = MockEscalationResult()

    rec_gen = MagicMock()
    rec_gen.generate.return_value = MockRecResult()

    service = ProjectReviewService(
        risk_engine=risk_engine,
        exposure_engine=exposure_engine,
        escalation_engine=escalation_engine,
        recommendation_generator=rec_gen,
    )
    return service, risk_engine, exposure_engine, escalation_engine, rec_gen


# ═══════════════════════════════════════════════════════════════════════════════
# 服务层测试
# ═══════════════════════════════════════════════════════════════════════════════

class TestProjectReviewService(unittest.TestCase):
    """服务层核心逻辑测试。"""

    def test_01_build_review_returns_summary(self):
        """build_review 返回正确的汇总信息。"""
        service, *_ = _make_service_with_mocks()
        bom_items = _make_bom_items(5)
        summary = service.build_review("proj-1", "测试项目", bom_items)

        self.assertIsInstance(summary, ReviewSummary)
        self.assertEqual(summary.project_id, "proj-1")
        self.assertEqual(summary.project_name, "测试项目")
        self.assertEqual(summary.total_items, 5)

    def test_02_risk_distribution_counted(self):
        """风险分布正确统计。"""
        service, *_ = _make_service_with_mocks()
        bom_items = _make_bom_items(5)
        summary = service.build_review("proj-1", "测试项目", bom_items)

        # 所有物料经mock引擎后均为 "red" (提级后)
        self.assertIn("red", summary.risk_distribution)
        self.assertEqual(summary.risk_distribution["red"], 5)

    def test_03_category_coverage_counted(self):
        """品类覆盖正确统计。"""
        service, *_ = _make_service_with_mocks()
        bom_items = _make_bom_items(5)
        summary = service.build_review("proj-1", "测试项目", bom_items)

        self.assertEqual(len(summary.category_coverage), 5)
        self.assertIn("MCU", summary.category_coverage)

    def test_04_get_bom_items_returns_all(self):
        """get_bom_items 无筛选时返回全部物料。"""
        service, *_ = _make_service_with_mocks()
        bom_items = _make_bom_items(5)
        service.build_review("proj-1", "测试项目", bom_items)

        items, total = service.get_bom_items("proj-1")
        self.assertEqual(total, 5)
        self.assertEqual(len(items), 5)

    def test_05_get_bom_items_with_risk_filter(self):
        """按风险等级筛选。"""
        service, *_ = _make_service_with_mocks()
        bom_items = _make_bom_items(5)
        service.build_review("proj-1", "测试项目", bom_items)

        items, total = service.get_bom_items("proj-1", risk_level="red")
        self.assertEqual(total, 5)

        items, total = service.get_bom_items("proj-1", risk_level="green")
        self.assertEqual(total, 0)

    def test_06_get_bom_items_with_category_filter(self):
        """按品类筛选。"""
        service, *_ = _make_service_with_mocks()
        bom_items = _make_bom_items(5)
        service.build_review("proj-1", "测试项目", bom_items)

        items, total = service.get_bom_items("proj-1", category="MCU")
        self.assertEqual(total, 1)
        self.assertEqual(items[0].category, "MCU")

    def test_07_get_bom_items_with_manufacturer_filter(self):
        """按供应商筛选。"""
        service, *_ = _make_service_with_mocks()
        bom_items = _make_bom_items(5)
        service.build_review("proj-1", "测试项目", bom_items)

        items, total = service.get_bom_items("proj-1", manufacturer="MFR-1")
        self.assertTrue(total >= 1)

    def test_08_pagination_works(self):
        """分页逻辑正确。"""
        service, *_ = _make_service_with_mocks()
        bom_items = _make_bom_items(10)
        service.build_review("proj-1", "测试项目", bom_items)

        items_p1, total = service.get_bom_items("proj-1", page=1, page_size=3)
        self.assertEqual(total, 10)
        self.assertEqual(len(items_p1), 3)

        items_p4, _ = service.get_bom_items("proj-1", page=4, page_size=3)
        self.assertEqual(len(items_p4), 1)  # 10 % 3 = 1 余

    def test_09_approve_item_success(self):
        """批准物料成功。"""
        service, *_ = _make_service_with_mocks()
        bom_items = _make_bom_items(3)
        service.build_review("proj-1", "测试项目", bom_items)

        result = service.approve_item("proj-1", "item-001", True)
        self.assertTrue(result)

        summary = service.get_summary("proj-1")
        self.assertEqual(summary.approved_count, 1)

    def test_10_reject_item_success(self):
        """驳回物料成功。"""
        service, *_ = _make_service_with_mocks()
        bom_items = _make_bom_items(3)
        service.build_review("proj-1", "测试项目", bom_items)

        result = service.approve_item("proj-1", "item-002", False)
        self.assertTrue(result)

        summary = service.get_summary("proj-1")
        self.assertEqual(summary.rejected_count, 1)

    def test_11_approve_nonexistent_item(self):
        """批准不存在的物料返回False。"""
        service, *_ = _make_service_with_mocks()
        bom_items = _make_bom_items(3)
        service.build_review("proj-1", "测试项目", bom_items)

        result = service.approve_item("proj-1", "nonexistent", True)
        self.assertFalse(result)

    def test_12_export_review_json(self):
        """导出评审报告JSON格式。"""
        service, *_ = _make_service_with_mocks()
        bom_items = _make_bom_items(3)
        service.build_review("proj-1", "测试项目", bom_items)

        data = service.export_review("proj-1", format="json")
        self.assertEqual(data["format"], "json")
        self.assertIn("summary", data)
        self.assertIn("items", data)
        self.assertEqual(len(data["items"]), 3)

    def test_13_get_summary_empty_project(self):
        """获取不存在项目的汇总返回默认值。"""
        service = ProjectReviewService()
        summary = service.get_summary("nonexistent")
        self.assertEqual(summary.total_items, 0)
        self.assertEqual(summary.project_name, "")

    def test_14_engines_called_correctly(self):
        """各引擎被正确调用。"""
        service, risk_engine, exposure_engine, escalation_engine, rec_gen = _make_service_with_mocks()
        bom_items = _make_bom_items(2)
        service.build_review("proj-1", "测试项目", bom_items)

        self.assertEqual(risk_engine.evaluate.call_count, 2)
        self.assertEqual(exposure_engine.calculate.call_count, 2)
        self.assertEqual(escalation_engine.check.call_count, 2)
        self.assertEqual(rec_gen.generate.call_count, 2)

    def test_15_engine_exception_handled(self):
        """引擎抛异常时不崩溃，使用默认值。"""
        risk_engine = MagicMock()
        risk_engine.evaluate.side_effect = RuntimeError("engine error")

        service = ProjectReviewService(risk_engine=risk_engine)
        bom_items = _make_bom_items(1)
        summary = service.build_review("proj-1", "测试项目", bom_items)

        self.assertEqual(summary.total_items, 1)

    def test_16_no_engines_provided(self):
        """无引擎时仍可构建评审（全默认值）。"""
        service = ProjectReviewService()
        bom_items = _make_bom_items(3)
        summary = service.build_review("proj-1", "测试项目", bom_items)

        self.assertEqual(summary.total_items, 3)
        items, _ = service.get_bom_items("proj-1")
        self.assertEqual(items[0].risk_level, "gray")
        self.assertEqual(items[0].risk_score, 0.0)

    def test_17_empty_bom_list(self):
        """空BOM列表时汇总正确。"""
        service = ProjectReviewService()
        summary = service.build_review("proj-1", "空项目", [])
        self.assertEqual(summary.total_items, 0)
        self.assertEqual(summary.pending_count, 0)

    def test_18_mixed_approval_status(self):
        """混合审批状态计数正确。"""
        service, *_ = _make_service_with_mocks()
        bom_items = _make_bom_items(5)
        service.build_review("proj-1", "测试项目", bom_items)

        service.approve_item("proj-1", "item-001", True)
        service.approve_item("proj-1", "item-002", True)
        service.approve_item("proj-1", "item-003", False)

        summary = service.get_summary("proj-1")
        self.assertEqual(summary.approved_count, 2)
        self.assertEqual(summary.rejected_count, 1)
        self.assertEqual(summary.pending_count, 2)


# ═══════════════════════════════════════════════════════════════════════════════
# API层测试
# ═══════════════════════════════════════════════════════════════════════════════

class TestProjectReviewAPI(unittest.TestCase):
    """API端点测试（使用FastAPI TestClient + mock service）。"""

    @classmethod
    def setUpClass(cls):
        """设置测试客户端。"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from api.v1.project_review import router

        app = FastAPI()
        app.include_router(router)
        cls.client = TestClient(app)

    def _setup_service_data(self):
        """预填充service数据。"""
        service, *_ = _make_service_with_mocks()
        bom_items = _make_bom_items(5)
        service.build_review("test-proj", "测试项目", bom_items)
        return service

    def test_19_api_get_summary(self):
        """GET /summary 返回正确结构。"""
        service = self._setup_service_data()

        with patch("api.v1.project_review._get_service", return_value=service):
            resp = self.client.get("/api/v1/project-review/summary?project_id=test-proj")

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["project_id"], "test-proj")
        self.assertEqual(data["total_items"], 5)
        self.assertIn("risk_distribution", data)

    def test_20_api_get_bom_items(self):
        """GET /bom-items 返回分页列表。"""
        service = self._setup_service_data()

        with patch("api.v1.project_review._get_service", return_value=service):
            resp = self.client.get("/api/v1/project-review/bom-items?project_id=test-proj&page=1&page_size=3")

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total"], 5)
        self.assertEqual(len(data["items"]), 3)
        self.assertEqual(data["page"], 1)

    def test_21_api_get_bom_items_with_filter(self):
        """GET /bom-items 带筛选条件。"""
        service = self._setup_service_data()

        with patch("api.v1.project_review._get_service", return_value=service):
            resp = self.client.get("/api/v1/project-review/bom-items?project_id=test-proj&risk_level=red")

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total"], 5)  # all are red after escalation

    def test_22_api_approve_item(self):
        """POST /approve 批准物料。"""
        service = self._setup_service_data()

        with patch("api.v1.project_review._get_service", return_value=service):
            resp = self.client.post("/api/v1/project-review/approve", json={
                "project_id": "test-proj",
                "bom_item_id": "item-001",
                "approved": True,
            })

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])

    def test_23_api_approve_nonexistent(self):
        """POST /approve 物料不存在返回404。"""
        service = self._setup_service_data()

        with patch("api.v1.project_review._get_service", return_value=service):
            resp = self.client.post("/api/v1/project-review/approve", json={
                "project_id": "test-proj",
                "bom_item_id": "nonexistent",
                "approved": True,
            })

        self.assertEqual(resp.status_code, 404)

    def test_24_api_export(self):
        """GET /export 返回导出数据。"""
        service = self._setup_service_data()

        with patch("api.v1.project_review._get_service", return_value=service):
            resp = self.client.get("/api/v1/project-review/export?project_id=test-proj&format=json")

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["format"], "json")
        self.assertEqual(len(data["items"]), 5)

    def test_25_api_summary_empty_project(self):
        """GET /summary 空项目返回默认值。"""
        service = ProjectReviewService()

        with patch("api.v1.project_review._get_service", return_value=service):
            resp = self.client.get("/api/v1/project-review/summary?project_id=empty-proj")

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_items"], 0)


# ═══════════════════════════════════════════════════════════════════════════════
# 单例与辅助测试
# ═══════════════════════════════════════════════════════════════════════════════

class TestProjectReviewUtils(unittest.TestCase):
    """辅助工具测试。"""

    def test_26_review_item_dataclass(self):
        """ReviewItem 数据类默认值正确。"""
        item = ReviewItem(bom_item_id="x", mpn="MPN", category="MCU")
        self.assertEqual(item.risk_level, "gray")
        self.assertEqual(item.risk_score, 0.0)
        self.assertIsNone(item.approved)

    def test_27_review_summary_dataclass(self):
        """ReviewSummary 数据类默认值正确。"""
        summary = ReviewSummary(project_id="p1", project_name="测试")
        self.assertEqual(summary.total_items, 0)
        self.assertEqual(summary.approved_count, 0)

    def test_28_get_project_review_service_singleton(self):
        """get_project_review_service 返回同一实例。"""
        # 重置全局
        import app.services.project_review_service as mod
        mod._review_service = None

        s1 = get_project_review_service()
        s2 = get_project_review_service()
        self.assertIs(s1, s2)

        # 清理
        mod._review_service = None


if __name__ == "__main__":
    unittest.main()
