"""BOM文件解析与标准化（v2 — 集成型号前缀反查、多品牌降级、品类智能推断）"""

import io
import re
import csv
import pandas as pd
from app.knowledge.brand_category_map import normalize_brand, get_brand_categories
from app.knowledge.part_number_prefix import infer_brand_from_part_number


# ============================================================
# 文件解析
# ============================================================
def parse_bom_file(contents: bytes, filename: str) -> list[dict]:
    """解析BOM文件，返回原始行列表"""
    name_lower = filename.lower()
    if name_lower.endswith('.csv'):
        return _parse_csv(contents)
    if name_lower.endswith('.xls'):
        return _parse_excel(contents, engine="xlrd")
    return _parse_excel(contents)


def _parse_csv(contents: bytes) -> list[dict]:
    """解析CSV格式（兼容utf-8/gbk）"""
    for enc in ("utf-8-sig", "gbk", "utf-8"):
        try:
            text = contents.decode(enc)
            reader = csv.DictReader(io.StringIO(text))
            return [_map_row(row) for row in reader]
        except UnicodeDecodeError:
            continue
    return []


def _parse_excel(contents: bytes, engine: str = None) -> list[dict]:
    """解析Excel格式（自动探测表头位置）"""
    bio = io.BytesIO(contents)
    # 自动找表头：在前5行内找含"型号"/"Part Number"/"物件编号"/"物料编码"的行
    df_probe = pd.read_excel(bio, dtype=str, header=None, nrows=5, engine=engine)
    header_row = 0
    for i in range(min(5, len(df_probe))):
        row_cells = [str(c) for c in df_probe.iloc[i].tolist() if pd.notna(c)]
        if any(_is_header_cell(c) for c in row_cells):
            header_row = i
            break

    bio.seek(0)
    df = pd.read_excel(bio, dtype=str, header=header_row, engine=engine)
    items = []
    for _, row in df.iterrows():
        items.append(_map_row(row))
    return items


def _is_header_cell(cell: str) -> bool:
    """判断单元格是否像表头"""
    if not cell:
        return False
    s = str(cell).strip()
    return s in ('型号', '物件编号', '物料编码', '*物料编码', 'Part Number',
                  'PartNumber', 'part_number', 'MPN', '料号', 'PN')


# ============================================================
# 字段映射
# ============================================================
def _map_row(row) -> dict:
    """字段映射：多列名兼容（中英文、多种写法）"""
    return {
        "part_number": _get_field(row, '型号', 'Part Number', 'PartNumber', 'part_number',
                                    'MPN', '料号', 'PN', '物件编号', '物料编码', '*物料编码'),
        "brand": _get_field(row, '品牌', 'Brand', 'brand', '厂商', '制造商', '制造商名称',
                             '厂家', '供应商名称', '供应商'),
        "category": _get_field(row, '品类', 'Category', 'category', '类别', '类型', '物料类型',
                                '名称', '物料名称'),
        "spec": _get_field(row, '规格', 'Spec', 'spec', '规格型号', '封装', 'Footprint'),
        "description": _get_field(row, '描述', 'Description', 'description', '物料描述',
                                    '规格描述', '物料短描述', '长描述', 'Name'),
        "qty": _get_field(row, '用量', 'Qty', 'qty', '数量', 'Quantity', '*数量', '单机用量'),
    }


def _get_field(row, *names):
    """从row中按优先级获取字段值"""
    for name in names:
        try:
            val = row.get(name) if hasattr(row, 'get') else row[name]
        except (KeyError, IndexError):
            continue
        if val and str(val).strip() and str(val).strip().lower() not in ('nan', 'none', 'null', ''):
            return str(val).strip()
    return ""


# ============================================================
# 品牌智能标准化
# ============================================================
def split_brands(brand_raw: str) -> list[str]:
    """
    分割多品牌字段，返回品牌列表
    处理多种格式：
    - "YAGEO(国巨,PHYCOMP)" → ["YAGEO"]  括号内是别名，忽略
    - "村田、TDK、国巨" → ["村田", "TDK", "国巨"]
    - "村田/Murata" → ["村田", "Murata"]
    """
    if not brand_raw or str(brand_raw).strip().lower() in ("nan", "tbd", "none", ""):
        return []
    s = str(brand_raw).strip()
    # 1. 剥离括号内别名
    s = re.sub(r'[\(（][^\)）]*[\)）]', '', s).strip()
    # 2. 去引号
    s = re.sub(r'["""]', '', s)
    # 3. 分割
    parts = re.split(r'[/,，、；;\s]+', s)
    return [p.strip() for p in parts if p and len(p.strip()) >= 2]


def smart_normalize_brand(brand_raw: str, part_number: str = "") -> tuple[str | None, bool]:
    """
    智能品牌标准化

    返回 (normalized_brand, is_single_brand)
    - is_single_brand=True：单一品牌锁定（型号前缀命中 或 字段只有1个品牌）→ 可走RED
    - is_single_brand=False：多品牌备选 → 应降级到YELLOW
    """
    # 1. 型号前缀优先（物理事实，最高可信度）
    if part_number:
        nb = infer_brand_from_part_number(part_number)
        if nb:
            return nb, True

    # 2. 品牌字段
    brands = split_brands(brand_raw)
    if len(brands) == 0:
        return None, True
    if len(brands) == 1:
        return normalize_brand(brands[0]), True

    # 3. 多品牌备选：返回第一个能标准化的，但标记为非锁定
    for b in brands:
        nb = normalize_brand(b)
        if nb:
            return nb, False
    return None, False


# ============================================================
# 品类智能推断
# ============================================================
_CATEGORY_CLUES = [
    (['钽电容', '钽电解', 'tantalum'], "Tantalum"),
    (['mlcc', '片式电容', '贴片电容', '陶瓷电容', '瓷片电容', '独石电容', '瓷介电容',
      '电容器', 'capacitor', 'cap '], "MLCC"),
    (['电解电容', '铝电解', 'electrolytic'], "Electrolytic"),
    (['安规电容', 'x2电容', 'y1电容', 'x电容', 'y电容', '薄膜电容', 'mkp'], "Film"),
    (['贴片电阻', '片式电阻', '厚膜电阻', '精密电阻', '薄膜电阻', 'resistor', '电阻器'], "Resistor"),
    (['电感', 'inductor', '磁珠', 'bead', '共模', '扼流圈', '共模线圈'], "Inductor"),
    (['mcu', '微控制器', '单片机', 'cortex-m', 'arm cortex'], "MCU"),
    (['mosfet', 'mos管', 'mos ', 'mos-', '场效应管'], "MOSFET"),
    (['igbt', 'ipm'], "IGBT"),
    (['二极管', 'diode', 'tvs', 'esd保护', '桥堆', '整流'], "Diode"),
    (['连接器', 'connector', '端子', '插座', '排针', '排母', '接插件', 'header'], "Connector"),
    (['晶振', 'crystal', 'oscillator', '谐振器'], "Crystal"),
    (['保险丝', 'fuse', '熔断器', '熔断'], "Fuse"),
    (['继电器', 'relay'], "Relay"),
    (['变压器', 'transformer', '互感器'], "Transformer"),
    (['pcb', '印制板', '印刷板', '线路板'], "PCB"),
    (['运放', '比较器', 'op amp', '放大器'], "Analog"),
    (['dc-dc', 'dcdc', 'ldo', '电源管理', 'pwm', 'buck', 'boost', '电源芯片', '电源ic'], "Power"),
    (['光耦', '光电器件', 'optocoupler', '光电耦合'], "Optocoupler"),
]


def infer_category(text_pieces: list[str]) -> str | None:
    """根据多个文本片段推断品类（按优先级匹配关键词）"""
    text = " ".join(str(t).lower() for t in text_pieces if t)
    if not text:
        return None
    for keys, cat in _CATEGORY_CLUES:
        if any(k in text for k in keys):
            return cat
    return None


# ============================================================
# 主入口
# ============================================================
def normalize_item(item: dict) -> dict:
    """标准化BOM行：品牌 + 品类（v2智能版）"""
    raw_brand = item.get("brand", "")
    raw_category = item.get("category", "")
    raw_description = item.get("description", "")
    part_number = item.get("part_number", "")

    # 品牌智能标准化
    norm_brand, is_single_brand = smart_normalize_brand(raw_brand, part_number)

    # 品类智能推断（依次从 category > description > brand默认 推断）
    norm_category = infer_category([raw_category, raw_description])
    if not norm_category and norm_brand:
        brand_cats = get_brand_categories(norm_brand)
        if brand_cats:
            norm_category = brand_cats[0]
    if not norm_category and raw_category:
        norm_category = raw_category

    return {
        # 多品牌备选不锁定品牌（避免误判RED）
        "brand": norm_brand if is_single_brand else None,
        "category": norm_category,
        "is_multi_brand": not is_single_brand,
    }
