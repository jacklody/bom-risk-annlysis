import streamlit as st

from src.dashboard_service import (
    get_latest_bom_batch,
    get_latest_scoring_summary,
    get_recent_audit_logs,
    get_scored_batches,
    get_scoring_results_for_batch,
)
from src.importers import (
    BomValidationError,
    SupplyValidationError,
    read_bom_excel,
    read_supply_excel,
    save_bom_import,
    save_supply_import,
)
from src.report_exporter import export_review_report
from src.rule_config import RULE_KEYS, get_rules, update_rule
from src.scoring_service import get_bom_batches, run_scoring_for_batch


def render_home_page() -> None:
    st.title("BOM选型评审及交付风险预警系统")
    st.caption("首页展示最近导入、最近评分和最近操作日志。")

    latest_batch = get_latest_bom_batch()
    if latest_batch:
        st.subheader("最近BOM导入")
        st.write(f"批次ID：{latest_batch['id']}，文件：{latest_batch['file_name']}，物料数：{latest_batch['row_count']}，导入时间：{latest_batch['created_at']}")
    else:
        st.info("暂无BOM导入记录。")

    latest_summary = get_latest_scoring_summary()
    if latest_summary:
        st.subheader("最近评分概览")
        col_total, col_high, col_medium, col_low = st.columns(4)
        col_total.metric("物料总数", latest_summary["物料总数"])
        col_high.metric("高风险数量", latest_summary["高风险数量"])
        col_medium.metric("中风险数量", latest_summary["中风险数量"])
        col_low.metric("低风险数量", latest_summary["低风险数量"])
    else:
        st.info("暂无评分结果。")

    st.subheader("最近5条操作日志")
    logs = get_recent_audit_logs(limit=5)
    if logs:
        st.dataframe(logs, use_container_width=True)
    else:
        st.info("暂无操作日志。")


def render_bom_import_page() -> None:
    st.title("BOM导入")
    st.caption("支持上传Excel，校验字段，并保存BOM明细。")

    uploaded_file = st.file_uploader("上传BOM Excel文件", type=["xlsx"], key="bom_upload")
    if uploaded_file is None:
        st.info("请上传包含BOM字段的 `.xlsx` 文件。")
        return

    try:
        df = read_bom_excel(uploaded_file)
    except BomValidationError as exc:
        st.error(str(exc))
        return

    st.success("字段校验通过")
    st.dataframe(df.head(20), use_container_width=True)

    operator = st.text_input("操作者", value="本地用户", key="bom_operator")
    if st.button("保存导入结果", type="primary"):
        batch_id = save_bom_import(df, file_name=uploaded_file.name, operator=operator)
        st.success(f"保存成功，导入批次ID：{batch_id}")


def render_supply_import_page() -> None:
    st.title("供应数据导入")
    st.caption("支持上传Excel，校验字段，并保存供应风险数据。")

    uploaded_file = st.file_uploader("上传供应风险Excel文件", type=["xlsx"], key="supply_upload")
    if uploaded_file is None:
        st.info("请上传包含供应风险字段的 `.xlsx` 文件。")
        return

    try:
        df = read_supply_excel(uploaded_file)
    except SupplyValidationError as exc:
        st.error(str(exc))
        return

    st.success("字段校验通过")
    st.dataframe(df.head(20), use_container_width=True)

    operator = st.text_input("操作者", value="本地用户", key="supply_operator")
    if st.button("保存供应数据", type="primary"):
        saved_count = save_supply_import(df, file_name=uploaded_file.name, operator=operator)
        st.success(f"保存成功，导入供应风险数据：{saved_count} 条")


def render_risk_scoring_page() -> None:
    st.title("风险评分")
    st.caption("选择一个BOM导入批次，执行物料级风险评分，并保存评分结果。")

    batches = get_bom_batches()
    if not batches:
        st.info("暂无BOM导入批次，请先完成BOM导入。")
        return

    batch_options = {
        f"{batch['id']} - {batch['file_name']} - {batch['created_at']}": batch["id"]
        for batch in batches
    }
    selected_label = st.selectbox("选择BOM导入批次", list(batch_options.keys()))
    batch_id = batch_options[selected_label]
    operator = st.text_input("操作者", value="本地用户", key="scoring_operator")

    if st.button("开始评分", type="primary"):
        results, summary = run_scoring_for_batch(batch_id, operator=operator)
        st.session_state["last_scoring_batch_id"] = batch_id
        st.session_state["last_scoring_operator"] = operator
        st.session_state["last_scoring_results"] = results
        st.session_state["last_scoring_summary"] = summary
        st.success("评分完成，结果已保存。")

    results = st.session_state.get("last_scoring_results")
    summary = st.session_state.get("last_scoring_summary")
    if results is None or summary is None:
        return

    col_total, col_high, col_medium, col_low = st.columns(4)
    col_total.metric("物料总数", summary["物料总数"])
    col_high.metric("高风险数量", summary["高风险数量"])
    col_medium.metric("中风险数量", summary["中风险数量"])
    col_low.metric("低风险数量", summary["低风险数量"])

    selected_levels = st.multiselect(
        "按风险等级筛选",
        ["高", "中", "低"],
        default=["高", "中", "低"],
    )
    filtered_results = results[results["风险等级"].isin(selected_levels)]
    st.dataframe(filtered_results, use_container_width=True)

    unmatched = results[results["风险原因"].str.contains("未找到供应风险数据|无法计算价格涨幅", na=False)]
    if not unmatched.empty:
        st.subheader("无法正常评分的物料")
        st.warning(f"共 {len(unmatched)} 条物料无法正常评分，请核实供应数据完整性。")
        st.dataframe(unmatched, use_container_width=True)

    if st.button("导出评审报告"):
        report_path = export_review_report(
            st.session_state["last_scoring_batch_id"],
            operator=st.session_state.get("last_scoring_operator"),
        )
        st.session_state["last_report_path"] = str(report_path)
        st.success(f"报告已生成：{report_path.name}")

    report_path = st.session_state.get("last_report_path")
    if report_path:
        with open(report_path, "rb") as report_file:
            st.download_button(
                "下载评审报告",
                data=report_file,
                file_name=report_path.split("\\")[-1],
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )


def render_history_page() -> None:
    st.title("历史记录")
    st.caption("查看已评分的BOM批次和对应评分明细。")

    batches = get_scored_batches()
    if not batches:
        st.info("暂无已评分批次。")
        return

    st.subheader("已评分批次")
    st.dataframe(batches, use_container_width=True)

    batch_options = {
        f"{batch['id']} - {batch['file_name']} - {batch['created_at']}": batch["id"]
        for batch in batches
    }
    selected_label = st.selectbox("选择历史批次", list(batch_options.keys()))
    batch_id = batch_options[selected_label]
    results = get_scoring_results_for_batch(batch_id)

    st.subheader("评分明细")
    selected_levels = st.multiselect(
        "按风险等级筛选",
        ["高", "中", "低"],
        default=["高", "中", "低"],
        key="history_risk_level_filter",
    )
    st.dataframe(results[results["风险等级"].isin(selected_levels)], use_container_width=True)


def render_rule_config_page() -> None:
    st.title("规则配置")
    st.caption("维护风险评分阈值，保存后重新评分将使用新规则。")

    rules = get_rules()
    operator = st.text_input("操作者", value="本地用户", key="rule_operator")
    changed = False

    for rule_key, rule_name, unit in RULE_KEYS:
        current_value = rules.get(rule_key, 0)
        if unit == "比例":
            display_value = float(current_value)
            new_value = st.number_input(
                f"{rule_name} ({unit})",
                min_value=0.0,
                max_value=1.0,
                value=display_value,
                step=0.05,
                format="%.2f",
                key=f"rule_{rule_key}",
            )
        else:
            display_value = int(float(current_value))
            new_value = st.number_input(
                f"{rule_name} ({unit})",
                min_value=0,
                value=display_value,
                step=1,
                key=f"rule_{rule_key}",
            )

        if new_value != current_value:
            changed = True

    if changed and st.button("保存规则修改", type="primary"):
        for rule_key, _, _ in RULE_KEYS:
            new_value = st.session_state[f"rule_{rule_key}"]
            if new_value != rules.get(rule_key, 0):
                update_rule(rule_key, new_value, operator=operator)
        st.success("规则已更新，刷新页面后可见。")
