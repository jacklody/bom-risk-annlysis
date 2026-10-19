"""产业链知识图谱查询服务。

T2-005: 产业链知识图谱数据模型
基于 SQLite 关系表 + Python 实现图遍历（不依赖 Neo4j）。

提供三个核心查询:
1. get_upstream_chain  - 从品类向上追溯完整材料链路
2. get_downstream_impact - 从材料事件向下传导到品类
3. get_bom_exposure     - 风险事件命中哪些 BOM 行
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.orm import Session

from app.models.chain_node import IndustryNode
from app.models.chain_edge import IndustryEdge, CategoryMaterialMapping

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────
# 数据类
# ────────────────────────────────────────────────────────────

@dataclass
class UpstreamNode:
    """上游链路节点。"""
    node_id: int
    node_name: str
    node_type: str
    depth: int               # 距离品类的层级数 (0=品类自身)
    transfer_rate: Optional[float] = None
    lag_months: Optional[float] = None
    confidence: float = 0.8
    edge_description: str = ""


@dataclass
class DownstreamImpact:
    """下游影响结果。"""
    category_node_id: int
    category_name: str
    transfer_rate: Optional[float] = None
    lag_months: Optional[float] = None
    confidence: float = 0.8
    chain_path: List[str] = field(default_factory=list)  # 传导路径


@dataclass
class BomExposure:
    """BOM 暴露度结果。"""
    bom_item_category: str
    bom_item_id: Optional[int] = None
    bom_item_name: str = ""
    matched_materials: List[str] = field(default_factory=list)
    total_cost_weight: float = 0.0
    risk_level: str = "gray"


# ────────────────────────────────────────────────────────────
# 主查询服务
# ────────────────────────────────────────────────────────────

class ChainQueryService:
    """产业链知识图谱查询服务。

    使用 SQLAlchemy Session 查询 SQLite 中的 industry_node / industry_edge
    / category_material_mapping 三张表，通过 BFS 实现图遍历。
    """

    def __init__(self, db: Session):
        self.db = db
        # 缓存: 避免重复查库
        self._node_cache: Dict[int, IndustryNode] = {}
        self._name_to_node: Dict[str, IndustryNode] = {}
        self._edges_from: Dict[int, List[IndustryEdge]] = defaultdict(list)
        self._edges_to: Dict[int, List[IndustryEdge]] = defaultdict(list)
        self._loaded = False

    def _ensure_loaded(self):
        """首次调用时全量加载节点和边到内存。"""
        if self._loaded:
            return
        # 加载节点
        for node in self.db.query(IndustryNode).all():
            self._node_cache[node.id] = node
            self._name_to_node[node.name] = node
        # 加载边
        for edge in self.db.query(IndustryEdge).all():
            self._edges_from[edge.from_node_id].append(edge)
            self._edges_to[edge.to_node_id].append(edge)
        self._loaded = True
        logger.info(
            "ChainQueryService 初始化: %d 节点, %d 边",
            len(self._node_cache),
            sum(len(v) for v in self._edges_from.values()),
        )

    def _get_node(self, node_id: int) -> Optional[IndustryNode]:
        self._ensure_loaded()
        return self._node_cache.get(node_id)

    def _find_node_by_name(self, name: str) -> Optional[IndustryNode]:
        """按名称模糊查找节点。"""
        self._ensure_loaded()
        # 精确匹配
        if name in self._name_to_node:
            return self._name_to_node[name]
        # 模糊匹配 (包含关系)
        for node_name, node in self._name_to_node.items():
            if name in node_name or node_name in name:
                return node
        return None

    def _find_nodes_by_type(self, node_type: str) -> List[IndustryNode]:
        self._ensure_loaded()
        return [n for n in self._node_cache.values() if n.node_type == node_type]

    # ────────────────────────────────────────────────────────
    # 1. 向上追溯: 品类 → 中间制品 → 基础材料
    # ────────────────────────────────────────────────────────

    def get_upstream_chain(
        self,
        component_category: str,
        max_depth: int = 5,
    ) -> List[UpstreamNode]:
        """查询某品类的完整上游材料链路（向上遍历）。

        Args:
            component_category: 品类名称 (如 "PCB/FPC", "MLCC") 或 node_id。
            max_depth: 最大追溯深度，默认 5 层。

        Returns:
            按深度排序的上游节点列表，包含转嫁率和滞后时间。
        """
        self._ensure_loaded()

        # 定位起始品类节点
        start_node = self._find_node_by_name(component_category)
        if start_node is None:
            logger.warning("未找到品类节点: %s", component_category)
            return []

        result: List[UpstreamNode] = []
        visited: Set[int] = {start_node.id}

        # BFS 向上遍历 (to → from, 即从下游找上游)
        queue: List[tuple] = [(start_node.id, 0)]

        while queue:
            current_id, depth = queue.pop(0)
            if depth >= max_depth:
                continue

            # 查找指向当前节点的所有边 (上游 → 当前)
            for edge in self._edges_to.get(current_id, []):
                if edge.from_node_id in visited:
                    continue
                upstream_node = self._get_node(edge.from_node_id)
                if upstream_node is None:
                    continue

                visited.add(edge.from_node_id)
                result.append(UpstreamNode(
                    node_id=upstream_node.id,
                    node_name=upstream_node.name,
                    node_type=upstream_node.node_type,
                    depth=depth + 1,
                    transfer_rate=edge.transfer_rate,
                    lag_months=edge.lag_months,
                    confidence=edge.confidence,
                    edge_description=edge.description or "",
                ))
                queue.append((edge.from_node_id, depth + 1))

        # 按深度排序
        result.sort(key=lambda x: (x.depth, x.node_name))
        return result

    # ────────────────────────────────────────────────────────
    # 2. 向下传导: 材料事件 → 中间制品 → 品类
    # ────────────────────────────────────────────────────────

    def get_downstream_impact(
        self,
        material_event: str,
        max_depth: int = 5,
    ) -> List[DownstreamImpact]:
        """查询某材料事件影响哪些器件品类（向下遍历）。

        Args:
            material_event: 材料名称 (如 "铜", "镍", "银") 或描述。
            max_depth: 最大传播深度。

        Returns:
            受影响的品类列表，按转嫁率/置信度排序。
        """
        self._ensure_loaded()

        # 定位起始材料节点
        start_node = self._find_node_by_name(material_event)
        if start_node is None:
            logger.debug("未找到材料节点: %s", material_event)
            return []

        result: List[DownstreamImpact] = []
        visited: Set[int] = {start_node.id}

        # BFS 向下遍历 (from → to, 即从上游找下游)
        queue: List[tuple] = [(start_node.id, 0, [start_node.name])]

        while queue:
            current_id, depth, path = queue.pop(0)
            if depth >= max_depth:
                continue

            current_node = self._get_node(current_id)

            # 查找从当前节点出发的所有边
            for edge in self._edges_from.get(current_id, []):
                if edge.to_node_id in visited:
                    continue
                downstream_node = self._get_node(edge.to_node_id)
                if downstream_node is None:
                    continue

                visited.add(edge.to_node_id)
                new_path = path + [downstream_node.name]

                # 如果下游是品类节点，记录结果
                if downstream_node.node_type == "component_category":
                    result.append(DownstreamImpact(
                        category_node_id=downstream_node.id,
                        category_name=downstream_node.name,
                        transfer_rate=edge.transfer_rate,
                        lag_months=edge.lag_months,
                        confidence=edge.confidence,
                        chain_path=new_path,
                    ))
                else:
                    # 继续向下传播
                    queue.append((edge.to_node_id, depth + 1, new_path))

        # 按置信度 × 转嫁率 排序
        result.sort(
            key=lambda x: (
                (x.confidence or 0) * (x.transfer_rate or 0.5),
                x.confidence or 0,
            ),
            reverse=True,
        )
        return result

    # ────────────────────────────────────────────────────────
    # 3. BOM 暴露度查询
    # ────────────────────────────────────────────────────────

    def get_bom_exposure(
        self,
        risk_event: str,
        bom_items: List[Dict[str, Any]],
    ) -> List[BomExposure]:
        """查询风险事件命中哪些 BOM 行。

        通过 category_material_mapping 表将风险事件中的材料
        与 BOM 品类的上游材料进行匹配，计算暴露度。

        Args:
            risk_event: 风险事件描述 (包含材料名称)。
            bom_items: BOM 行列表，每行需包含:
                - category: str  (BOM品类)
                - id: int (可选)
                - name: str (可选, 物料名称)

        Returns:
            命中风险暴露的 BOM 行列表，按 cost_weight 排序。
        """
        self._ensure_loaded()

        # 提取风险事件涉及的材料关键词
        risk_keywords = self._extract_material_keywords(risk_event)
        if not risk_keywords:
            return []

        # 查询品类-材料映射
        mappings = self.db.query(CategoryMaterialMapping).all()
        cat_materials: Dict[str, List[CategoryMaterialMapping]] = defaultdict(list)
        for m in mappings:
            cat_materials[m.component_category].append(m)

        result: List[BomExposure] = []

        for item in bom_items:
            category = item.get("category", "")
            if not category:
                continue

            # 查找该品类映射的材料
            matched: List[str] = []
            total_weight = 0.0

            # 在品类映射中查找匹配的材料
            for mapping in cat_materials.get(category, []):
                for keyword in risk_keywords:
                    if keyword in mapping.material_name or mapping.material_name in keyword:
                        matched.append(mapping.material_name)
                        total_weight += (mapping.cost_weight or 0.1)
                        break

            if matched:
                # 确定风险等级
                if total_weight >= 0.5:
                    risk_level = "red"
                elif total_weight >= 0.2:
                    risk_level = "orange"
                elif total_weight >= 0.1:
                    risk_level = "yellow"
                else:
                    risk_level = "gray"

                result.append(BomExposure(
                    bom_item_category=category,
                    bom_item_id=item.get("id"),
                    bom_item_name=item.get("name", ""),
                    matched_materials=matched,
                    total_cost_weight=round(total_weight, 4),
                    risk_level=risk_level,
                ))

        # 按 cost_weight 降序排序
        result.sort(key=lambda x: x.total_cost_weight, reverse=True)
        return result

    # ────────────────────────────────────────────────────────
    # 辅助方法
    # ────────────────────────────────────────────────────────

    def _extract_material_keywords(self, event_text: str) -> List[str]:
        """从风险事件文本中提取材料关键词。"""
        # 从所有材料节点名称中提取
        self._ensure_loaded()
        material_nodes = self._find_nodes_by_type("material")
        keywords: List[str] = []
        for node in material_nodes:
            if node.name in event_text:
                keywords.append(node.name)
        # 也检查 sub_assembly 名称
        sub_nodes = self._find_nodes_by_type("sub_assembly")
        for node in sub_nodes:
            if node.name in event_text:
                keywords.append(node.name)
        return keywords

    def get_all_categories(self) -> List[Dict[str, Any]]:
        """获取所有 BOM 品类节点。"""
        self._ensure_loaded()
        return [
            n.to_dict()
            for n in self._node_cache.values()
            if n.node_type == "component_category"
        ]

    def get_all_materials(self) -> List[Dict[str, Any]]:
        """获取所有基础材料节点。"""
        self._ensure_loaded()
        return [
            n.to_dict()
            for n in self._node_cache.values()
            if n.node_type == "material"
        ]

    def get_category_mappings(self, category: str) -> List[Dict[str, Any]]:
        """获取某品类的材料映射表。"""
        return [
            m.to_dict()
            for m in self.db.query(CategoryMaterialMapping)
            .filter(CategoryMaterialMapping.component_category == category)
            .all()
        ]

    def get_graph_stats(self) -> Dict[str, int]:
        """获取图谱统计信息。"""
        self._ensure_loaded()
        type_counts: Dict[str, int] = defaultdict(int)
        for node in self._node_cache.values():
            type_counts[node.node_type] += 1
        return {
            "total_nodes": len(self._node_cache),
            "total_edges": sum(len(v) for v in self._edges_from.values()),
            **{f"nodes_{k}": v for k, v in type_counts.items()},
        }

    # ────────────────────────────────────────────────────────
    # 4. T2-015: 上游原材料查询（品类-材料映射表）
    # ────────────────────────────────────────────────────────

    def get_upstream_materials(
        self,
        category: str,
    ) -> List[Dict[str, Any]]:
        """T2-015: 查询某品类的上游原材料映射。

        通过 CategoryMaterialMappingService 获取品类对应的原材料列表，
        包含权重、价格敏感度、前置时间等信息。

        Args:
            category: 品类名称 (如 "MLCC", "PCB/FPC", "电阻") 或别名。

        Returns:
            上游原材料列表，每项包含:
                - material_key: str  材料内部代码
                - material_name: str 材料中文名
                - weight: float  成本权重 (0-1)
                - price_sensitivity: float  价格敏感度 (0-1)
                - lead_time_days: int  前置时间(天)
                - source: str  数据源标识
            品类不存在时返回空列表。
        """
        from app.knowledge.category_material_mapping import (
            get_category_material_mapping_service,
        )

        service = get_category_material_mapping_service()
        mappings = service.get_materials_for_category(category)
        return [
            {
                "material_key": m.material_key,
                "material_name": m.material_name,
                "weight": m.weight,
                "price_sensitivity": m.price_sensitivity,
                "lead_time_days": m.lead_time_days,
                "source": m.source,
            }
            for m in mappings
        ]

    def get_downstream_categories_for_material(
        self,
        material_key: str,
    ) -> List[Dict[str, Any]]:
        """T2-015: 反向查询某原材料影响哪些品类。

        Args:
            material_key: 材料内部代码 (如 "cu_cathode", "nickel_powder")

        Returns:
            受影响的品类列表，每项包含:
                - category: str  品类名称
                - weight: float  该材料在该品类中的成本权重
                - price_sensitivity: float  价格敏感度
        """
        from app.knowledge.category_material_mapping import (
            get_category_material_mapping_service,
            CATEGORY_MAPPING_DATA,
        )

        service = get_category_material_mapping_service()
        categories = service.get_categories_for_material(material_key)

        result = []
        for cat in categories:
            for m in CATEGORY_MAPPING_DATA.get(cat, []):
                if m.material_key == material_key:
                    result.append({
                        "category": cat,
                        "weight": m.weight,
                        "price_sensitivity": m.price_sensitivity,
                        "lead_time_days": m.lead_time_days,
                    })
                    break
        return result
