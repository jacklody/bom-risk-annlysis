"""BOM暴露度模型定义。

T2-006: BOM暴露度引擎 - 数据模型
定义风险事件对BOM物料暴露程度的计算结果结构。

核心模型:
- ExposureResult: 单个物料的暴露度评估结果
- ExposureFactorDetail: 四因子评分明细
- BatchExposureReport: 批量计算汇总报告
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class CriticalityLevel(str, Enum):
    """物料功能关键度等级。

    关键度越高，该物料出问题时对整机影响越大。
    排序: MCU > power > active > passive > mechanical
    """
    MCU = "mcu"               # 微控制器/主控芯片
    POWER = "power"           # 功率器件 (MOSFET/IGBT)
    ACTIVE = "active"         # 有源器件 (IC/晶体管)
    PASSIVE_HIGH = "passive_high"  # 关键被动件 (MLCC/晶振)
    PASSIVE = "passive"       # 普通被动件 (电阻/电容)
    CONNECTOR = "connector"   # 连接器/线束
    MECHANICAL = "mechanical" # 结构件/散热器
    DISPLAY = "display"       # 显示/光电
    BATTERY = "battery"       # 电池
    OTHER = "other"           # 其他


# 关键度 -> 权重系数映射 (0.0 ~ 1.0)
CRITICALITY_WEIGHT_MAP: Dict[CriticalityLevel, float] = {
    CriticalityLevel.MCU: 1.0,
    CriticalityLevel.POWER: 0.95,
    CriticalityLevel.ACTIVE: 0.85,
    CriticalityLevel.PASSIVE_HIGH: 0.75,
    CriticalityLevel.PASSIVE: 0.55,
    CriticalityLevel.CONNECTOR: 0.50,
    CriticalityLevel.MECHANICAL: 0.35,
    CriticalityLevel.DISPLAY: 0.40,
    CriticalityLevel.BATTERY: 0.80,
    CriticalityLevel.OTHER: 0.30,
}

# 品类名称 -> 关键度映射
CATEGORY_CRITICALITY_MAP: Dict[str, CriticalityLevel] = {
    # MCU / 主控
    "MCU": CriticalityLevel.MCU,
    "汽车MCU": CriticalityLevel.MCU,
    "通用MCU": CriticalityLevel.MCU,
    # 功率器件
    "MOSFET/IGBT": CriticalityLevel.POWER,
    # 有源器件
    "IC": CriticalityLevel.ACTIVE,
    "晶体管": CriticalityLevel.ACTIVE,
    # 关键被动件
    "MLCC": CriticalityLevel.PASSIVE_HIGH,
    "晶振": CriticalityLevel.PASSIVE_HIGH,
    # 普通被动件
    "电阻": CriticalityLevel.PASSIVE,
    "铝电解电容": CriticalityLevel.PASSIVE,
    "薄膜电容": CriticalityLevel.PASSIVE,
    "电感/变压器": CriticalityLevel.PASSIVE,
    # PCB
    "PCB/FPC": CriticalityLevel.PASSIVE_HIGH,
    # 连接器/线缆
    "连接器": CriticalityLevel.CONNECTOR,
    "线束": CriticalityLevel.CONNECTOR,
    "继电器": CriticalityLevel.CONNECTOR,
    # 结构/散热
    "散热器": CriticalityLevel.MECHANICAL,
    "结构件": CriticalityLevel.MECHANICAL,
    # 电池
    "电池": CriticalityLevel.BATTERY,
    # 显示
    "显示/光电": CriticalityLevel.DISPLAY,
}


@dataclass
class ExposureFactorDetail:
    """四因子评分明细。

    BOM暴露度 = 用量权重(30%) + 项目权重(30%) + 关键度权重(20%) + 集中度权重(20%)

    Attributes:
        usage_weight_score: 用量权重评分 (0-100), 该物料在项目BOM中的用量占比
        project_weight_score: 项目权重评分 (0-100), 该物料被多少个项目共用
        criticality_weight_score: 关键度权重评分 (0-100), 物料功能关键程度
        concentration_weight_score: 集中度权重评分 (0-100), 供应商/品牌集中度
        usage_ratio: 物料占BOM总金额的比例 (0.0-1.0)
        project_count: 被多少个项目共用
        is_single_source: 是否单源供应
        criticality: 关键度等级
    """
    usage_weight_score: float = 0.0
    project_weight_score: float = 0.0
    criticality_weight_score: float = 0.0
    concentration_weight_score: float = 0.0
    usage_ratio: float = 0.0
    project_count: int = 1
    is_single_source: bool = False
    criticality: str = CriticalityLevel.OTHER.value


@dataclass(frozen=True)
class ExposureResult:
    """单个物料的暴露度评估结果。

    表示一个风险事件对某个BOM物料的暴露程度，分值0-100，可排序。

    Attributes:
        material_id: BOM物料ID
        risk_event_id: 风险事件ID
        exposure_score: 暴露度分值 (0-100)
        affected_categories: 受影响品类列表
        usage_ratio: 占BOM总金额比例 (0.0-1.0)
        project_count: 被多少个项目共用
        is_single_source: 是否单源供应
        criticality: 关键度等级 ("high" / "medium" / "low")
        factor_detail: 四因子评分明细
        chain_path: 风险传导路径 (如 ["银", "银浆", "MLCC"])
        risk_event_description: 风险事件描述
    """
    material_id: int
    risk_event_id: int
    exposure_score: float  # 0-100
    affected_categories: List[str] = field(default_factory=list)
    usage_ratio: float = 0.0
    project_count: int = 1
    is_single_source: bool = False
    criticality: str = "low"
    factor_detail: Optional[ExposureFactorDetail] = None
    chain_path: List[str] = field(default_factory=list)
    risk_event_description: str = ""

    def __lt__(self, other: "ExposureResult") -> bool:
        """支持按暴露度分值排序。"""
        return self.exposure_score < other.exposure_score

    def __le__(self, other: "ExposureResult") -> bool:
        return self.exposure_score <= other.exposure_score

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典，便于API返回。"""
        result: Dict[str, Any] = {
            "material_id": self.material_id,
            "risk_event_id": self.risk_event_id,
            "exposure_score": round(self.exposure_score, 1),
            "affected_categories": self.affected_categories,
            "usage_ratio": round(self.usage_ratio, 4),
            "project_count": self.project_count,
            "is_single_source": self.is_single_source,
            "criticality": self.criticality,
            "chain_path": self.chain_path,
            "risk_event_description": self.risk_event_description,
        }
        if self.factor_detail:
            fd = self.factor_detail
            result["factor_detail"] = {
                "usage_weight_score": round(fd.usage_weight_score, 1),
                "project_weight_score": round(fd.project_weight_score, 1),
                "criticality_weight_score": round(fd.criticality_weight_score, 1),
                "concentration_weight_score": round(fd.concentration_weight_score, 1),
                "usage_ratio": round(fd.usage_ratio, 4),
                "project_count": fd.project_count,
                "is_single_source": fd.is_single_source,
                "criticality": fd.criticality,
            }
        return result


@dataclass
class BatchExposureReport:
    """批量暴露度计算汇总报告。

    Attributes:
        risk_event_id: 风险事件ID
        risk_event_description: 风险事件描述
        total_materials_evaluated: 评估的物料总数
        exposed_material_count: 受影响的物料数量
        results: 按暴露度降序排列的结果列表
        affected_categories_summary: 受影响品类汇总
        compute_time_ms: 计算耗时(毫秒)
    """
    risk_event_id: int
    risk_event_description: str = ""
    total_materials_evaluated: int = 0
    exposed_material_count: int = 0
    results: List[ExposureResult] = field(default_factory=list)
    affected_categories_summary: Dict[str, int] = field(default_factory=dict)
    compute_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典。"""
        return {
            "risk_event_id": self.risk_event_id,
            "risk_event_description": self.risk_event_description,
            "total_materials_evaluated": self.total_materials_evaluated,
            "exposed_material_count": self.exposed_material_count,
            "results": [r.to_dict() for r in self.results],
            "affected_categories_summary": self.affected_categories_summary,
            "compute_time_ms": round(self.compute_time_ms, 2),
        }
