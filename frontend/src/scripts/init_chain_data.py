"""产业链知识图谱数据初始化脚本。

T2-005: 将 industry_chain.py 中定义的节点、边、品类映射数据
写入 SQLite 数据库。

使用方式:
    cd backend/
    python -m scripts.init_chain_data
    # 或
    python scripts/init_chain_data.py
"""

from __future__ import annotations

import json
import logging
import sys
import os

# 确保 backend 目录在 Python path 中
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
_backend_dir = os.path.join(_project_root, "backend")
for _p in (_backend_dir, _project_root):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.database import engine, SessionLocal, Base
from app.models.chain_node import IndustryNode
from app.models.chain_edge import IndustryEdge, CategoryMaterialMapping
from app.knowledge.industry_chain import (
    ALL_NODES,
    ALL_EDGES,
    CATEGORY_MATERIAL_MAPPINGS,
    validate_coverage,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def create_tables():
    """创建三张图谱表（如不存在）。"""
    IndustryNode.__table__.create(bind=engine, checkfirst=True)
    IndustryEdge.__table__.create(bind=engine, checkfirst=True)
    CategoryMaterialMapping.__table__.create(bind=engine, checkfirst=True)
    logger.info("图谱表已就绪 (industry_node, industry_edge, category_material_mapping)")


def clear_existing_data(db):
    """清空旧数据（可选，用于重新初始化）。"""
    db.query(IndustryEdge).delete()
    db.query(CategoryMaterialMapping).delete()
    db.query(IndustryNode).delete()
    db.commit()
    logger.info("已清空旧图谱数据")


def load_nodes(db) -> dict:
    """加载所有节点到数据库，返回 node_id(str) → db_id(int) 映射。"""
    id_map: dict = {}
    for node_def in ALL_NODES:
        db_node = IndustryNode(
            node_type=node_def.node_type,
            name=node_def.name,
            category=node_def.category or None,
            geo_location=node_def.geo_location or None,
            node_metadata=node_def.metadata or None,
        )
        db.add(db_node)
        db.flush()  # 获取自增 ID
        id_map[node_def.node_id] = db_node.id
    db.commit()
    logger.info("已加载 %d 个节点", len(id_map))
    return id_map


def load_edges(db, id_map: dict) -> int:
    """加载所有边到数据库。"""
    count = 0
    missing = []
    for edge_def in ALL_EDGES:
        from_id = id_map.get(edge_def.from_id)
        to_id = id_map.get(edge_def.to_id)
        if from_id is None or to_id is None:
            missing.append((edge_def.from_id, edge_def.to_id))
            continue
        db_edge = IndustryEdge(
            from_node_id=from_id,
            to_node_id=to_id,
            edge_type=edge_def.edge_type,
            transfer_rate=edge_def.transfer_rate,
            lag_months=edge_def.lag_months,
            confidence=edge_def.confidence,
            description=edge_def.description or None,
        )
        db.add(db_edge)
        count += 1
    db.commit()
    if missing:
        logger.warning("有 %d 条边因节点缺失被跳过: %s", len(missing), missing[:5])
    logger.info("已加载 %d 条边", count)
    return count


def load_category_mappings(db) -> int:
    """加载品类-材料映射。"""
    count = 0
    for mapping_def in CATEGORY_MATERIAL_MAPPINGS:
        db_mapping = CategoryMaterialMapping(
            component_category=mapping_def.component_category,
            material_name=mapping_def.material_name,
            cost_weight=mapping_def.cost_weight,
            data_source=mapping_def.data_source or None,
        )
        db.add(db_mapping)
        count += 1
    db.commit()
    logger.info("已加载 %d 条品类-材料映射", count)
    return count


def run_validation():
    """运行覆盖率验证。"""
    result = validate_coverage()
    logger.info("品类覆盖率验证: %s", json.dumps(result, ensure_ascii=False, indent=2))
    if not result["all_covered"]:
        logger.error("❌ 有品类未覆盖: %s", result["missing"])
        return False
    logger.info("✅ 所有 %d 个品类均已覆盖", result["total_categories"])
    return True


def init_chain_data(clear: bool = False):
    """主初始化流程。

    Args:
        clear: 是否先清空旧数据。
    """
    logger.info("=" * 60)
    logger.info("开始初始化产业链知识图谱数据 (T2-005)")
    logger.info("=" * 60)

    # 1. 建表
    create_tables()

    db = SessionLocal()
    try:
        # 2. 可选清空
        if clear:
            clear_existing_data(db)

        # 3. 检查是否已有数据
        existing_count = db.query(IndustryNode).count()
        if existing_count > 0 and not clear:
            logger.info("图谱已有 %d 个节点，跳过初始化（传 clear=True 可强制重建）", existing_count)
            return

        # 4. 加载数据
        id_map = load_nodes(db)
        load_edges(db, id_map)
        load_category_mappings(db)

        # 5. 验证
        run_validation()

    finally:
        db.close()

    # 6. T2-015: 品类-材料映射表（内存驻留，不依赖DB）
    init_t2_015_mappings()

    logger.info("=" * 60)
    logger.info("产业链知识图谱初始化完成 ✅")
    logger.info("=" * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="初始化产业链知识图谱数据")
    parser.add_argument("--clear", action="store_true", help="清空旧数据后重新初始化")
    args = parser.parse_args()

    init_chain_data(clear=args.clear)


# ────────────────────────────────────────────────────────────
# T2-015: 品类-材料映射表初始化
# ────────────────────────────────────────────────────────────

def init_t2_015_mappings():
    """初始化 T2-015 品类-材料映射数据。

    验证并加载 category_material_mapping.py 中的映射数据。
    该数据驻留在内存中（通过 CategoryMaterialMappingService 提供查询），
    本函数负责验证数据完整性。
    """
    from app.knowledge.category_material_mapping import (
        CategoryMaterialMappingService,
        CATEGORY_MAPPING_DATA,
    )

    logger.info("-" * 60)
    logger.info("开始初始化 T2-015 品类-材料映射数据")
    logger.info("-" * 60)

    service = CategoryMaterialMappingService()

    # 1. 数据完整性验证
    validation = service.validate_data_integrity()
    if not validation["valid"]:
        logger.error("T2-015 数据验证失败:")
        for issue in validation["issues"]:
            logger.error("  - %s", issue)
        return False

    # 2. 统计信息
    stats = service.get_mapping_stats()
    logger.info("T2-015 映射统计:")
    logger.info("  品类数量: %d", stats["total_categories"])
    logger.info("  映射条目: %d", stats["total_mappings"])
    logger.info("  涉及材料: %d", stats["unique_materials"])

    # 3. 逐品类验证
    for category in service.get_all_categories():
        mappings = service.get_materials_for_category(category)
        total_weight = sum(m.weight for m in mappings)
        logger.info(
            "  ✓ %-12s: %d 种上游材料, 权重合计=%.2f",
            category, len(mappings), total_weight,
        )

    # 4. 反向查询验证（验证铜的影响范围）
    cu_categories = service.get_categories_for_material("cu_cathode")
    logger.info("  铜(cu_cathode)影响 %d 个品类: %s", len(cu_categories), cu_categories)

    logger.info("T2-015 品类-材料映射初始化完成 ✅")
    return True
