import streamlit as st

from src.database import initialize_database
from src.ui_components import (
    render_bom_import_page,
    render_history_page,
    render_home_page,
    render_risk_scoring_page,
    render_rule_config_page,
    render_supply_import_page,
)


initialize_database()

st.set_page_config(
    page_title="BOM选型评审及交付风险预警系统",
    layout="wide",
)

page = st.sidebar.radio(
    "功能导航",
    ["首页", "BOM导入", "供应数据导入", "风险评分", "历史记录", "规则配置"],
)

if page == "BOM导入":
    render_bom_import_page()
elif page == "供应数据导入":
    render_supply_import_page()
elif page == "风险评分":
    render_risk_scoring_page()
elif page == "历史记录":
    render_history_page()
elif page == "规则配置":
    render_rule_config_page()
else:
    render_home_page()
