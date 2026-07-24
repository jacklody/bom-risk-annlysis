from pathlib import Path

import pandas as pd

from src.audit_log import write_audit_log
from src.database import DEFAULT_DB_PATH, get_connection


BOM_REQUIRED_COLUMNS = ["BOM版本", "物料编码", "物料名称", "用量"]
BOM_OPTIONAL_COLUMNS = ["规格型号", "是否虚拟件", "替代料组", "是否共用料"]
BOM_COLUMNS = BOM_REQUIRED_COLUMNS[:3] + ["规格型号", "用量", "是否虚拟件", "替代料组", "是否共用料"]

SUPPLY_REQUIRED_COLUMNS = [
    "物料编码",
    "供应商数量",
    "标准交期",
    "当前库存",
    "库存变化率",
    "当前价格",
    "历史价格",
    "是否停产",
    "是否有替代料",
]
SUPPLY_OPTIONAL_COLUMNS = ["主供应商"]
SUPPLY_COLUMNS = [
    "物料编码",
    "供应商数量",
    "主供应商",
    "标准交期",
    "当前库存",
    "库存变化率",
    "当前价格",
    "历史价格",
    "是否停产",
    "是否有替代料",
]
SUPPLY_NUMERIC_COLUMNS = ["供应商数量", "标准交期", "当前库存", "库存变化率", "当前价格", "历史价格"]


class BomValidationError(ValueError):
    pass


class SupplyValidationError(ValueError):
    pass


def _normalize_text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def read_bom_excel(file_path_or_buffer, db_path: Path | str = DEFAULT_DB_PATH) -> pd.DataFrame:
    file_name = getattr(file_path_or_buffer, "name", "未知文件")
    try:
        df = pd.read_excel(file_path_or_buffer)
    except Exception as exc:
        write_audit_log(operation_type="导入BOM", operation_object=file_name, operation_result="失败", message=f"BOM文件读取失败：{exc}", db_path=db_path)
        raise BomValidationError(f"BOM文件读取失败：{exc}") from exc

    if df.empty:
        write_audit_log(operation_type="导入BOM", operation_object=file_name, operation_result="失败", message="文件中没有可导入的数据", db_path=db_path)
        raise BomValidationError("文件中没有可导入的数据")

    missing_columns = [column for column in BOM_REQUIRED_COLUMNS if column not in df.columns]
    if missing_columns:
        write_audit_log(operation_type="导入BOM", operation_object=file_name, operation_result="失败", message=f"缺少必填字段：{'、'.join(missing_columns)}", db_path=db_path)
        raise BomValidationError(f"缺少必填字段：{'、'.join(missing_columns)}")

    for column in BOM_OPTIONAL_COLUMNS:
        if column not in df.columns:
            df[column] = ""

    df = df[BOM_COLUMNS].copy()
    for column in ["BOM版本", "物料编码", "物料名称", "规格型号", "是否虚拟件", "替代料组", "是否共用料"]:
        df[column] = df[column].apply(_normalize_text)

    if df["物料编码"].eq("").any():
        raise BomValidationError("物料编码不能为空")

    duplicated_codes = df.loc[df["物料编码"].duplicated(), "物料编码"].tolist()
    if duplicated_codes:
        raise BomValidationError(f"物料编码不能重复：{'、'.join(duplicated_codes)}")

    numeric_quantity = pd.to_numeric(df["用量"], errors="coerce")
    if numeric_quantity.isna().any():
        raise BomValidationError("用量必须为数字")
    df["用量"] = numeric_quantity

    return df


def save_bom_import(
    df: pd.DataFrame,
    file_name: str,
    db_path: Path | str = DEFAULT_DB_PATH,
    operator: str | None = None,
) -> int:
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO import_batches (batch_type, file_name, row_count, status, message)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("BOM", file_name, len(df), "成功", "BOM导入成功"),
        )
        batch_id = cursor.lastrowid

        rows = [
            (
                batch_id,
                row["BOM版本"],
                row["物料编码"],
                row["物料名称"],
                row["规格型号"],
                float(row["用量"]),
                row["是否虚拟件"],
                row["替代料组"],
                row["是否共用料"],
            )
            for _, row in df.iterrows()
        ]
        conn.executemany(
            """
            INSERT INTO bom_items (
                batch_id,
                bom_version,
                material_code,
                material_name,
                specification,
                quantity,
                is_virtual,
                alternative_group,
                is_common
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()

    write_audit_log(
        operation_type="导入BOM",
        operation_object=file_name,
        operation_result="成功",
        operator=operator,
        message=f"成功导入{len(df)}条BOM明细",
        db_path=db_path,
    )
    return int(batch_id)


def read_supply_excel(file_path_or_buffer, db_path: Path | str = DEFAULT_DB_PATH) -> pd.DataFrame:
    file_name = getattr(file_path_or_buffer, "name", "未知文件")
    try:
        df = pd.read_excel(file_path_or_buffer)
    except Exception as exc:
        write_audit_log(operation_type="导入供应数据", operation_object=file_name, operation_result="失败", message=f"供应数据文件读取失败：{exc}", db_path=db_path)
        raise SupplyValidationError(f"供应数据文件读取失败：{exc}") from exc

    if df.empty:
        write_audit_log(operation_type="导入供应数据", operation_object=file_name, operation_result="失败", message="文件中没有可导入的数据", db_path=db_path)
        raise SupplyValidationError("文件中没有可导入的数据")

    missing_columns = [column for column in SUPPLY_REQUIRED_COLUMNS if column not in df.columns]
    if missing_columns:
        write_audit_log(operation_type="导入供应数据", operation_object=file_name, operation_result="失败", message=f"缺少必填字段：{'、'.join(missing_columns)}", db_path=db_path)
        raise SupplyValidationError(f"缺少必填字段：{'、'.join(missing_columns)}")

    for column in SUPPLY_OPTIONAL_COLUMNS:
        if column not in df.columns:
            df[column] = ""

    df = df[SUPPLY_COLUMNS].copy()
    for column in ["物料编码", "主供应商", "是否停产", "是否有替代料"]:
        df[column] = df[column].apply(_normalize_text)

    if df["物料编码"].eq("").any():
        raise SupplyValidationError("物料编码不能为空")

    for column in SUPPLY_NUMERIC_COLUMNS:
        numeric_values = pd.to_numeric(df[column], errors="coerce")
        if numeric_values.isna().any():
            raise SupplyValidationError(f"{column}必须为数字")
        df[column] = numeric_values

    return df


def save_supply_import(
    df: pd.DataFrame,
    file_name: str,
    db_path: Path | str = DEFAULT_DB_PATH,
    operator: str | None = None,
) -> int:
    rows = [
        (
            row["物料编码"],
            int(row["供应商数量"]),
            row["主供应商"],
            float(row["标准交期"]),
            float(row["当前库存"]),
            float(row["库存变化率"]),
            float(row["当前价格"]),
            float(row["历史价格"]),
            row["是否停产"],
            row["是否有替代料"],
        )
        for _, row in df.iterrows()
    ]

    with get_connection(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO supply_risk_data (
                material_code,
                supplier_count,
                primary_supplier,
                lead_time_days,
                current_inventory,
                inventory_drop_rate,
                current_price,
                historical_price,
                is_discontinued,
                has_alternative
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()

    write_audit_log(
        operation_type="导入供应数据",
        operation_object=file_name,
        operation_result="成功",
        operator=operator,
        message=f"成功导入{len(df)}条供应风险数据",
        db_path=db_path,
    )
    return len(df)
