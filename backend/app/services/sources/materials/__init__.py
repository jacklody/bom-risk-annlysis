"""原材料价格数据源包。

数据源实现：
- MetalsAPISource: metals-api.com 免费 API (有色金属域)
- RareEarthSource: 稀土行业协会 HTML 解析 (稀土域, Phase 2)
- SmallMetalSource: 亚洲金属网/金投网 HTML 解析 (小金属域, Phase 2)
- ChemicalSource: 生意社/卓创 HTML 解析 (化工域, Phase 3)

P1 补充数据源 (T2-016):
- SMMSource: 上海有色网 付费API (Cu/Al/Sn/Ni/Ag/稀土/锂电)
- MysteelSource: 我的钢铁网 付费API (冷轧/热轧/硅钢)
- LMESource: 伦敦金属交易所 网页解析 (Cu/Al/Ni/Sn/Zn/Pb/Co)
"""

from app.services.sources.materials.base import MaterialPriceSource
from app.services.sources.materials.metals_api_source import MetalsAPISource
from app.services.sources.materials.smm_source import SMMSource
from app.services.sources.materials.mysteel_source import MysteelSource
from app.services.sources.materials.lme_source import LMESource

__all__ = [
    "MaterialPriceSource",
    "MetalsAPISource",
    "SMMSource",
    "MysteelSource",
    "LMESource",
]
