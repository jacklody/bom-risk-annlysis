"""BOM暴露度引擎。

T2-006: BOM暴露度引擎
计算风险事件对具体BOM物料的暴露程度。

核心公式:
    BOM暴露度 = 用量权重(30%) + 项目权重(30%) + 关键度权重(20%) + 集中度权重(20%)

风险传导流程:
    1. 输入原材料风险事件 (如"铜价上涨15%")
    2. 通过产业链知识图谱(ChainQueryService.get_downstream_impact)找到受影响品类
    3. 匹配BOM中属于这些品类的物料
    4. 计算每个物料的暴露度分值 (0-100)

依赖:
    - T2-005 ChainQueryService: 产业链知识图谱查询
    - T2-001 MultiFactorRiskResult: 多因子评分引擎 (可选集成)
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

from app.models.exposure import (
    CATEGORY_CRITICALITY_MAP,
    CRITICALITY_WEIGHT_MAP,
    BatchExposureReport,
    CriticalityLevel,
    ExposureFactorDetail,
    ExposureResult,
)
from app.services.chain_query_service import ChainQueryService

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────
# 常量: 四因子权重
# ────────────────────────────────────────────────────────────

WEIGHT_USAGE: float = 0.30        # 用量权重 30%
WEIGHT_PROJECT: float = 0.30      # 项目权重 30%
WEIGHT_CRITICALITY: float = 0.20  # 关键度权重 20%
WEIGHT_CONCENTRATION: float = 0.20  # 集中度权重 20%

# 项目数 -> 评分映射 (项目越多暴露度越高)
PROJECT_COUNT_SCORE_TABLE: Dict[int, float] = {
    1: 20.0,   # 仅1个项目
    2: 40.0,
    3: 60.0,
    4: 70.0,
    5: 80.0,
    6: 85.0,
    7: 90.0,
    8: 93.0,
    9: 96.0,
}
PROJECT_COUNT_SCORE_MAX: float = 100.0  # 10+ 项目

# ────────────────────────────────────────────────────────────
# 品类暴露度下限 (matched materials floor)
# 通过产业链知识图谱匹配到的物料，至少获得该品类的暴露度下限分。
# 因为: 匹配本身已证明供应链风险传导存在，即使该物料用量低、项目少，
# 也代表一个真实的供应风险暴露。
# ────────────────────────────────────────────────────────────

CATEGORY_EXPOSURE_FLOOR: Dict[str, float] = {
    "MCU": 80.0,
    "汽车MCU": 90.0,
    "通用MCU": 85.0,
    "MOSFET/IGBT": 78.0,
    "MLCC": 60.0,
    "晶振": 60.0,
    "PCB/FPC": 55.0,
    "电池": 65.0,
    "铝电解电容": 55.0,
    "薄膜电容": 55.0,
    "电阻": 50.0,
    "电感/变压器": 55.0,
    "连接器": 50.0,
    "线束": 55.0,
    "继电器": 55.0,
    "散热器": 40.0,
    "结构件": 40.0,
    "显示/光电": 50.0,
}

# 关键度等级 -> 简化输出字符串映射
_CRITICALITY_OUTPUT_MAP: Dict[CriticalityLevel, str] = {
    CriticalityLevel.MCU: "high",
    CriticalityLevel.POWER: "high",
    CriticalityLevel.ACTIVE: "high",
    CriticalityLevel.PASSIVE_HIGH: "high",
    CriticalityLevel.PASSIVE: "medium",
    CriticalityLevel.CONNECTOR: "medium",
    CriticalityLevel.MECHANICAL: "low",
    CriticalityLevel.DISPLAY: "medium",
    CriticalityLevel.BATTERY: "high",
    CriticalityLevel.OTHER: "low",
}


class BomExposureEngine:
    """BOM暴露度引擎。

    通过产业链知识图谱将原材料风险事件传导到BOM品类，
    再结合用量、项目数、关键度、集中度四因子计算每个物料的暴露度分值。

    Usage::

        engine = BomExposureEngine(chain_query_service)
        result = engine.calculate_exposure(
            risk_event_description="铜价上涨15%",
            risk_event_id=1,
            bom_items=[...],
        )
    """

    def __init__(self, chain_query_service: ChainQueryService):
        """初始化BOM暴露度引擎。

        Args:
            chain_query_service: 产业链知识图谱查询服务 (T2-005)
        """
        self._chain_service = chain_query_service

    # ────────────────────────────────────────────────────────
    # 公开接口
    # ────────────────────────────────────────────────────────

    def calculate_exposure(
        self,
        risk_event_description: str,
        risk_event_id: int,
        bom_items: List[Dict[str, Any]],
    ) -> BatchExposureReport:
        """计算单个风险事件对所有BOM物料的暴露度。

        流程:
        1. 通过知识图谱找到受影响的品类
        2. 匹配BOM中属于受影响品类的物料
        3. 对每个匹配物料计算四因子暴露度

        Args:
            risk_event_description: 风险事件描述 (如"铜价上涨15%", "白银+200%")
            risk_event_id: 风险事件ID
            bom_items: BOM物料列表，每个物料为字典，需包含:
                - material_id (int): 物料ID
                - category (str): 物料品类 (如"MLCC", "PCB/FPC", "连接器")
                - usage_ratio (float): 占BOM总金额比例 (0.0-1.0)
                - project_count (int, optional): 被多少个项目共用, 默认1
                - is_single_source (bool, optional): 是否单源供应, 默认False
                - brand (str, optional): 品牌
                - name (str, optional): 物料名称
                - criticality (str, optional): 自定义关键度 (覆盖自动推断)

        Returns:
            BatchExposureReport: 批量暴露度计算报告，结果按 exposure_score 降序
        """
        start_time = time.monotonic()

        # Step 1: 通过知识图谱获取受影响的品类
        affected_categories = self._get_affected_categories(risk_event_description)
        affected_cat_names: Set[str] = set(
            impact.category_name for impact in affected_categories
        )

        # Step 2: 匹配BOM物料并计算暴露度
        results: List[ExposureResult] = []
        categories_hit: Dict[str, int] = defaultdict(int)

        for item in bom_items:
            item_category = item.get("category", "")
            if not item_category:
                continue

            # 检查物料品类是否被风险事件命中
            matched_cats = self._match_category(item_category, affected_cat_names)
            if not matched_cats:
                continue

            # 计算该物料的暴露度
            exposure = self._calculate_single_exposure(
                item=item,
                risk_event_id=risk_event_id,
                risk_event_description=risk_event_description,
                affected_categories=list(matched_cats),
                chain_paths=self._get_chain_paths(
                    risk_event_description, matched_cats, affected_categories
                ),
            )
            results.append(exposure)

            for cat in matched_cats:
                categories_hit[cat] += 1

        # 按暴露度降序排序
        results.sort(key=lambda r: r.exposure_score, reverse=True)

        elapsed_ms = (time.monotonic() - start_time) * 1000

        return BatchExposureReport(
            risk_event_id=risk_event_id,
            risk_event_description=risk_event_description,
            total_materials_evaluated=len(bom_items),
            exposed_material_count=len(results),
            results=results,
            affected_categories_summary=dict(categories_hit),
            compute_time_ms=elapsed_ms,
        )

    def calculate_single_material_exposure(
        self,
        risk_event_description: str,
        risk_event_id: int,
        material_id: int,
        category: str,
        usage_ratio: float = 0.0,
        project_count: int = 1,
        is_single_source: bool = False,
        brand: str = "",
        name: str = "",
        criticality_override: Optional[str] = None,
    ) -> ExposureResult:
        """计算单个物料的暴露度（便捷接口）。

        Args:
            risk_event_description: 风险事件描述
            risk_event_id: 风险事件ID
            material_id: 物料ID
            category: 物料品类
            usage_ratio: 占BOM总金额比例
            project_count: 被多少个项目共用
            is_single_source: 是否单源供应
            brand: 品牌
            name: 物料名称
            criticality_override: 自定义关键度

        Returns:
            ExposureResult: 暴露度计算结果
        """
        item: Dict[str, Any] = {
            "material_id": material_id,
            "category": category,
            "usage_ratio": usage_ratio,
            "project_count": project_count,
            "is_single_source": is_single_source,
            "brand": brand,
            "name": name,
        }
        if criticality_override:
            item["criticality"] = criticality_override

        report = self.calculate_exposure(
            risk_event_description=risk_event_description,
            risk_event_id=risk_event_id,
            bom_items=[item],
        )

        if report.results:
            return report.results[0]

        # 未命中任何品类时，返回0分
        return ExposureResult(
            material_id=material_id,
            risk_event_id=risk_event_id,
            exposure_score=0.0,
            affected_categories=[],
            usage_ratio=usage_ratio,
            project_count=project_count,
            is_single_source=is_single_source,
            criticality="low",
            risk_event_description=risk_event_description,
        )

    # ────────────────────────────────────────────────────────
    # 内部: 品类匹配
    # ────────────────────────────────────────────────────────

    def _get_affected_categories(
        self,
        risk_event_description: str,
    ) -> list:
        """通过产业链知识图谱获取受影响品类。

        调用 ChainQueryService.get_downstream_impact 进行风险传导匹配。

        Args:
            risk_event_description: 风险事件描述文本

        Returns:
            DownstreamImpact 列表
        """
        try:
            impacts = self._chain_service.get_downstream_impact(
                material_event=risk_event_description,
                max_depth=5,
            )
            logger.info(
                "风险事件 '%s' 传导到 %d 个品类",
                risk_event_description,
                len(impacts),
            )
            return impacts
        except Exception as e:
            logger.error(
                "知识图谱查询失败, event='%s': %s",
                risk_event_description,
                str(e),
            )
            return []

    def _match_category(
        self,
        item_category: str,
        affected_cat_names: Set[str],
    ) -> Set[str]:
        """匹配物料品类与受影响品类。

        支持精确匹配和模糊匹配（包含关系）。

        Args:
            item_category: BOM物料品类
            affected_cat_names: 知识图谱返回的受影响品类名称集合

        Returns:
            匹配到的受影响品类名称集合
        """
        matched: Set[str] = set()

        for affected in affected_cat_names:
            # 精确匹配
            if item_category == affected:
                matched.add(affected)
                continue
            # 模糊包含匹配
            if item_category in affected or affected in item_category:
                matched.add(affected)
                continue

        return matched

    def _get_chain_paths(
        self,
        risk_event_description: str,
        matched_cats: Set[str],
        all_impacts: list,
    ) -> List[str]:
        """获取风险传导路径。

        Args:
            risk_event_description: 风险事件描述
            matched_cats: 匹配到的品类集合
            all_impacts: 全部 DownstreamImpact 结果

        Returns:
            传导路径列表 (取最佳匹配的路径)
        """
        paths: List[str] = []
        for impact in all_impacts:
            if impact.category_name in matched_cats:
                if impact.chain_path:
                    paths.append(" → ".join(impact.chain_path))
        return paths[:3]  # 最多返回3条路径

    # ────────────────────────────────────────────────────────
    # 内部: 四因子计算
    # ────────────────────────────────────────────────────────

    def _calculate_single_exposure(
        self,
        item: Dict[str, Any],
        risk_event_id: int,
        risk_event_description: str,
        affected_categories: List[str],
        chain_paths: Optional[List[str]] = None,
    ) -> ExposureResult:
        """计算单个物料的暴露度分值。

        BOM暴露度 = 用量权重(30%) + 项目权重(30%) + 关键度权重(20%) + 集中度权重(20%)

        Args:
            item: BOM物料信息字典
            risk_event_id: 风险事件ID
            risk_event_description: 风险事件描述
            affected_categories: 受影响品类列表
            chain_paths: 风险传导路径

        Returns:
            ExposureResult: 暴露度计算结果
        """
        # 提取物料参数
        material_id: int = item.get("material_id", 0)
        usage_ratio: float = float(item.get("usage_ratio", 0.0) or 0.0)
        project_count: int = int(item.get("project_count", 1) or 1)
        is_single_source: bool = bool(item.get("is_single_source", False))
        category: str = item.get("category", "")
        criticality_override: Optional[str] = item.get("criticality")

        # ── 因子1: 用量权重 (0-100) ──
        usage_score = self._calc_usage_weight_score(usage_ratio)

        # ── 因子2: 项目权重 (0-100) ──
        project_score = self._calc_project_weight_score(project_count)

        # ── 因子3: 关键度权重 (0-100) ──
        criticality_level = self._resolve_criticality(category, criticality_override)
        criticality_score = self._calc_criticality_weight_score(criticality_level)

        # ── 因子4: 集中度权重 (0-100) ──
        concentration_score = self._calc_concentration_weight_score(
            is_single_source=is_single_source,
            project_count=project_count,
        )

        # ── 加权求和 ──
        exposure_score = (
            usage_score * WEIGHT_USAGE
            + project_score * WEIGHT_PROJECT
            + criticality_score * WEIGHT_CRITICALITY
            + concentration_score * WEIGHT_CONCENTRATION
        )

        # ── 品类暴露度下限 (matched floor) ──
        # 通过产业链知识图谱匹配到的物料，至少获得该品类的下限分。
        # 匹配本身已证明供应链风险传导存在，确保不会因低用量等因素
        # 导致真实风险被低估。
        floor_score = self._get_category_floor(category)
        exposure_score = max(exposure_score, floor_score)

        # 限制在 0-100 范围
        exposure_score = max(0.0, min(100.0, exposure_score))

        # 构建因子明细
        factor_detail = ExposureFactorDetail(
            usage_weight_score=usage_score,
            project_weight_score=project_score,
            criticality_weight_score=criticality_score,
            concentration_weight_score=concentration_score,
            usage_ratio=usage_ratio,
            project_count=project_count,
            is_single_source=is_single_source,
            criticality=criticality_level.value,
        )

        # 构建输出关键度
        criticality_output = _CRITICALITY_OUTPUT_MAP.get(
            criticality_level, "low"
        )

        return ExposureResult(
            material_id=material_id,
            risk_event_id=risk_event_id,
            exposure_score=round(exposure_score, 1),
            affected_categories=affected_categories,
            usage_ratio=usage_ratio,
            project_count=project_count,
            is_single_source=is_single_source,
            criticality=criticality_output,
            factor_detail=factor_detail,
            chain_path=chain_paths or [],
            risk_event_description=risk_event_description,
        )

    @staticmethod
    def _calc_usage_weight_score(usage_ratio: float) -> float:
        """计算用量权重评分。

        用量占比越大，暴露度越高。
        映射逻辑:
        - usage_ratio = 0.0  -> 0分
        - usage_ratio = 0.05 -> 25分
        - usage_ratio = 0.10 -> 45分
        - usage_ratio = 0.20 -> 70分
        - usage_ratio = 0.30 -> 85分
        - usage_ratio >= 0.5 -> 100分

        Args:
            usage_ratio: 物料占BOM总金额比例 (0.0-1.0)

        Returns:
            0-100 评分
        """
        if usage_ratio <= 0.0:
            return 0.0
        # 使用分段线性映射 + 上限
        # 基础: ratio * 200, 上限100
        # 但为了让低用量也有区分度，采用 sqrt 曲线
        import math
        score = math.sqrt(usage_ratio) * 130
        return min(score, 100.0)

    @staticmethod
    def _calc_project_weight_score(project_count: int) -> float:
        """计算项目权重评分。

        共用项目越多，暴露度越高。
        映射逻辑:
        - 1个项目 -> 20分
        - 3个项目 -> 60分
        - 5个项目 -> 80分
        - 10+ 个项目 -> 100分

        Args:
            project_count: 被多少个项目共用

        Returns:
            0-100 评分
        """
        if project_count <= 0:
            return 0.0
        if project_count in PROJECT_COUNT_SCORE_TABLE:
            return PROJECT_COUNT_SCORE_TABLE[project_count]
        if project_count >= 10:
            return PROJECT_COUNT_SCORE_MAX
        # 在表间线性插值
        keys = sorted(PROJECT_COUNT_SCORE_TABLE.keys())
        for i in range(len(keys) - 1):
            if keys[i] < project_count < keys[i + 1]:
                lower_score = PROJECT_COUNT_SCORE_TABLE[keys[i]]
                upper_score = PROJECT_COUNT_SCORE_TABLE[keys[i + 1]]
                ratio = (project_count - keys[i]) / (keys[i + 1] - keys[i])
                return lower_score + ratio * (upper_score - lower_score)
        return PROJECT_COUNT_SCORE_MAX

    @staticmethod
    def _calc_criticality_weight_score(
        criticality_level: CriticalityLevel,
    ) -> float:
        """计算关键度权重评分。

        MCU > 电阻 → 关键度越高，暴露度评分越高。
        映射逻辑:
        - MCU: 100分 (最关键)
        - 功率器件: 95分
        - 有源器件: 85分
        - 关键被动件: 75分
        - 电池: 80分
        - 普通被动件: 55分
        - 连接器: 50分
        - 显示: 40分
        - 结构件: 35分
        - 其他: 30分

        Args:
            criticality_level: 关键度等级

        Returns:
            0-100 评分
        """
        weight = CRITICALITY_WEIGHT_MAP.get(criticality_level, 0.3)
        return weight * 100.0

    @staticmethod
    def _calc_concentration_weight_score(
        is_single_source: bool,
        project_count: int = 1,
    ) -> float:
        """计算集中度权重评分。

        单源供应 > 多源供应 → 暴露度越高。
        映射逻辑:
        - 单源 + 多项目: 100分 (最危险)
        - 单源 + 单项目: 85分
        - 多源 + 多项目: 40分
        - 多源 + 单项目: 15分

        Args:
            is_single_source: 是否单源供应
            project_count: 被多少个项目共用

        Returns:
            0-100 评分
        """
        if is_single_source:
            if project_count >= 3:
                return 100.0
            elif project_count == 2:
                return 90.0
            else:
                return 85.0
        else:
            if project_count >= 5:
                return 50.0
            elif project_count >= 3:
                return 40.0
            elif project_count == 2:
                return 25.0
            else:
                return 15.0

    @staticmethod
    def _resolve_criticality(
        category: str,
        override: Optional[str] = None,
    ) -> CriticalityLevel:
        """解析物料关键度等级。

        优先使用 override 参数，否则根据品类自动推断。

        Args:
            category: 物料品类名称
            override: 自定义关键度覆盖

        Returns:
            CriticalityLevel 枚举值
        """
        if override:
            try:
                return CriticalityLevel(override.lower())
            except ValueError:
                pass

        # 从品类映射表查找
        level = CATEGORY_CRITICALITY_MAP.get(category)
        if level:
            return level

        # 模糊匹配
        for cat_key, cat_level in CATEGORY_CRITICALITY_MAP.items():
            if cat_key in category or category in cat_key:
                return cat_level

        return CriticalityLevel.OTHER

    @staticmethod
    def _get_category_floor(category: str) -> float:
        """获取品类暴露度下限分。

        通过产业链知识图谱匹配到的物料，至少获得该品类的下限分。
        MCU等高关键度品类下限更高，确保关键物料风险不被低估。

        Args:
            category: 物料品类名称

        Returns:
            品类下限分 (0-100)
        """
        # 精确匹配
        if category in CATEGORY_EXPOSURE_FLOOR:
            return CATEGORY_EXPOSURE_FLOOR[category]

        # 模糊匹配
        for cat_key, floor_val in CATEGORY_EXPOSURE_FLOOR.items():
            if cat_key in category or category in cat_key:
                return floor_val

        return 0.0  # 未知品类无下限
