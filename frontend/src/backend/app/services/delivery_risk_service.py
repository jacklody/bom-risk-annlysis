"""交付风险预警服务 (T2-010)。

聚合 ChainQueryService、MultiFactorRiskEngine、BomExposureEngine、RecommendationGenerator
的输出，生成项目级交付风险视图：项目汇总 + 物料明细 + 时间线 + 建议。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.bom import BomItem, BomProject

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────
# 数据类
# ────────────────────────────────────────────────────────────

class MaterialRiskView:
    """单个物料的交付风险视图。"""

    def __init__(
        self,
        material_id: int,
        mpn: str,
        brand: str,
        category: str,
        risk_score: float,
        risk_level: str,
        trend: str,
        lead_time_impact_weeks: float,
        exposure_score: float,
        suggestion: str,
        is_acknowledged: bool = False,
    ):
        self.material_id = material_id
        self.mpn = mpn
        self.brand = brand
        self.category = category
        self.risk_score = risk_score
        self.risk_level = risk_level
        self.trend = trend  # "up" | "down" | "flat"
        self.lead_time_impact_weeks = lead_time_impact_weeks
        self.exposure_score = exposure_score
        self.suggestion = suggestion
        self.is_acknowledged = is_acknowledged

    def to_dict(self) -> dict:
        return {
            "material_id": self.material_id,
            "mpn": self.mpn,
            "brand": self.brand,
            "category": self.category,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "trend": self.trend,
            "lead_time_impact_weeks": self.lead_time_impact_weeks,
            "exposure_score": self.exposure_score,
            "suggestion": self.suggestion,
            "is_acknowledged": self.is_acknowledged,
        }


class ProjectRiskOverview:
    """项目级风险总览。"""

    def __init__(
        self,
        project_id: int,
        project_name: str,
        overall_risk_level: str,
        total_materials: int,
        red_count: int,
        orange_count: int,
        yellow_count: int,
        green_count: int,
        recent_event_count: int,
        gray_count: int = 0,
    ):
        self.project_id = project_id
        self.project_name = project_name
        self.overall_risk_level = overall_risk_level
        self.total_materials = total_materials
        self.red_count = red_count
        self.orange_count = orange_count
        self.yellow_count = yellow_count
        self.green_count = green_count
        self.gray_count = gray_count
        self.recent_event_count = recent_event_count

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "project_name": self.project_name,
            "overall_risk_level": self.overall_risk_level,
            "total_materials": self.total_materials,
            "red_count": self.red_count,
            "orange_count": self.orange_count,
            "yellow_count": self.yellow_count,
            "green_count": self.green_count,
            "gray_count": self.gray_count,
            "recent_event_count": self.recent_event_count,
        }


class TimelineEvent:
    """风险时间线事件。"""

    def __init__(
        self,
        event_id: int,
        timestamp: str,
        title: str,
        event_type: str,
        severity: str,
        source: str,
        affected_materials: List[str],
    ):
        self.event_id = event_id
        self.timestamp = timestamp
        self.title = title
        self.event_type = event_type
        self.severity = severity
        self.source = source
        self.affected_materials = affected_materials

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "title": self.title,
            "event_type": self.event_type,
            "severity": self.severity,
            "source": self.source,
            "affected_materials": self.affected_materials,
        }


class RecommendationItem:
    """建议措施条目。"""

    def __init__(
        self,
        rec_id: str,
        role: str,
        action_type: str,
        title: str,
        detail: str,
        urgency: str,
        material: str,
    ):
        self.rec_id = rec_id
        self.role = role
        self.action_type = action_type
        self.title = title
        self.detail = detail
        self.urgency = urgency
        self.material = material

    def to_dict(self) -> dict:
        return {
            "rec_id": self.rec_id,
            "role": self.role,
            "action_type": self.action_type,
            "title": self.title,
            "detail": self.detail,
            "urgency": self.urgency,
            "material": self.material,
        }


# ────────────────────────────────────────────────────────────
# 核心服务
# ────────────────────────────────────────────────────────────

class DeliveryRiskService:
    """交付风险预警聚合服务。

    调用 ChainQueryService (T2-005)、MultiFactorRiskEngine (T2-001)、
    BomExposureEngine (T2-006)、RecommendationGenerator (T2-013)
    聚合为交付风险视图。
    """

    def __init__(self, db: Session):
        self.db = db
        self._chain_query_service = None
        self._multi_factor_engine = None
        self._bom_exposure_engine = None
        self._recommendation_generator = None
        # 内存存储已确认的风险项 (material_id -> True)
        self._acknowledged: Dict[int, bool] = {}

    def _get_chain_query_service(self):
        if self._chain_query_service is None:
            from app.services.chain_query_service import ChainQueryService
            self._chain_query_service = ChainQueryService(self.db)
        return self._chain_query_service

    def _get_multi_factor_engine(self):
        if self._multi_factor_engine is None:
            from app.services.upstream.multi_factor_risk_engine import MultiFactorRiskEngine
            self._multi_factor_engine = MultiFactorRiskEngine()
        return self._multi_factor_engine

    def _get_bom_exposure_engine(self):
        if self._bom_exposure_engine is None:
            from app.services.bom_exposure_engine import BomExposureEngine
            chain_svc = self._get_chain_query_service()
            self._bom_exposure_engine = BomExposureEngine(chain_svc)
        return self._bom_exposure_engine

    def _get_recommendation_generator(self):
        if self._recommendation_generator is None:
            from app.services.llm.recommendation_generator import RecommendationGenerator
            self._recommendation_generator = RecommendationGenerator()
        return self._recommendation_generator

    # ────────────────────────────────────────────────────────
    # 公开接口
    # ────────────────────────────────────────────────────────

    def get_project_overview(self, project_id: int) -> Optional[ProjectRiskOverview]:
        """获取项目级风险总览（红黄绿灯）。"""
        project = self.db.query(BomProject).filter(BomProject.id == project_id).first()
        if not project:
            return None

        items = self.db.query(BomItem).filter(BomItem.bom_upload_id == project_id).all()

        red_count = sum(1 for i in items if i.risk_level and i.risk_level.value == "red")
        orange_count = sum(1 for i in items if i.risk_level and i.risk_level.value == "orange")
        yellow_count = sum(1 for i in items if i.risk_level and i.risk_level.value == "yellow")
        green_count = sum(1 for i in items if i.risk_level and i.risk_level.value == "green")
        gray_count = sum(1 for i in items if not i.risk_level or i.risk_level.value == "gray")

        # 整体风险等级（灰色不允许显示为正常，gray不降低整体等级）
        if red_count > 0:
            overall = "red"
        elif orange_count > 0:
            overall = "orange"
        elif yellow_count > 0:
            overall = "yellow"
        elif gray_count > 0 and green_count == 0:
            overall = "gray"
        else:
            overall = "green"

        # 最近30天事件数
        from app.models.event import MarketEvent
        since = datetime.now(timezone.utc) - timedelta(days=30)
        recent_events = self.db.query(MarketEvent).filter(
            MarketEvent.created_at >= since,
            MarketEvent.is_active == 1,
        ).all()

        return ProjectRiskOverview(
            project_id=project.id,
            project_name=project.project_name or project.filename,
            overall_risk_level=overall,
            total_materials=len(items),
            red_count=red_count,
            orange_count=orange_count,
            yellow_count=yellow_count,
            green_count=green_count,
            recent_event_count=len(recent_events),
            gray_count=gray_count,
        )

    def get_material_risk_list(self, project_id: int) -> List[MaterialRiskView]:
        """获取物料级风险列表（按风险分排序）。"""
        items = (
            self.db.query(BomItem)
            .filter(BomItem.bom_upload_id == project_id)
            .order_by(BomItem.risk_score.desc() if hasattr(BomItem, 'risk_score') else BomItem.id)
            .all()
        )

        results: List[MaterialRiskView] = []
        for item in items:
            risk_score = float(item.risk_score or 0)
            risk_level = item.risk_level.value if item.risk_level else "gray"

            # 趋势判断：基于风险分
            if risk_score >= 80:
                trend = "up"
            elif risk_score >= 35:
                trend = "flat"
            else:
                trend = "down"

            # 交期影响估算
            lead_time_impact = self._estimate_lead_time_impact(risk_score, item.lead_time_days)

            # 暴露度
            exposure_score = self._calculate_material_exposure(item)

            # 建议
            suggestion = self._generate_material_suggestion(item, risk_level)

            results.append(MaterialRiskView(
                material_id=item.id,
                mpn=item.raw_part_number or "未知型号",
                brand=item.raw_brand or "",
                category=item.normalized_category or item.raw_category or "未分类",
                risk_score=risk_score,
                risk_level=risk_level,
                trend=trend,
                lead_time_impact_weeks=lead_time_impact,
                exposure_score=exposure_score,
                suggestion=suggestion,
                is_acknowledged=self._acknowledged.get(item.id, False),
            ))

        # 按风险分降序排序
        results.sort(key=lambda r: r.risk_score, reverse=True)
        return results

    def get_risk_timeline(self, project_id: int, days: int = 30) -> List[TimelineEvent]:
        """获取风险时间线（最近N天事件流）。"""
        from app.models.event import MarketEvent

        since = datetime.now(timezone.utc) - timedelta(days=days)
        events = (
            self.db.query(MarketEvent)
            .filter(
                MarketEvent.created_at >= since,
                MarketEvent.is_active == 1,
            )
            .order_by(MarketEvent.created_at.desc())
            .all()
        )

        results: List[TimelineEvent] = []
        for evt in events:
            severity_map = {
                "high": "red",
                "medium": "orange",
                "low": "yellow",
            }
            severity = severity_map.get(
                evt.severity.value if hasattr(evt.severity, 'value') else str(evt.severity),
                "yellow"
            )

            # 获取受影响物料
            affected = self._get_affected_materials_for_event(project_id, evt)

            results.append(TimelineEvent(
                event_id=evt.id,
                timestamp=evt.created_at.isoformat() if evt.created_at else "",
                title=evt.raw_title or "未命名事件",
                event_type=evt.event_type.value if hasattr(evt.event_type, 'value') else str(evt.event_type),
                severity=severity,
                source=evt.source_name or "未知来源",
                affected_materials=affected,
            ))

        return results

    def get_recommendations(self, project_id: int) -> List[RecommendationItem]:
        """获取建议措施列表。"""
        material_list = self.get_material_risk_list(project_id)

        recommendations: List[RecommendationItem] = []
        rec_counter = 0

        for mat in material_list:
            if mat.risk_level in ("red", "orange"):
                rec_counter += 1
                recommendations.append(RecommendationItem(
                    rec_id=f"rec-{rec_counter:03d}",
                    role="采购",
                    action_type="lock_price",
                    title=f"锁定 {mat.mpn} 供应",
                    detail=f"{mat.mpn} 当前风险等级 {mat.risk_level}，建议立即锁定12周需求量并与供应商签订长协",
                    urgency="high" if mat.risk_level == "red" else "medium",
                    material=mat.mpn,
                ))
                rec_counter += 1
                recommendations.append(RecommendationItem(
                    rec_id=f"rec-{rec_counter:03d}",
                    role="研发",
                    action_type="alt_verification",
                    title=f"启动 {mat.mpn} 替代料验证",
                    detail=f"评估国产替代方案，优先 Pin-to-Pin 兼容型号，预计验证周期4-8周",
                    urgency="high" if mat.risk_level == "red" else "medium",
                    material=mat.mpn,
                ))

            if mat.risk_level == "red" and mat.lead_time_impact_weeks > 4:
                rec_counter += 1
                recommendations.append(RecommendationItem(
                    rec_id=f"rec-{rec_counter:03d}",
                    role="项目经理",
                    action_type="schedule_buffer",
                    title=f"增加交期缓冲",
                    detail=f"{mat.mpn} 预计交期影响 {mat.lead_time_impact_weeks:.1f} 周，建议在项目关键路径增加缓冲",
                    urgency="high",
                    material=mat.mpn,
                ))

        return recommendations

    def acknowledge_risk(self, material_id: int) -> bool:
        """确认某条风险已处理。"""
        item = self.db.query(BomItem).filter(BomItem.id == material_id).first()
        if not item:
            return False
        self._acknowledged[material_id] = True
        return True

    # ────────────────────────────────────────────────────────
    # 内部辅助方法
    # ────────────────────────────────────────────────────────

    def _estimate_lead_time_impact(self, risk_score: float, current_lead_time_days: Optional[int]) -> float:
        """估算交期影响（周）。"""
        base_lead = (current_lead_time_days or 14) / 7.0
        if risk_score >= 80:
            return round(base_lead * 1.5, 1)
        elif risk_score >= 60:
            return round(base_lead * 1.2, 1)
        elif risk_score >= 35:
            return round(base_lead * 1.0, 1)
        else:
            return round(base_lead * 0.8, 1)

    def _calculate_material_exposure(self, item: BomItem) -> float:
        """计算单个物料的暴露度分数。"""
        try:
            exposure_engine = self._get_bom_exposure_engine()
            bom_item_dict = {
                "material_id": item.id,
                "category": item.normalized_category or item.raw_category or "",
                "usage_ratio": 0.1,  # 默认值
                "project_count": 1,
                "is_single_source": (item.supplier_count or 0) <= 1,
                "brand": item.raw_brand or "",
                "name": item.raw_part_number or "",
            }
            result = exposure_engine.calculate_single_material_exposure(
                risk_event_description=f"{item.raw_category or '物料'}供应风险",
                risk_event_id=item.id,
                **bom_item_dict,
            )
            return result.exposure_score
        except Exception as e:
            logger.debug("暴露度计算降级: %s", str(e))
            # 降级: 基于风险分估算
            return float(item.risk_score or 0) * 0.7

    def _generate_material_suggestion(self, item: BomItem, risk_level: str) -> str:
        """为单个物料生成建议。"""
        mpn = item.raw_part_number or "该物料"
        category = item.normalized_category or item.raw_category or "该品类"

        if risk_level == "red":
            return f"紧急：{mpn} 交付风险极高，建议立即锁单并启动替代料方案"
        elif risk_level == "orange":
            return f"高风险：{mpn} 供应不稳定，建议提升安全库存至8周并寻找二供"
        elif risk_level == "yellow":
            return f"关注：{mpn} 存在早期风险信号，建议纳入观察池跟踪"
        else:
            return f"{mpn} 当前风险可控，保持常规监控"

    def _get_affected_materials_for_event(self, project_id: int, event) -> List[str]:
        """获取某事件在指定项目中影响的物料列表。"""
        items = self.db.query(BomItem).filter(BomItem.bom_upload_id == project_id).all()
        affected = []
        event_category = getattr(event, 'category', '') or ''
        for item in items:
            item_cat = item.normalized_category or item.raw_category or ''
            if event_category and item_cat and (
                event_category.lower() in item_cat.lower() or item_cat.lower() in event_category.lower()
            ):
                affected.append(item.raw_part_number or "未知物料")
        return affected[:5]  # 最多返回5个
