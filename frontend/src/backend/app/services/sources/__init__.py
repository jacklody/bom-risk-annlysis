"""数据源模块 — 统一的多源物料查询接口"""

from .base import BaseSource, SourceResult
from .lcsc import LCSCSource
from .mouser import MouserSource
from .digikey import DigiKeySource
from .guanxintai import GuanxintaiSource
from .gdacs_source import GdacsSource
from .usgs_earthquake_source import UsgsEarthquakeSource
from .octopart_source import OctopartSource

__all__ = [
    "BaseSource", "SourceResult",
    "LCSCSource", "MouserSource", "DigiKeySource", "GuanxintaiSource",
    "GdacsSource", "UsgsEarthquakeSource",
    "OctopartSource",
]
