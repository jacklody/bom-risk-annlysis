"""MaterialPrice 模型 — 上游原材料价格持久化。

每行记录一次原材料价格采集快照，支持：
- 价格历史查询（按 material_key + 时间范围）
- 30 日/90 日基线计算
- 多数据源价格对比
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Index, Integer, String

from app.database import Base


class MaterialPrice(Base):
    __tablename__ = "material_prices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    material_key = Column(String(64), nullable=False)
    price_value = Column(Float, nullable=False)
    price_unit = Column(String(32), default="元/吨")
    source_name = Column(String(128), nullable=False)
    fetch_timestamp = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_material_price_key_ts", "material_key", "fetch_timestamp"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "material_key": self.material_key,
            "price_value": self.price_value,
            "price_unit": self.price_unit,
            "source_name": self.source_name,
            "fetch_timestamp": self.fetch_timestamp.isoformat() if self.fetch_timestamp else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ── v4.0 数据新鲜度监控模型 ─────────────────────────────────────
from typing import Optional, List
from pydantic import BaseModel, Field


class MaterialPriceRecord(BaseModel):
    """材料价格数据记录 — Pydantic 响应模型。"""
    material_key: str = Field(..., description="材料代码")
    price: Optional[float] = Field(None, description="当前价格")
    unit: str = Field(default="元/吨", description="单位")
    source: str = Field(..., description="数据源标识")
    updated_at: datetime = Field(..., description="最后更新时间")
    freshness_hours: float = Field(0.0, description="数据新鲜度（小时）")
    is_stale: bool = Field(False, description="是否过期")

    class Config:
        from_attributes = True


class FreshnessResult(BaseModel):
    """单个材料的新鲜度检查结果。"""
    material_key: str
    source: str
    updated_at: Optional[datetime] = None
    hours_since_update: float = 0.0
    threshold_hours: float = 24.0
    is_stale: bool = False
    severity: str = "ok"  # ok / warning / critical

    class Config:
        from_attributes = True


class FreshnessAlert(BaseModel):
    """数据新鲜度预警。"""
    material_key: str = Field(..., description="材料代码")
    source: str = Field(..., description="数据源标识")
    hours_since_update: float = Field(..., description="距上次更新的小时数")
    threshold_hours: float = Field(..., description="阈值小时数")
    severity: str = Field(..., description="严重程度: warning / critical")

    class Config:
        from_attributes = True


class SourceHealth(BaseModel):
    """数据源健康状态汇总。"""
    source: str
    total_materials: int = 0
    fresh_count: int = 0
    stale_count: int = 0
    avg_freshness_hours: float = 0.0
    last_success_at: Optional[datetime] = None
    degraded: bool = False

    class Config:
        from_attributes = True
