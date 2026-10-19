"""新项目选型评审服务 (T2-009)。

聚合多引擎输出，生成每个BOM物料的选型评审结论：
- MultiFactorRiskEngine (T2-001): 七因子风险评分
- BomExposureEngine (T2-006): BOM暴露度
- AutoEscalationEngine (T2-007): 自动提级建议
- RecommendationGenerator (T2-013): 替代/行动建议

输出结构:
    ReviewSummary: 项目级汇总（风险分布、品类覆盖）
    ReviewItem: 物料级评审结论（风险等级/分/暴露度/建议/替代方案）
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ReviewItem:
    """单个物料的评审结论。"""
    bom_item_id: str
    mpn: str
    category: str
    manufacturer: str = ""
    risk_level: str = "gray"
    risk_score: float = 0.0
    exposure_score: float = 0.0
    escalation_rules: list[str] = field(default_factory=list)
    recommendation: str = ""
    alt_suggestions: list[str] = field(default_factory=list)
    approved: Optional[bool] = None  # None=待审, True=批准, False=驳回


@dataclass
class ReviewSummary:
    """项目级评审汇总。"""
    project_id: str
    project_name: str
    created_at: str = ""
    total_items: int = 0
    risk_distribution: dict[str, int] = field(default_factory=dict)
    category_coverage: dict[str, int] = field(default_factory=dict)
    approved_count: int = 0
    rejected_count: int = 0
    pending_count: int = 0
    conclusion: str = ""  # "通过" / "有条件通过" / "不通过"
    conclusion_reasons: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════════
# 服务类
# ═══════════════════════════════════════════════════════════════════════════════

class ProjectReviewService:
    """新项目选型评审服务。

    聚合多引擎输出，为每个BOM物料生成评审结论。
    """

    def __init__(
        self,
        risk_engine: Any = None,
        exposure_engine: Any = None,
        escalation_engine: Any = None,
        recommendation_generator: Any = None,
    ):
        self.risk_engine = risk_engine
        self.exposure_engine = exposure_engine
        self.escalation_engine = escalation_engine
        self.recommendation_generator = recommendation_generator
        # 内存存储评审状态（生产环境应持久化）
        self._review_items: dict[str, list[ReviewItem]] = {}
        self._summaries: dict[str, ReviewSummary] = {}

    def get_summary(self, project_id: str) -> ReviewSummary:
        """获取项目评审汇总。"""
        if project_id in self._summaries:
            return self._summaries[project_id]
        return ReviewSummary(project_id=project_id, project_name="")

    def get_bom_items(
        self,
        project_id: str,
        risk_level: Optional[str] = None,
        category: Optional[str] = None,
        manufacturer: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ReviewItem], int]:
        """获取BOM物料评审列表（分页+筛选）。

        Returns:
            (items, total_count)
        """
        items = self._review_items.get(project_id, [])

        # 筛选
        if risk_level:
            items = [i for i in items if i.risk_level == risk_level]
        if category:
            items = [i for i in items if i.category == category]
        if manufacturer:
            items = [i for i in items if i.manufacturer == manufacturer]

        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        return items[start:end], total

    def approve_item(self, project_id: str, bom_item_id: str, approved: bool) -> bool:
        """批准/驳回某物料选型。

        Returns:
            bool: 是否找到并更新成功
        """
        items = self._review_items.get(project_id, [])
        for item in items:
            if item.bom_item_id == bom_item_id:
                item.approved = approved
                # 更新汇总计数
                self._refresh_summary_counts(project_id)
                return True
        return False

    def build_review(self, project_id: str, project_name: str, bom_items: list[dict]) -> ReviewSummary:
        """构建完整评审结论。

        Args:
            project_id: 项目ID
            project_name: 项目名称
            bom_items: BOM物料列表，每项包含:
                - bom_item_id: str
                - mpn: str (物料型号)
                - category: str (品类)
                - manufacturer: str (供应商/品牌)
                - quantity: int (用量)
                - project_count: int (使用项目数)

        Returns:
            ReviewSummary
        """
        review_items: list[ReviewItem] = []

        for bom in bom_items:
            item = self._evaluate_single_item(bom)
            review_items.append(item)

        self._review_items[project_id] = review_items

        # 构建汇总
        summary = self._build_summary(project_id, project_name, review_items)
        self._summaries[project_id] = summary
        return summary

    def export_review(self, project_id: str, format: str = "json") -> dict[str, Any]:
        """导出评审报告数据。

        Args:
            project_id: 项目ID
            format: 导出格式 (json/excel/pdf)

        Returns:
            dict: 导出数据
        """
        summary = self.get_summary(project_id)
        items = self._review_items.get(project_id, [])

        return {
            "format": format,
            "summary": {
                "project_id": summary.project_id,
                "project_name": summary.project_name,
                "total_items": summary.total_items,
                "risk_distribution": summary.risk_distribution,
                "approved_count": summary.approved_count,
                "rejected_count": summary.rejected_count,
                "pending_count": summary.pending_count,
            },
            "items": [
                {
                    "bom_item_id": item.bom_item_id,
                    "mpn": item.mpn,
                    "category": item.category,
                    "manufacturer": item.manufacturer,
                    "risk_level": item.risk_level,
                    "risk_score": item.risk_score,
                    "exposure_score": item.exposure_score,
                    "recommendation": item.recommendation,
                    "approved": item.approved,
                }
                for item in items
            ],
        }

    # ── 内部方法 ──

    def _evaluate_single_item(self, bom: dict) -> ReviewItem:
        """评估单个物料的评审结论。"""
        item = ReviewItem(
            bom_item_id=bom.get("bom_item_id", ""),
            mpn=bom.get("mpn", ""),
            category=bom.get("category", ""),
            manufacturer=bom.get("manufacturer", ""),
        )

        # 1. 调用多因子风险引擎
        if self.risk_engine:
            try:
                risk_result = self.risk_engine.evaluate(bom)
                if risk_result:
                    item.risk_score = getattr(risk_result, "total_score", 0.0)
                    item.risk_level = getattr(risk_result, "risk_level", "gray")
                    if hasattr(item.risk_level, "value"):
                        item.risk_level = item.risk_level.value
            except Exception as e:
                logger.warning(f"风险引擎评估失败 [{bom.get('mpn')}]: {e}")

        # 2. 调用暴露度引擎
        if self.exposure_engine:
            try:
                exposure_result = self.exposure_engine.calculate(
                    category=bom.get("category", ""),
                    quantity=bom.get("quantity", 1),
                    project_count=bom.get("project_count", 1),
                )
                if exposure_result:
                    item.exposure_score = getattr(exposure_result, "exposure_score", 0.0)
            except Exception as e:
                logger.warning(f"暴露度引擎评估失败 [{bom.get('mpn')}]: {e}")

        # 3. 调用自动提级引擎
        if self.escalation_engine:
            try:
                escalation_result = self.escalation_engine.check(risk_result if self.risk_engine else None, bom)
                if escalation_result:
                    item.risk_level = getattr(escalation_result, "final_level", item.risk_level)
                    if hasattr(item.risk_level, "value"):
                        item.risk_level = item.risk_level.value
                    item.escalation_rules = getattr(escalation_result, "triggered_rules", [])
            except Exception as e:
                logger.warning(f"提级引擎评估失败 [{bom.get('mpn')}]: {e}")

        # 4. 调用建议生成器
        if self.recommendation_generator:
            try:
                rec_result = self.recommendation_generator.generate(
                    event="选型评审",
                    risk_level=item.risk_level,
                    risk_score=item.risk_score,
                    affected_materials=[{"mpn": item.mpn, "category": item.category}],
                )
                if rec_result and hasattr(rec_result, "data"):
                    recs = rec_result.data.get("procurement_recommendations", [])
                    if recs:
                        item.recommendation = recs[0].get("detail", "")
                    alts = rec_result.data.get("rd_recommendations", [])
                    if alts:
                        item.alt_suggestions = [a.get("detail", "") for a in alts[:3]]
            except Exception as e:
                logger.warning(f"建议生成失败 [{bom.get('mpn')}]: {e}")

        return item

    def _judge_conclusion(
        self, items: list[ReviewItem], risk_dist: dict[str, int]
    ) -> tuple[str, list[str]]:
        """项目级评审结论自动判定。

        判定规则（PRD要求）:
          - 不通过: 存在红色风险物料 OR 有2个及以上item被驳回(approved=False)
          - 有条件通过: 存在橙色风险物料 OR 有1个item被驳回 OR 存在gray(数据不足)物料
          - 通过: 全部item为green且无pending审批
          - 其他情况（有待审项但无风险）→ 有条件通过
        """
        reasons: list[str] = []

        # ── 不通过 ──
        red_count = risk_dist.get("red", 0)
        rejected_count = sum(1 for item in items if item.approved is False)

        if red_count > 0:
            reasons.append(f"存在 {red_count} 个红色风险物料，需立即处置")
            return "不通过", reasons
        if rejected_count >= 2:
            reasons.append(f"{rejected_count} 个物料被驳回，评审不通过")
            return "不通过", reasons

        # ── 有条件通过 ──
        orange_count = risk_dist.get("orange", 0)
        gray_count = risk_dist.get("gray", 0)
        pending_count = sum(1 for item in items if item.approved is None)

        if orange_count > 0:
            reasons.append(f"存在 {orange_count} 个橙色风险物料，需关注并制定预案")
        if rejected_count == 1:
            reasons.append("有 1 个物料被驳回，需补充说明后重新评审")
        if gray_count > 0:
            reasons.append(f"存在 {gray_count} 个物料数据不足(灰色)，建议补充信息后再评估")
        if pending_count > 0 and not reasons:
            reasons.append(f"仍有 {pending_count} 个物料待审")

        if reasons:
            return "有条件通过", reasons

        # ── 通过 ──
        return "通过", ["所有物料风险可控，评审通过"]

    def _build_summary(
        self, project_id: str, project_name: str, items: list[ReviewItem]
    ) -> ReviewSummary:
        """构建项目汇总。"""
        risk_dist: dict[str, int] = {}
        category_cov: dict[str, int] = {}
        approved = rejected = pending = 0

        for item in items:
            # 风险分布
            level = item.risk_level or "gray"
            risk_dist[level] = risk_dist.get(level, 0) + 1

            # 品类覆盖
            cat = item.category or "未知"
            category_cov[cat] = category_cov.get(cat, 0) + 1

            # 审批状态
            if item.approved is True:
                approved += 1
            elif item.approved is False:
                rejected += 1
            else:
                pending += 1

        # ── 项目级结论自动判定（通过/有条件通过/不通过）──
        conclusion, reasons = self._judge_conclusion(items, risk_dist)

        return ReviewSummary(
            project_id=project_id,
            project_name=project_name,
            total_items=len(items),
            risk_distribution=risk_dist,
            category_coverage=category_cov,
            approved_count=approved,
            rejected_count=rejected,
            pending_count=pending,
            conclusion=conclusion,
            conclusion_reasons=reasons,
        )

    def _refresh_summary_counts(self, project_id: str) -> None:
        """刷新汇总中的审批计数。"""
        if project_id not in self._summaries:
            return
        summary = self._summaries[project_id]
        items = self._review_items.get(project_id, [])
        approved = rejected = pending = 0
        for item in items:
            if item.approved is True:
                approved += 1
            elif item.approved is False:
                rejected += 1
            else:
                pending += 1
        summary.approved_count = approved
        summary.rejected_count = rejected
        summary.pending_count = pending


# ═══════════════════════════════════════════════════════════════════════════════
# 全局单例
# ═══════════════════════════════════════════════════════════════════════════════

_review_service: ProjectReviewService | None = None


def get_project_review_service() -> ProjectReviewService:
    """获取或创建 ProjectReviewService 单例。"""
    global _review_service
    if _review_service is None:
        _review_service = ProjectReviewService()
    return _review_service
