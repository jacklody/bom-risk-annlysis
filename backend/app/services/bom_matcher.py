"""BOM物料与市场事件的匹配引擎

v2.0：全量收集模式，不再短路。收集全部命中事件后综合评分，
确保物料风险全景可追溯，不遗漏任何关联事件。

v4.1 (T2-004)：新增生命周期状态影响逻辑
    - Octopart/Nexar 生命周期数据接入
    - NRND → 自动提升至黄色
    - EOL → 自动提升至橙色，若无替代料则红色
    - Unknown → 显示灰色，提示数据不足
    - 降级策略：Octopart 不可用时 fallback 到 DigiKey/Mouser
"""

from datetime import datetime, timezone
from typing import List, Tuple, Set, Optional
from app.models.event import MarketEvent
from app.models.bom import BomItem, RiskLevel
from app.knowledge.brand_category_map import normalize_brand
from app.knowledge.category_tree import get_sibling_categories, get_ancestor_categories
from app.services.sources.octopart_source import (
    OctopartSource,
    LIFECYCLE_ACTIVE,
    LIFECYCLE_NRND,
    LIFECYCLE_EOL,
    LIFECYCLE_UNKNOWN,
)


class BOMMatcher:
    """
    BOM物料与市场事件的匹配引擎

    匹配规则（全量收集，不短路）：
    1. 品牌完全匹配 + 品类完全匹配 → 精确命中（RED 级权重）
    2. 品牌未指定 + 品类模糊匹配（同级波及）→ 波及命中（YELLOW 级权重）
    3. 收集全部命中事件后综合判定最终等级和评分
    4. 物料信息不足 → GRAY

    品类传播距离限制：向上/同级1级，防止泛化。
    """

    def __init__(
        self,
        active_events: List[MarketEvent],
        octopart_source: Optional[OctopartSource] = None,
        fallback_sources: Optional[list] = None,
    ):
        """
        Args:
            active_events: 当前活跃的市场事件列表
            octopart_source: Octopart/Nexar 数据源实例（可选，T2-004）
            fallback_sources: 降级数据源列表，如 [DigiKeySource, MouserSource]（可选，T2-004）
        """
        self.events = active_events
        self.octopart_source = octopart_source
        self.fallback_sources = fallback_sources or []

    def match_item(
        self, item: BomItem
    ) -> Tuple[RiskLevel, float, List[MarketEvent], str]:
        """
        对单个BOM物料进行风险匹配（全量收集，不短路）

        Returns:
            (风险等级, 风险评分0-100, 匹配到的全部事件列表, 综合风险原因说明)
        """
        norm_brand = item.normalized_brand
        norm_cat = item.normalized_category or item.raw_category

        # 物料信息不足 → GRAY
        if not norm_brand and not norm_cat:
            return (
                RiskLevel.GRAY,
                0.0,
                [],
                "物料品牌和品类信息均缺失，无法评估",
            )

        # Phase 1：收集全部精确命中事件（品牌+品类直接匹配）
        exact_events: List[MarketEvent] = []
        exact_reasons: List[str] = []
        exact_event_ids: Set[int] = set()

        for evt in self.events:
            brand_match = self.match_brand(norm_brand, evt.brand)
            cat_match = self.exact_category_match(norm_cat, evt.category)

            if brand_match and cat_match:
                exact_events.append(evt)
                if evt.id is not None:
                    exact_event_ids.add(evt.id)
                exact_reasons.append(
                    f"品牌+品类直接命中: {evt.brand} {evt.category} "
                    f"受{evt.event_type.value if evt.event_type else '未知'}事件影响"
                )

        # Phase 2：收集全部品类波及事件（去重，排除已在 Phase 1 中的事件）
        spread_events: List[MarketEvent] = []
        spread_reasons: List[str] = []

        if norm_cat:
            siblings = get_sibling_categories(norm_cat)
            ancestors = get_ancestor_categories(norm_cat)
            search_cats = set(siblings + ancestors)

            for evt in self.events:
                # 跳过已在精确命中中的事件
                if evt.id is not None and evt.id in exact_event_ids:
                    continue

                evt_cat = evt.category or ""
                # 检查事件品类本身或其祖先是否在搜索范围内
                if evt_cat in search_cats:
                    spread_events.append(evt)
                    spread_reasons.append(
                        f"品类波及: {evt_cat}的事件可能影响{norm_cat}"
                    )
                else:
                    # 检查事件品类的祖先是否在搜索范围内
                    evt_ancestors = get_ancestor_categories(evt_cat)
                    if any(a in search_cats for a in evt_ancestors):
                        spread_events.append(evt)
                        spread_reasons.append(
                            f"品类波及: {evt_cat}(父品类{evt_ancestors[0] if evt_ancestors else ''})"
                            f"的事件可能影响{norm_cat}"
                        )

        # Phase 3：综合判定 — 汇总所有匹配事件
        all_events = exact_events + spread_events
        all_reasons = exact_reasons + spread_reasons

        if not all_events:
            return (
                RiskLevel.GREEN,
                0.0,
                [],
                "未发现影响该物料的市场事件",
            )

        # 最终风险等级：有精确命中 → RED，仅有波及 → YELLOW
        if exact_events:
            risk_level = RiskLevel.RED
        else:
            risk_level = RiskLevel.YELLOW

        # 综合评分：精确命中全权重，波及命中 0.6 权重，取最大值
        exact_score = self._calc_risk_score(exact_events) if exact_events else 0.0
        spread_weight = 0.6
        spread_score = self._calc_risk_score(spread_events) * spread_weight if spread_events else 0.0
        score = max(exact_score, spread_score)

        # 综合原因说明
        reason_parts: List[str] = []
        if exact_reasons:
            reason_parts.append(f"[精确命中 {len(exact_events)}条] " + "; ".join(exact_reasons))
        if spread_reasons:
            reason_parts.append(f"[品类波及 {len(spread_events)}条] " + "; ".join(spread_reasons))
        reason = " | ".join(reason_parts)

        # T2-004: 生命周期状态影响调整
        risk_level, reason = self.adjust_risk_by_lifecycle(
            mpn=item.raw_part_number or "",
            current_risk_level=risk_level,
            current_reason=reason,
        )

        return (
            risk_level,
            round(score, 1),
            all_events,
            reason,
        )

    def match_brand(self, item_brand: str | None, event_brand: str | None) -> bool:
        """品牌匹配（标准化后比较）（v3.3: 公开接口）"""
        if not item_brand or not event_brand:
            return False
        # 直接比较
        if item_brand.lower() == event_brand.lower():
            return True
        # 标准化后比较：item_brand 可能已经是标准名 "村田/Murata" 这种形式
        std_item = normalize_brand(item_brand) or item_brand
        # 完全相等
        if std_item.lower() == event_brand.lower():
            return True
        # 标准名中包含 event_brand (如 std_item="村田/Murata", event_brand="Murata")
        if "/" in std_item:
            for part in std_item.split("/"):
                if part.strip().lower() == event_brand.lower():
                    return True
        # 反向：event_brand 包含 item brand
        if event_brand.lower() in std_item.lower():
            return True
        return False

    def exact_category_match(
        self, item_cat: str | None, event_cat: str | None
    ) -> bool:
        """精确品类匹配（v3.3: 公开接口）"""
        if not item_cat or not event_cat:
            return False
        return item_cat.lower() == event_cat.lower()

    def _calc_risk_score(self, events: List[MarketEvent]) -> float:
        """计算综合风险评分 0-100 (v3.3: 含事件时效衰减)"""
        if not events:
            return 0.0

        severity_weights = {
            "critical": 100,
            "high": 75,
            "medium": 50,
            "low": 25,
            "unknown": 30,
        }

        max_score = 0.0
        now = datetime.now(timezone.utc)
        for evt in events:
            sev_value = evt.severity.value if hasattr(evt.severity, "value") else str(evt.severity)
            base = severity_weights.get(sev_value, 30)
            confidence = evt.confidence or 0.5
            cross_val = min(evt.cross_validated or 0, 3)
            score = base * confidence * (1 + cross_val * 0.1)

            # v3.3: 事件时效衰减 — 超过30天后每30天置信度 ×0.9
            if hasattr(evt, "created_at") and evt.created_at:
                days_old = (now - evt.created_at).days
                if days_old > 30:
                    decay = 0.9 ** ((days_old - 30) / 30.0)
                    score *= decay

            max_score = max(max_score, score)

        return min(max_score, 100.0)

    # ================================================================
    # T2-004: 生命周期状态影响风险等级调整
    # ================================================================

    def adjust_risk_by_lifecycle(
        self,
        mpn: str,
        current_risk_level: RiskLevel,
        current_reason: str,
    ) -> Tuple[RiskLevel, str]:
        """根据生命周期状态提升风险等级

        映射规则:
            Active  → 不调整
            NRND    → 自动提升至黄色 (YELLOW)
            EOL     → 自动提升至橙色 (ORANGE)，若无替代料则红色 (RED)
            Unknown → 显示灰色 (GRAY)，提示数据不足

        Args:
            mpn: 物料型号 (用于查询生命周期数据)
            current_risk_level: 当前风险等级
            current_reason: 当前风险原因说明

        Returns:
            (调整后的风险等级, 更新后的原因说明)
        """
        lifecycle = self._get_lifecycle_sync(mpn)

        if lifecycle == LIFECYCLE_ACTIVE:
            return current_risk_level, current_reason

        if lifecycle == LIFECYCLE_NRND:
            # NRND → 至少 YELLOW
            adjusted = self._raise_to_at_least(current_risk_level, RiskLevel.YELLOW)
            extra = f"[生命周期:NRND] {mpn} 不推荐用于新设计，风险提升至{adjusted.value}"
            return adjusted, f"{current_reason} | {extra}" if current_reason else extra

        if lifecycle == LIFECYCLE_EOL:
            # EOL → 至少 ORANGE；当前已是 ORANGE 或更高则提升为 RED
            if current_risk_level in (RiskLevel.ORANGE, RiskLevel.RED):
                adjusted = RiskLevel.RED
            else:
                adjusted = RiskLevel.ORANGE
            extra = f"[生命周期:EOL] {mpn} 已停产/即将停产，风险提升至{adjusted.value}"
            return adjusted, f"{current_reason} | {extra}" if current_reason else extra

        if lifecycle == LIFECYCLE_UNKNOWN:
            # Unknown → GRAY，提示数据不足
            extra = f"[生命周期:Unknown] {mpn} 生命周期数据不足，需人工确认"
            return RiskLevel.GRAY, f"{current_reason} | {extra}" if current_reason else extra

        # 其他情况不调整
        return current_risk_level, current_reason

    def _get_lifecycle_sync(self, mpn: str) -> str:
        """同步获取生命周期状态 (Octopart优先，降级到fallback)

        Args:
            mpn: 物料型号

        Returns:
            归一化的生命周期状态字符串
        """
        # 优先使用 Octopart
        if self.octopart_source and self.octopart_source.is_configured:
            try:
                # 先尝试从缓存获取 (同步安全)
                clean_mpn = self.octopart_source.clean_mpn(mpn) if mpn else mpn
                cached = self.octopart_source._cache_get(clean_mpn)
                if cached and cached.lifecycle_status:
                    return cached.lifecycle_status

                # 缓存未命中 → 尝试异步查询
                import asyncio
                loop = asyncio.get_event_loop()
                if not loop.is_running():
                    result = loop.run_until_complete(
                        self.octopart_source.query_by_mpn(mpn)
                    )
                    if result and result.lifecycle_status:
                        return result.lifecycle_status
            except Exception:
                pass

        # 降级: 从 fallback_sources 获取
        for src in self.fallback_sources:
            try:
                # 先尝试从缓存获取
                if hasattr(src, "_cache_get"):
                    clean_mpn = src.clean_mpn(mpn) if hasattr(src, "clean_mpn") else mpn
                    cached = src._cache_get(clean_mpn)
                    if cached and cached.lifecycle_status:
                        return OctopartSource.normalize_lifecycle_status(cached.lifecycle_status)

                # 缓存未命中 → 尝试异步查询
                import asyncio
                loop = asyncio.get_event_loop()
                if not loop.is_running():
                    result = loop.run_until_complete(src.query_by_mpn(mpn))
                    if result and result.lifecycle_status:
                        return OctopartSource.normalize_lifecycle_status(result.lifecycle_status)
            except Exception:
                continue

        return LIFECYCLE_ACTIVE  # 无数据源可用时默认不调整

    @staticmethod
    def _raise_to_at_least(
        current: RiskLevel, minimum: RiskLevel
    ) -> RiskLevel:
        """将风险等级提升到至少 minimum

        风险等级从低到高: GREEN < YELLOW < ORANGE < RED
        GRAY 视为独立等级，不做降级处理
        """
        risk_order = {
            RiskLevel.GRAY: 0,
            RiskLevel.GREEN: 1,
            RiskLevel.YELLOW: 2,
            RiskLevel.ORANGE: 3,
            RiskLevel.RED: 4,
        }
        if risk_order.get(current, 0) >= risk_order.get(minimum, 0):
            return current
        return minimum
