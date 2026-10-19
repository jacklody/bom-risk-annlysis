"""数据源抽象基类 — 统一各分销商API的查询接口和返回格式。

所有数据源实现以下接口：
- query_by_mpn(mpn) -> SourceResult | None  单物料查询
- source_name -> str                        数据源标识
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SourceResult:
    """统一的数据源查询结果，屏蔽不同 API 的字段差异。"""

    source: str
    mpn_queried: str
    mpn_matched: str = ""
    manufacturer: str = ""

    total_stock: int = 0
    supplier_count: int = 0
    stock_location: str = ""

    lead_time_days: Optional[int] = None
    lead_time_display: str = ""

    unit_price: Optional[float] = None
    price_breaks: list[dict] = field(default_factory=list)
    moq: int = 1
    currency: str = "USD"

    lifecycle_status: str = "Unknown"
    category: str = ""

    product_url: str = ""
    datasheet_url: str = ""

    match_status: str = "not_found"
    error_reason: str = ""
    raw_summary: str = ""
    raw_response: dict = field(default_factory=dict)
    is_available: bool = False


class BaseSource(ABC):
    """数据源抽象基类"""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """数据源名称，如 'lcsc' / 'mouser'"""
        ...

    @abstractmethod
    async def query_by_mpn(self, mpn: str) -> Optional[SourceResult]:
        """根据型号查询物料信息，失败/超时返回 None"""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """检查数据源是否可用"""
        ...

    def clean_mpn(self, mpn: str) -> str:
        """清洗型号：去除包装后缀等，提升匹配率"""
        import re
        mpn = mpn.strip()
        # 去除常见包装后缀
        pack_suffixes = [
            r'[-/\s]T/?R$', r'[-/\s]CT$', r'[-/\s]DKR$',
            r'[-/\s]TAPE$', r'[-/\s]REEL$', r'[-/\s]EMBOSS$',
            r'[-/\s]TUBE$', r'[-/\s]TRAY$',
            r'[-/\s]CUT\s*TAPE$', r'[-/\s]DIGI[-/\s]REEL$',
        ]
        for pattern in pack_suffixes:
            mpn = re.sub(pattern, '', mpn, flags=re.IGNORECASE)
        return mpn.strip()
