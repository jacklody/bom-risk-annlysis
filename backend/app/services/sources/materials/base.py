"""原材料价格数据源抽象基类。

所有数据源必须实现:
- fetch_prices(material_keys) -> dict[str, float | None]
- is_available() -> bool
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class MaterialPriceSource(ABC):
    """原材料价格数据源抽象基类。"""

    source_name: str = "unknown"

    @abstractmethod
    async def fetch_prices(self, material_keys: List[str]) -> Dict[str, Optional[float]]:
        """获取指定材料的最新价格。

        Args:
            material_keys: 材料标识列表, 如 ["cu_cathode", "al_ingot"]

        Returns:
            {material_key: price_value} 字典。单个材料获取失败时对应值为 None。
            例如: {"cu_cathode": 78200.0, "al_ingot": None}
        """
        ...

    async def is_available(self) -> bool:
        """检查数据源是否可用。默认返回 True，子类可覆写实现健康检查。"""
        return True

    async def fetch_price(self, material_key: str) -> Optional[float]:
        """获取单个材料的价格（便捷方法）。"""
        results = await self.fetch_prices([material_key])
        return results.get(material_key)
