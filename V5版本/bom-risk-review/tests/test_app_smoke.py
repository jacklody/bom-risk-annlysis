from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_streamlit_entrypoint_contains_project_title_and_navigation():
    app_path = PROJECT_ROOT / "app.py"
    assert app_path.exists(), "app.py 应存在于项目根目录"

    content = app_path.read_text(encoding="utf-8")
    assert "BOM选型评审及交付风险预警系统" in content
    assert "BOM导入" in content


def test_home_component_contains_dashboard_elements():
    ui_path = PROJECT_ROOT / "src" / "ui_components.py"
    content = ui_path.read_text(encoding="utf-8")
    assert "最近BOM导入" in content
    assert "最近评分概览" in content
    assert "最近5条操作日志" in content
