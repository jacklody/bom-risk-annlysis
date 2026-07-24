import pandas as pd


DEFAULT_RULES = {
    "lead_time_medium_days": 30,
    "lead_time_high_days": 60,
    "price_increase_rate": 0.2,
    "inventory_drop_rate": 0.3,
}

RESULT_COLUMNS = ["物料编码", "物料名称", "风险等级", "推荐结论", "风险原因", "建议动作"]


def _is_yes(value) -> bool:
    return str(value).strip() == "是"


def _price_increase_rate(current_price, historical_price) -> float | None:
    if historical_price is None or float(historical_price) == 0:
        return None
    return (float(current_price) - float(historical_price)) / float(historical_price)


def _build_result(material_code, material_name, high_reasons, medium_reasons):
    if high_reasons:
        return {
            "物料编码": material_code,
            "物料名称": material_name,
            "风险等级": "高",
            "推荐结论": "不推荐使用",
            "风险原因": "；".join(high_reasons + medium_reasons),
            "建议动作": "建议确认供应保障，优先寻找替代料或调整选型。",
        }

    if medium_reasons:
        return {
            "物料编码": material_code,
            "物料名称": material_name,
            "风险等级": "中",
            "推荐结论": "谨慎使用",
            "风险原因": "；".join(medium_reasons),
            "建议动作": "建议采购或供应链确认交期、价格、库存和替代料状态。",
        }

    return {
        "物料编码": material_code,
        "物料名称": material_name,
        "风险等级": "低",
        "推荐结论": "推荐使用",
        "风险原因": "未命中风险规则",
        "建议动作": "可按当前选型继续推进。",
    }


def evaluate_risks(bom_df: pd.DataFrame, supply_df: pd.DataFrame, rules: dict | None = None) -> pd.DataFrame:
    active_rules = dict(DEFAULT_RULES)
    if rules:
        active_rules.update(rules)

    supply_by_code = {
        str(row["物料编码"]).strip(): row
        for _, row in supply_df.iterrows()
    }

    results = []
    for _, bom_row in bom_df.iterrows():
        material_code = str(bom_row["物料编码"]).strip()
        material_name = str(bom_row["物料名称"]).strip()
        supply_row = supply_by_code.get(material_code)

        if supply_row is None:
            results.append(
                _build_result(
                    material_code,
                    material_name,
                    ["未找到供应风险数据"],
                    [],
                )
            )
            continue

        high_reasons = []
        medium_reasons = []

        supplier_count = int(supply_row["供应商数量"])
        lead_time_days = float(supply_row["标准交期"])
        inventory_drop_rate = float(supply_row["库存变化率"])
        current_price = float(supply_row["当前价格"])
        historical_price = float(supply_row["历史价格"])
        is_discontinued = _is_yes(supply_row["是否停产"])
        has_alternative = _is_yes(supply_row["是否有替代料"])

        if is_discontinued:
            high_reasons.append("物料已停产")

        if supplier_count == 1 and not has_alternative:
            high_reasons.append("单一来源且无替代料")

        if lead_time_days > float(active_rules["lead_time_high_days"]):
            high_reasons.append(f"交期超过{int(active_rules['lead_time_high_days'])}天")
        elif lead_time_days > float(active_rules["lead_time_medium_days"]):
            medium_reasons.append(f"交期超过{int(active_rules['lead_time_medium_days'])}天")

        increase_rate = _price_increase_rate(current_price, historical_price)
        if increase_rate is not None and increase_rate > float(active_rules["price_increase_rate"]):
            medium_reasons.append(f"价格涨幅超过{int(float(active_rules['price_increase_rate']) * 100)}%")
        elif increase_rate is None:
            medium_reasons.append("无法计算价格涨幅")

        if inventory_drop_rate > float(active_rules["inventory_drop_rate"]):
            medium_reasons.append(f"库存下降率超过{int(float(active_rules['inventory_drop_rate']) * 100)}%")

        if not has_alternative:
            medium_reasons.append("无替代料")

        results.append(_build_result(material_code, material_name, high_reasons, medium_reasons))

    return pd.DataFrame(results, columns=RESULT_COLUMNS)
