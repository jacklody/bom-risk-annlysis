"""原材料价格追踪器 — 30日/90日历史基线 + 三档阈值判定。

为每个材料独立追踪价格变动，计算当前价格与历史基线的百分比变化，
按 5%/10%/20% 三档阈值判定风险等级。

Usage:
    tracker = MaterialTracker(db_session, price_service)
    results = await tracker.track_materials(["cu_cathode", "al_ingot"])
    # results["cu_cathode"].risk_level -> "ORANGE"
"""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge.material_mapping import (
    get_material_entry,
    get_adjusted_cost_ratio,
    RARE_EARTH_AMPLIFIER,
)
from app.models.material_price import MaterialPrice

logger = logging.getLogger(__name__)

# ── 阈值配置 ──────────────────────────────────────────────

PRICE_CHANGE_YELLOW = 5.0    # 涨幅 ≥5% 触发 YELLOW
PRICE_CHANGE_ORANGE = 10.0   # 涨幅 ≥10% 触发 ORANGE
PRICE_CHANGE_RED = 20.0      # 涨幅 ≥20% 触发 RED
PRICE_DROP_GREEN = -10.0     # 跌幅 ≥10% 触发 GREEN (采购窗口)

RISK_SCORE_MAP = {
    "RED": 35,
    "ORANGE": 20,
    "YELLOW": 10,
    "GREEN": -15,
    "NORMAL": 0,
}


# ── 追踪结果 ──────────────────────────────────────────────

@dataclass
class MaterialTracking:
    """单个材料的追踪结果。"""

    material_key: str
    material_name_zh: str = ""
    domain: str = ""
    risk_level: str = "NORMAL"          # RED/ORANGE/YELLOW/GREEN/NORMAL
    current_price: Optional[float] = None
    price_unit: str = "元/吨"
    baseline_30d: Optional[float] = None
    baseline_90d: Optional[float] = None
    change_pct: float = 0.0              # 当前价格 vs 30日基线的百分比变化
    adjusted_cost_ratio: float = 0.0     # 调整后的传导系数 (含稀土放大+加工溢价)
    material_track_score: float = 0.0    # 双轨引擎 material_track 加分
    source_name: str = ""
    degraded: bool = False               # 是否使用了降级/过期数据
    affected_categories: List[str] = field(default_factory=list)

    @property
    def has_alert(self) -> bool:
        return self.risk_level in ("RED", "ORANGE", "YELLOW", "GREEN")


# ── 追踪器 ────────────────────────────────────────────────

class MaterialTracker:
    """原材料价格追踪器。

    核心功能:
    1. 查询每个材料过去 30 日和 90 日的价格记录
    2. 计算 30 日均价作为短期基线
    3. 最新价格 vs 30 日基线计算百分比变化
    4. 按三档阈值判定风险等级
    5. 稀土材料自动应用 1.6× 传导系数放大器
    """

    def __init__(self, db: AsyncSession, price_service=None):
        self._db = db
        self._price_service = price_service

    async def track_materials(
        self,
        material_keys: List[str],
        force_refresh: bool = False,
    ) -> Dict[str, MaterialTracking]:
        """追踪指定材料的价格变动。

        Args:
            material_keys: 要追踪的材料 key 列表
            force_refresh: 是否强制刷新价格（忽略缓存）

        Returns:
            {material_key: MaterialTracking} 字典
        """
        # Step 1: 获取最新价格
        current_prices: Dict[str, Optional[float]] = {}
        if self._price_service:
            current_prices = await self._price_service.get_prices(
                material_keys, force_refresh=force_refresh
            )
        else:
            current_prices = {k: None for k in material_keys}

        # Step 2: 查询历史基线
        # 使用 30 日窗口的数据来计算稳定基线（排除当日刚采集的数据点）
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        ninety_days_ago = datetime.now(timezone.utc) - timedelta(days=90)

        baselines_30d = await self._calculate_baselines(material_keys, thirty_days_ago)
        baselines_90d = await self._calculate_baselines(material_keys, ninety_days_ago)

        # Step 3: 为每个材料计算追踪结果
        results: Dict[str, MaterialTracking] = {}
        from app.knowledge.material_mapping import get_categories_for_material

        for mk in material_keys:
            entry = get_material_entry(mk)
            if not entry:
                continue

            current = current_prices.get(mk)
            bl30 = baselines_30d.get(mk)
            bl90 = baselines_90d.get(mk)

            # 计算百分比变化
            change_pct = self._calc_change_pct(current, bl30)

            # 判定风险等级
            risk_level = self._determine_risk_level(change_pct)

            # 计算传导分数
            adjusted_ratio = get_adjusted_cost_ratio(entry)
            material_score = change_pct * adjusted_ratio

            tracking = MaterialTracking(
                material_key=mk,
                material_name_zh=entry.name_zh,
                domain=entry.domain,
                risk_level=risk_level,
                current_price=current,
                price_unit=entry.unit,
                baseline_30d=bl30,
                baseline_90d=bl90,
                change_pct=round(change_pct, 2),
                adjusted_cost_ratio=round(adjusted_ratio, 4),
                material_track_score=round(material_score, 2),
                source_name=entry.primary_source,
                degraded=False,
                affected_categories=get_categories_for_material(mk),
            )
            results[mk] = tracking

        return results

    async def track_for_category(self, category: str) -> Dict[str, MaterialTracking]:
        """追踪指定品类的全部关联材料。"""
        from app.knowledge.material_mapping import get_materials_for_category
        materials = get_materials_for_category(category)
        keys = [m.key for m in materials]
        return await self.track_materials(keys)

    async def get_alert_signals(
        self, category: str
    ) -> Dict[str, float]:
        """获取品类级别材料预警信号，供双轨引擎使用。

        返回信号格式:
            {material_key: material_track_score}  # 仅返回 >0 的非 NORMAL 材料
        """
        results = await self.track_for_category(category)
        signals: Dict[str, float] = {}
        for mk, tracking in results.items():
            if tracking.risk_level != "NORMAL" and tracking.material_track_score != 0:
                signals[f"{mk}_score"] = tracking.material_track_score
                signals[f"{mk}_risk"] = 0  # 占位，保持接口兼容
        return signals

    # ── 内部方法 ──────────────────────────────────────────

    async def _calculate_baselines(
        self, material_keys: List[str], since: datetime
    ) -> Dict[str, Optional[float]]:
        """计算指定时间窗口内的均价基线。"""
        if not material_keys:
            return {}

        # 批量查询
        stmt = (
            select(
                MaterialPrice.material_key,
                func.avg(MaterialPrice.price_value).label("avg_price"),
            )
            .where(
                MaterialPrice.material_key.in_(material_keys),
                MaterialPrice.fetch_timestamp >= since,
            )
            .group_by(MaterialPrice.material_key)
        )

        execute_result = self._db.execute(stmt)
        result = await execute_result if inspect.isawaitable(execute_result) else execute_result
        rows = result.all()

        baselines: Dict[str, Optional[float]] = {}
        found_keys = set()
        for mk, avg_price in rows:
            baselines[mk] = round(float(avg_price), 2)
            found_keys.add(mk)

        # 未找到历史数据的 key 设为 None
        for mk in material_keys:
            if mk not in found_keys:
                baselines[mk] = None

        return baselines

    @staticmethod
    def _calc_change_pct(
        current: Optional[float], baseline: Optional[float]
    ) -> float:
        """计算当前价格相对于基线的百分比变化。"""
        if current is None or baseline is None or baseline == 0:
            return 0.0
        return ((current - baseline) / baseline) * 100.0

    @staticmethod
    def _determine_risk_level(change_pct: float) -> str:
        """按三档阈值判定风险等级。"""
        if change_pct >= PRICE_CHANGE_RED:
            return "RED"
        elif change_pct >= PRICE_CHANGE_ORANGE:
            return "ORANGE"
        elif change_pct >= PRICE_CHANGE_YELLOW:
            return "YELLOW"
        elif change_pct <= PRICE_DROP_GREEN:
            return "GREEN"
        return "NORMAL"


# ── 便捷工厂 ──────────────────────────────────────────────

async def create_material_tracker(
    db: AsyncSession, price_service=None
) -> MaterialTracker:
    """创建 MaterialTracker 实例的工厂函数。"""
    if price_service is None:
        from app.services.material_price_service import get_material_price_service
        price_service = get_material_price_service()
    return MaterialTracker(db, price_service)


# ── v4.0 数据新鲜度监控 ─────────────────────────────────────────

# 各数据源默认新鲜度阈值（小时）
SOURCE_FRESHNESS_THRESHOLDS: Dict[str, float] = {
    "smm": 24.0,
    "mysteel": 24.0,
    "lme": 48.0,
}
DEFAULT_FRESHNESS_THRESHOLD = 72.0


def get_source_threshold(source: str) -> float:
    """获取指定数据源的新鲜度阈值。"""
    source_lower = source.lower()
    for key, threshold in SOURCE_FRESHNESS_THRESHOLDS.items():
        if key in source_lower:
            return threshold
    return DEFAULT_FRESHNESS_THRESHOLD


class FreshnessMonitor:
    """数据新鲜度监控器。

    独立于 MaterialTracker 的价格追踪逻辑，专注于：
    - 追踪各数据源最后更新时间
    - 判断数据是否过期
    - 生成过期预警
    - 汇总数据源健康状态

    Usage:
        monitor = FreshnessMonitor(db_session)
        alerts = monitor.get_stale_alerts(threshold_hours=24)
    """

    def __init__(self, db):
        self._db = db

    def check_freshness(self, material_key: str) -> "FreshnessResult":
        """检查单个材料的数据新鲜度。"""
        from app.models.material_price import MaterialPrice, FreshnessResult

        now = datetime.now(timezone.utc)

        # 查询该材料最新价格记录
        stmt = (
            select(MaterialPrice)
            .where(MaterialPrice.material_key == material_key)
            .order_by(MaterialPrice.fetch_timestamp.desc())
            .limit(1)
        )

        execute_result = self._db.execute(stmt)
        if inspect.isawaitable(execute_result):
            import asyncio
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop and loop.is_running():
                # 已有运行中的循环，创建新线程执行
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    result = pool.submit(asyncio.run, execute_result).result()
            else:
                result = asyncio.run(execute_result)
        else:
            result = execute_result

        record = result.scalar_one_or_none()

        if record is None:
            return FreshnessResult(
                material_key=material_key,
                source="none",
                updated_at=None,
                hours_since_update=float("inf"),
                threshold_hours=DEFAULT_FRESHNESS_THRESHOLD,
                is_stale=True,
                severity="critical",
            )

        ts = record.fetch_timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        hours_since = (now - ts).total_seconds() / 3600.0
        threshold = get_source_threshold(record.source_name)

        if hours_since > threshold * 2:
            severity = "critical"
        elif hours_since > threshold:
            severity = "warning"
        else:
            severity = "ok"

        return FreshnessResult(
            material_key=material_key,
            source=record.source_name,
            updated_at=ts,
            hours_since_update=round(hours_since, 2),
            threshold_hours=threshold,
            is_stale=hours_since > threshold,
            severity=severity,
        )

    def get_all_freshness(self) -> List["FreshnessResult"]:
        """获取所有材料的新鲜度状态。"""
        from app.models.material_price import MaterialPrice, FreshnessResult

        now = datetime.now(timezone.utc)

        # 查询每个材料最新记录
        stmt = (
            select(
                MaterialPrice.material_key,
                MaterialPrice.source_name,
                func.max(MaterialPrice.fetch_timestamp).label("latest_ts"),
            )
            .group_by(MaterialPrice.material_key, MaterialPrice.source_name)
        )

        execute_result = self._db.execute(stmt)
        if inspect.isawaitable(execute_result):
            import asyncio
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop and loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    result = pool.submit(asyncio.run, execute_result).result()
            else:
                result = asyncio.run(execute_result)
        else:
            result = execute_result

        rows = result.all()
        results: List[FreshnessResult] = []

        for material_key, source_name, latest_ts in rows:
            if latest_ts.tzinfo is None:
                latest_ts = latest_ts.replace(tzinfo=timezone.utc)
            hours_since = (now - latest_ts).total_seconds() / 3600.0
            threshold = get_source_threshold(source_name)

            if hours_since > threshold * 2:
                severity = "critical"
            elif hours_since > threshold:
                severity = "warning"
            else:
                severity = "ok"

            results.append(FreshnessResult(
                material_key=material_key,
                source=source_name,
                updated_at=latest_ts,
                hours_since_update=round(hours_since, 2),
                threshold_hours=threshold,
                is_stale=hours_since > threshold,
                severity=severity,
            ))

        return results

    def get_stale_alerts(self, threshold_hours: float = 24.0) -> List["FreshnessAlert"]:
        """获取所有过期预警。

        Args:
            threshold_hours: 全局阈值（覆盖各数据源默认值时使用）

        Returns:
            过期预警列表
        """
        from app.models.material_price import FreshnessAlert as _FreshnessAlert

        all_freshness = self.get_all_freshness()
        alerts: List[_FreshnessAlert] = []

        for fr in all_freshness:
            # 使用各数据源自己的阈值
            source_threshold = fr.threshold_hours
            if fr.hours_since_update > source_threshold:
                if fr.hours_since_update > source_threshold * 2:
                    severity = "critical"
                else:
                    severity = "warning"
                alerts.append(_FreshnessAlert(
                    material_key=fr.material_key,
                    source=fr.source,
                    hours_since_update=fr.hours_since_update,
                    threshold_hours=source_threshold,
                    severity=severity,
                ))

        return alerts

    def update_price(self, material_key: str, price: float, source: str) -> bool:
        """手动更新材料价格记录。

        Args:
            material_key: 材料代码
            price: 价格值
            source: 数据源标识

        Returns:
            是否成功
        """
        try:
            from app.models.material_price import MaterialPrice

            new_record = MaterialPrice(
                material_key=material_key,
                price_value=price,
                price_unit="元/吨",
                source_name=source,
                fetch_timestamp=datetime.now(timezone.utc),
            )
            self._db.add(new_record)
            self._db.flush()
            return True
        except Exception as e:
            logger.warning(f"update_price failed for {material_key}: {e}")
            return False

    def get_source_health_summary(self) -> Dict[str, "SourceHealth"]:
        """汇总各数据源健康状态。"""
        from app.models.material_price import MaterialPrice, SourceHealth

        now = datetime.now(timezone.utc)
        all_freshness = self.get_all_freshness()

        # 按 source 分组
        source_groups: Dict[str, List] = {}
        for fr in all_freshness:
            source_groups.setdefault(fr.source, []).append(fr)

        health_map: Dict[str, SourceHealth] = {}
        for source, items in source_groups.items():
            fresh_count = sum(1 for i in items if not i.is_stale)
            stale_count = sum(1 for i in items if i.is_stale)
            avg_hours = (
                sum(i.hours_since_update for i in items if i.hours_since_update != float("inf"))
                / max(len([i for i in items if i.hours_since_update != float("inf")]), 1)
            )
            latest = max(
                (i.updated_at for i in items if i.updated_at is not None),
                default=None,
            )

            health_map[source] = SourceHealth(
                source=source,
                total_materials=len(items),
                fresh_count=fresh_count,
                stale_count=stale_count,
                avg_freshness_hours=round(avg_hours, 2),
                last_success_at=latest,
                degraded=stale_count == len(items) and len(items) > 0,
            )

        return health_map
