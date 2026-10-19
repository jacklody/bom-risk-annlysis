"""产业链知识图谱 - 节点模型。

T2-005: 产业链知识图谱数据模型
节点类型: material / sub_assembly / component_category / factory / region
"""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text
from app.database import Base


class IndustryNode(Base):
    """产业链图谱节点。

    node_type 取值:
      - material: 基础材料 (铜、铝、石油、镍粉 …)
      - sub_assembly: 中间制品/半成品 (铜箔、CCL、玻纤布 …)
      - component_category: BOM 品类 (PCB、MLCC、连接器 …)
      - factory: 工厂/产线
      - region: 地区/产业集群
    """

    __tablename__ = "industry_node"

    id = Column(Integer, primary_key=True, autoincrement=True)
    node_type = Column(String(64), nullable=False, index=True)
    name = Column(String(256), nullable=False, index=True)
    category = Column(String(128), nullable=True, comment="所属BOM大类")
    geo_location = Column(String(256), nullable=True, comment="地理位置/产业集群")
    node_metadata = Column("metadata", Text, nullable=True, comment="JSON扩展字段")

    created_at = Column(
        Integer,
        default=lambda: int(datetime.now(timezone.utc).timestamp()),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "node_type": self.node_type,
            "name": self.name,
            "category": self.category,
            "geo_location": self.geo_location,
            "metadata": self.node_metadata,
        }

    def __repr__(self) -> str:
        return f"<IndustryNode(id={self.id}, type={self.node_type}, name={self.name!r})>"
