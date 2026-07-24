from pathlib import Path

import pandas as pd

from src.sample_data import BOM_COLUMNS, SUPPLY_COLUMNS, create_sample_files


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_create_sample_excel_files_with_required_columns(tmp_path):
    sample_dir = tmp_path / "samples"

    bom_path, supply_path = create_sample_files(sample_dir)

    assert bom_path.exists()
    assert supply_path.exists()

    bom_df = pd.read_excel(bom_path)
    supply_df = pd.read_excel(supply_path)

    assert list(bom_df.columns) == BOM_COLUMNS
    assert list(supply_df.columns) == SUPPLY_COLUMNS
    assert len(bom_df) >= 8
    assert len(supply_df) >= 8


def test_sample_data_contains_required_risk_scenarios(tmp_path):
    sample_dir = tmp_path / "samples"
    bom_path, supply_path = create_sample_files(sample_dir)

    bom_df = pd.read_excel(bom_path)
    supply_df = pd.read_excel(supply_path)

    matched_codes = set(bom_df["物料编码"]).intersection(set(supply_df["物料编码"]))
    assert len(matched_codes) >= 5
    assert (supply_df["是否停产"] == "是").any()
    assert ((supply_df["供应商数量"] == 1) & (supply_df["是否有替代料"] == "否")).any()
    assert (supply_df["标准交期"] > 60).any()
    assert (((supply_df["当前价格"] - supply_df["历史价格"]) / supply_df["历史价格"]) > 0.2).any()
    assert (supply_df["库存变化率"] > 0.3).any()
