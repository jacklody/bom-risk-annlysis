"""共享 fixtures 和配置。"""
import pytest


@pytest.fixture(autouse=True)
def reset_material_tracker():
    """每个测试前重置模块级 MaterialTracker 引用。"""
    try:
        import app.services.upstream.risk_context_builder as rcb
        rcb._material_tracker = None
    except ImportError:
        pass


@pytest.fixture
def mock_settings(monkeypatch):
    """注入材料追踪相关配置。"""
    monkeypatch.setattr("app.config.settings.material_tracking_enabled", True)
    monkeypatch.setattr("app.config.settings.metals_api_key", "test_key_123")
    monkeypatch.setattr("app.config.settings.api_query_timeout", 30.0)
