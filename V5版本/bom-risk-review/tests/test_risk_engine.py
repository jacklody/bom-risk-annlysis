import pandas as pd

from src.risk_engine import DEFAULT_RULES, evaluate_risks


def make_bom_df():
    return pd.DataFrame(
        [
            {"BOM版本": "V1", "物料编码": "M001", "物料名称": "低风险物料", "规格型号": "A", "用量": 1, "是否虚拟件": "否", "替代料组": "ALT-A", "是否共用料": "是"},
            {"BOM版本": "V1", "物料编码": "M002", "物料名称": "停产物料", "规格型号": "B", "用量": 1, "是否虚拟件": "否", "替代料组": "", "是否共用料": "否"},
            {"BOM版本": "V1", "物料编码": "M003", "物料名称": "单一来源物料", "规格型号": "C", "用量": 1, "是否虚拟件": "否", "替代料组": "", "是否共用料": "否"},
            {"BOM版本": "V1", "物料编码": "M004", "物料名称": "交期中风险物料", "规格型号": "D", "用量": 1, "是否虚拟件": "否", "替代料组": "ALT-D", "是否共用料": "否"},
            {"BOM版本": "V1", "物料编码": "M005", "物料名称": "价格库存风险物料", "规格型号": "E", "用量": 1, "是否虚拟件": "否", "替代料组": "ALT-E", "是否共用料": "否"},
            {"BOM版本": "V1", "物料编码": "M006", "物料名称": "无供应数据物料", "规格型号": "F", "用量": 1, "是否虚拟件": "否", "替代料组": "", "是否共用料": "否"},
        ]
    )


def make_supply_df():
    return pd.DataFrame(
        [
            {"物料编码": "M001", "供应商数量": 2, "主供应商": "供应商A", "标准交期": 20, "当前库存": 100, "库存变化率": 0.05, "当前价格": 10, "历史价格": 10, "是否停产": "否", "是否有替代料": "是"},
            {"物料编码": "M002", "供应商数量": 2, "主供应商": "供应商B", "标准交期": 20, "当前库存": 100, "库存变化率": 0.05, "当前价格": 10, "历史价格": 10, "是否停产": "是", "是否有替代料": "是"},
            {"物料编码": "M003", "供应商数量": 1, "主供应商": "供应商C", "标准交期": 20, "当前库存": 100, "库存变化率": 0.05, "当前价格": 10, "历史价格": 10, "是否停产": "否", "是否有替代料": "否"},
            {"物料编码": "M004", "供应商数量": 2, "主供应商": "供应商D", "标准交期": 45, "当前库存": 100, "库存变化率": 0.05, "当前价格": 10, "历史价格": 10, "是否停产": "否", "是否有替代料": "是"},
            {"物料编码": "M005", "供应商数量": 2, "主供应商": "供应商E", "标准交期": 20, "当前库存": 100, "库存变化率": 0.35, "当前价格": 13, "历史价格": 10, "是否停产": "否", "是否有替代料": "是"},
        ]
    )


def get_result(results, material_code):
    row = results.loc[results["物料编码"] == material_code]
    assert len(row) == 1
    return row.iloc[0]


def test_evaluate_risks_returns_required_columns_and_one_result_per_bom_item():
    results = evaluate_risks(make_bom_df(), make_supply_df(), DEFAULT_RULES)

    assert list(results.columns) == ["物料编码", "物料名称", "风险等级", "推荐结论", "风险原因", "建议动作"]
    assert len(results) == len(make_bom_df())


def test_discontinued_material_is_high_risk_and_not_recommended():
    results = evaluate_risks(make_bom_df(), make_supply_df(), DEFAULT_RULES)
    row = get_result(results, "M002")

    assert row["风险等级"] == "高"
    assert row["推荐结论"] == "不推荐使用"
    assert "停产" in row["风险原因"]


def test_single_source_without_alternative_is_high_risk_with_explainable_reason():
    results = evaluate_risks(make_bom_df(), make_supply_df(), DEFAULT_RULES)
    row = get_result(results, "M003")

    assert row["风险等级"] == "高"
    assert row["推荐结论"] == "不推荐使用"
    assert "单一来源" in row["风险原因"]
    assert "无替代料" in row["风险原因"]


def test_45_day_lead_time_is_medium_risk_and_use_with_caution():
    results = evaluate_risks(make_bom_df(), make_supply_df(), DEFAULT_RULES)
    row = get_result(results, "M004")

    assert row["风险等级"] == "中"
    assert row["推荐结论"] == "谨慎使用"
    assert "交期超过30天" in row["风险原因"]


def test_price_increase_and_inventory_drop_are_medium_risks():
    results = evaluate_risks(make_bom_df(), make_supply_df(), DEFAULT_RULES)
    row = get_result(results, "M005")

    assert row["风险等级"] == "中"
    assert row["推荐结论"] == "谨慎使用"
    assert "价格涨幅超过20%" in row["风险原因"]
    assert "库存下降率超过30%" in row["风险原因"]


def test_material_without_risk_is_low_risk_and_recommended():
    results = evaluate_risks(make_bom_df(), make_supply_df(), DEFAULT_RULES)
    row = get_result(results, "M001")

    assert row["风险等级"] == "低"
    assert row["推荐结论"] == "推荐使用"
    assert row["风险原因"] == "未命中风险规则"


def test_material_without_supply_data_is_high_risk():
    results = evaluate_risks(make_bom_df(), make_supply_df(), DEFAULT_RULES)
    row = get_result(results, "M006")

    assert row["风险等级"] == "高"
    assert row["推荐结论"] == "不推荐使用"
    assert "未找到供应风险数据" in row["风险原因"]
