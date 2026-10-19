"""产业链知识图谱 - 边/传导关系模型 & 品类-材料映射模型。

T2-005: 产业链知识图谱数据模型
"""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey
from app.database import Base


class IndustryEdge(Base):
    """产业链图谱边（传导关系）。

    edge_type 取值:
      - supply_chain: 供应链上下游关系 (from 是上游, to 是下游)
      - co_material: 共享材料关系
      - substitute: 替代关系
    """

    __tablename__ = "industry_edge"

    id = Column(Integer, primary_key=True, autoincrement=True)
    from_node_id = Column(Integer, ForeignKey("industry_node.id"), nullable=False, index=True)
    to_node_id = Column(Integer, ForeignKey("industry_node.id"), nullable=False, index=True)
    edge_type = Column(String(64), nullable=False)
    transfer_rate = Column(Float, nullable=True, comment="转嫁率 0~1")
    lag_months = Column(Float, nullable=True, comment="滞后传导时间(月)")
    confidence = Column(Float, default=0.8, comment="置信度 0~1")
    description = Column(Text, nullable=True)

    created_at = Column(
        Integer,
        default=lambda: int(datetime.now(timezone.utc).timestamp()),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "from_node_id": self.from_node_id,
            "to_node_id": self.to_node_id,
            "edge_type": self.edge_type,
            "transfer_rate": self.transfer_rate,
            "lag_months": self.lag_months,
            "confidence": self.confidence,
            "description": self.description,
        }

    def __repr__(self) -> str:
        return (
            f"<IndustryEdge(id={self.id}, {self.from_node_id}->{self.to_node_id}, "
            f"type={self.edge_type}, rate={self.transfer_rate})>"
        )


class CategoryMaterialMapping(Base):
    """品类-材料映射表。

    建立 BOM 品类与上游原材料之间的映射关系，
    附带成本权重和数据源信息。
    """

    __tablename__ = "category_material_mapping"

    id = Column(Integer, primary_key=True, autoincrement=True)
    component_category = Column(String(128), nullable=False, index=True, comment="BOM品类名称")
    material_name = Column(String(256), nullable=False, index=True, comment="上游材料名称")
    cost_weight = Column(Float, nullable=True, comment="成本权重 0~1")
    data_source = Column(String(256), nullable=True, comment="数据源标识")

    created_at = Column(
        Integer,
        default=lambda: int(datetime.now(timezone.utc).timestamp()),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "component_category": self.component_category,
            "material_name": self.material_name,
            "cost_weight": self.cost_weight,
            "data_source": self.data_source,
        }

    def __repr__(self) -> str:
        return (
            f"<CategoryMaterialMapping({self.component_category} -> "
            f"{self.material_name}, w={self.cost_weight})>"
        )
