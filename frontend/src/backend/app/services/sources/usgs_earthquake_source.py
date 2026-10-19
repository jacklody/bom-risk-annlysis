"""USGS 地震数据源 — 接入 United States Geological Survey 实时地震 API。

数据来源：https://earthquake.usgs.gov/fdsnws/event/1/query
完全免费、无需 API Key。

采集逻辑：
- 定时 2 小时
- 震级 >= 5.0
- 特别关注区域（权重加倍）：台湾、日本九州/东北、韩国、马来西亚、四川
- 与半导体工厂匹配：<=200km 直接影响，200-500km 间接影响
- 事件类型: RiskEvent/earthquake
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# 半导体工厂坐标数据库
# 数据来源：公开资料整理的全球主要半导体晶圆厂/封测厂坐标
# ═══════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class SemiconductorFab:
    """半导体工厂信息。

    Attributes:
        fab_id: 工厂唯一标识
        company: 公司名称
        fab_name: 工厂名称
        city: 所在城市
        country: 所在国家
        latitude: 纬度
        longitude: 经度
        process_type: 工艺类型（如 Logic / DRAM / NAND / Analog）
        capacity_tier: 产能等级（tier1 = 全球前10, tier2 = 区域重要）
    """
    fab_id: str
    company: str
    fab_name: str
    city: str
    country: str
    latitude: float
    longitude: float
    process_type: str = ""
    capacity_tier: str = "tier2"


# 主要半导体工厂坐标数据库（至少 15 个关键工厂）
SEMICONDUCTOR_FAB_DATABASE: List[SemiconductorFab] = [
    # ── 台积电 (TSMC) ──
    SemiconductorFab(
        fab_id="TSMC_FAB12", company="TSMC", fab_name="Fab 12",
        city="台中", country="台湾",
        latitude=24.7856, longitude=121.0044,
        process_type="Logic/Advanced", capacity_tier="tier1",
    ),
    SemiconductorFab(
        fab_id="TSMC_FAB14", company="TSMC", fab_name="Fab 14 (南科)",
        city="台南 (南科)", country="台湾",
        latitude=23.1089, longitude=120.3916,
        process_type="Logic/Advanced", capacity_tier="tier1",
    ),
    SemiconductorFab(
        fab_id="TSMC_FAB15", company="TSMC", fab_name="Fab 15",
        city="台中", country="台湾",
        latitude=24.2285, longitude=120.6831,
        process_type="Logic", capacity_tier="tier1",
    ),
    SemiconductorFab(
        fab_id="TSMC_FAB18", company="TSMC", fab_name="Fab 18 (南科P3)",
        city="台南 (南科)", country="台湾",
        latitude=23.1120, longitude=120.3850,
        process_type="Advanced 5nm/3nm", capacity_tier="tier1",
    ),
    SemiconductorFab(
        fab_id="TSMC_FAB1", company="TSMC", fab_name="Fab 1",
        city="新竹", country="台湾",
        latitude=24.7980, longitude=120.9800,
        process_type="Legacy", capacity_tier="tier2",
    ),
    # ── 瑞萨 (Renesas) ──
    SemiconductorFab(
        fab_id="RENESAS_NAKA", company="Renesas", fab_name="那珂工厂",
        city="那珂", country="日本",
        latitude=36.4586, longitude=140.4553,
        process_type="MCU/Analog", capacity_tier="tier1",
    ),
    SemiconductorFab(
        fab_id="RENESAS_KAWAJIRI", company="Renesas", fab_name="川尻工厂",
        city="茨城", country="日本",
        latitude=36.1850, longitude=140.1830,
        process_type="Analog/Power", capacity_tier="tier2",
    ),
    SemiconductorFab(
        fab_id="RENESAS_KOFU", company="Renesas", fab_name="甲府工厂",
        city="甲府", country="日本",
        latitude=35.6838, longitude=138.5675,
        process_type="MCU", capacity_tier="tier2",
    ),
    # ── 索尼 (Sony) ──
    SemiconductorFab(
        fab_id="SONY_KUMAMOTO", company="Sony", fab_name="熊本图像传感器工厂",
        city="熊本", country="日本",
        latitude=32.7907, longitude=130.7066,
        process_type="CMOS Image Sensor", capacity_tier="tier1",
    ),
    SemiconductorFab(
        fab_id="SONY_NAGASAKI", company="Sony", fab_name="长崎工厂",
        city="的早", country="日本",
        latitude=32.9500, longitude=129.7500,
        process_type="CMOS Image Sensor", capacity_tier="tier2",
    ),
    # ── 三星 (Samsung) ──
    SemiconductorFab(
        fab_id="SAMSUNG_PYEONGTAEK", company="Samsung", fab_name="平泽 P1/P2/P3",
        city="平泽", country="韩国",
        latitude=37.0350, longitude=127.0370,
        process_type="DRAM/NAND/Logic", capacity_tier="tier1",
    ),
    SemiconductorFab(
        fab_id="SAMSUNG_HWASEONG", company="Samsung", fab_name="华城工厂",
        city="华城", country="韩国",
        latitude=37.1970, longitude=127.0130,
        process_type="DRAM/Logic", capacity_tier="tier1",
    ),
    # ── SK 海力士 (SK Hynix) ──
    SemiconductorFab(
        fab_id="SKHYNIX_ICHEON", company="SK Hynix", fab_name="利川 M9",
        city="利川", country="韩国",
        latitude=37.2730, longitude=127.4050,
        process_type="DRAM", capacity_tier="tier1",
    ),
    SemiconductorFab(
        fab_id="SKHYNIX_CHEONGJU", company="SK Hynix", fab_name="清州 M12",
        city="清州", country="韩国",
        latitude=36.6420, longitude=127.4880,
        process_type="NAND Flash", capacity_tier="tier1",
    ),
    # ── 英飞凌 (Infineon) ──
    SemiconductorFab(
        fab_id="INFINEON_DRESDEN", company="Infineon", fab_name="德累斯顿工厂",
        city="德累斯顿", country="德国",
        latitude=51.0504, longitude=13.7373,
        process_type="Power/Automotive", capacity_tier="tier1",
    ),
    # ── 格芯 (GlobalFoundries) ──
    SemiconductorFab(
        fab_id="GF_DRESDEN", company="GlobalFoundries", fab_name="Fab 1 Dresden",
        city="德累斯顿", country="德国",
        latitude=51.0880, longitude=13.7130,
        process_type="Logic/Specialty", capacity_tier="tier2",
    ),
    SemiconductorFab(
        fab_id="GF_SINGAPORE", company="GlobalFoundries", fab_name="新加坡 Fab 7",
        city="新加坡", country="新加坡",
        latitude=1.3417, longitude=103.9610,
        process_type="Specialty/FD-SOI", capacity_tier="tier2",
    ),
    # ── 联华电子 (UMC) ──
    SemiconductorFab(
        fab_id="UMC_FAB12A", company="UMC", fab_name="Fab 12A (南科)",
        city="台南 (南科)", country="台湾",
        latitude=23.1050, longitude=120.3950,
        process_type="Logic", capacity_tier="tier2",
    ),
    # ── 力积电 (PSMC) ──
    SemiconductorFab(
        fab_id="PSMC_P3", company="PSMC (力积电)", fab_name="P3 铜锣厂",
        city="铜锣", country="台湾",
        latitude=24.5150, longitude=120.8250,
        process_type="DRAM/Logic", capacity_tier="tier2",
    ),
    # ── 德州仪器 (TI) ──
    SemiconductorFab(
        fab_id="TI_SHERMAN", company="Texas Instruments", fab_name="Sherman Fab (LFAT)",
        city="Sherman, TX", country="美国",
        latitude=33.6360, longitude=-96.6100,
        process_type="Analog", capacity_tier="tier1",
    ),
    # ── 村田 (Murata) ──
    SemiconductorFab(
        fab_id="MURATA_IZUMIO", company="Murata", fab_name="和泉工厂",
        city="和泉", country="日本",
        latitude=34.5230, longitude=135.4180,
        process_type="MLCC/Capacitor", capacity_tier="tier2",
    ),
    # ── 铠侠 (Kioxia, 原 Toshiba Memory) ──
    SemiconductorFab(
        fab_id="KIOXIA_YOKKAICHI", company="Kioxia", fab_name="四日市工厂",
        city="四日市", country="日本",
        latitude=34.7700, longitude=136.6200,
        process_type="NAND Flash", capacity_tier="tier1",
    ),
    SemiconductorFab(
        fab_id="KIOXIA_KITAKAMI", company="Kioxia", fab_name="北上市工厂",
        city="北上", country="日本",
        latitude=39.2800, longitude=141.1400,
        process_type="NAND Flash", capacity_tier="tier1",
    ),
    # ── 美光 (Micron) ──
    SemiconductorFab(
        fab_id="MICRON_MANASSAS", company="Micron", fab_name="Manassas Fab",
        city="Manassas, VA", country="美国",
        latitude=38.7500, longitude=-77.4750,
        process_type="DRAM", capacity_tier="tier2",
    ),
    SemiconductorFab(
        fab_id="MICRON_HIROSHIMA", company="Micron", fab_name="广岛工厂",
        city="广岛", country="日本",
        latitude=34.3850, longitude=132.4630,
        process_type="DRAM", capacity_tier="tier1",
    ),
]


# ── 特别关注区域 ──
@dataclass(frozen=True)
class PriorityRegion:
    """优先关注区域。

    Attributes:
        name: 区域名称
        latitude: 中心纬度
        longitude: 中心经度
        radius_km: 关注半径（km）
        weight: 权重乘数
    """
    name: str
    latitude: float
    longitude: float
    radius_km: float = 500.0
    weight: float = 2.0


PRIORITY_REGIONS: List[PriorityRegion] = [
    PriorityRegion(name="台湾", latitude=23.7, longitude=121.0, radius_km=400, weight=2.0),
    PriorityRegion(name="日本九州", latitude=32.8, longitude=130.7, radius_km=500, weight=2.0),
    PriorityRegion(name="日本东北", latitude=38.3, longitude=140.9, radius_km=500, weight=2.0),
    PriorityRegion(name="韩国", latitude=37.0, longitude=127.0, radius_km=300, weight=2.0),
    PriorityRegion(name="马来西亚", latitude=5.3, longitude=100.3, radius_km=400, weight=2.0),
    PriorityRegion(name="四川", latitude=30.6, longitude=104.1, radius_km=500, weight=2.0),
]


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """使用 Haversine 公式计算两点间的地球表面距离。

    Args:
        lat1: 点 1 纬度
        lon1: 点 1 经度
        lat2: 点 2 纬度
        lon2: 点 2 经度

    Returns:
        两点间距离（千米）
    """
    R = 6371.0  # 地球平均半径 km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


@dataclass
class FabImpact:
    """工厂受影响评估。

    Attributes:
        fab: 工厂信息
        distance_km: 与震中距离
        impact_level: 影响等级（direct / indirect / none）
    """
    fab: SemiconductorFab
    distance_km: float
    impact_level: str  # "direct" / "indirect" / "none"


class UsgsEarthquakeSource:
    """USGS 地震数据源采集器。

    Attributes:
        _endpoint: USGS API 端点
        _timeout: HTTP 请求超时时间
        _max_retries: 最大重试次数
        _fab_db: 半导体工厂数据库
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        fab_db: Optional[List[SemiconductorFab]] = None,
    ) -> None:
        """初始化 USGS 地震数据源。

        Args:
            endpoint: USGS API 端点 URL，默认从配置读取
            timeout: HTTP 请求超时（秒），默认从配置读取
            max_retries: 最大重试次数，默认从配置读取
            fab_db: 半导体工厂数据库，默认使用内置数据库
        """
        self._endpoint = endpoint or settings.usgs_api_endpoint
        self._timeout = timeout or settings.usgs_request_timeout
        self._max_retries = max_retries if max_retries is not None else settings.usgs_max_retries
        self._fab_db = fab_db if fab_db is not None else list(SEMICONDUCTOR_FAB_DATABASE)

    @property
    def source_name(self) -> str:
        """数据源标识名称。"""
        return "usgs"

    @property
    def fab_count(self) -> int:
        """半导体工厂数据库数量。"""
        return len(self._fab_db)

    async def health_check(self) -> bool:
        """检查 USGS API 是否可用。

        Returns:
            bool: API 可用返回 True，否则返回 False
        """
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    self._endpoint,
                    params={
                        "format": "geojson",
                        "minmagnitude": "1",
                        "limit": "1",
                    },
                )
                return resp.status_code == 200
        except Exception as e:
            logger.warning(f"USGS health check failed: {e}")
            return False

    async def fetch_earthquakes(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """从 USGS 获取地震数据。

        Args:
            start_time: 起始时间，默认 2h 前
            end_time: 结束时间，默认当前时间

        Returns:
            标准化地震事件列表，每个事件包含：
            - earthquake_id: USGS 事件 ID
            - magnitude: 震级
            - depth_km: 震源深度
            - latitude: 震中纬度
            - longitude: 震中经度
            - location: 位置描述
            - time: 发生时间
            - place: 地点文字描述
            - felt_reports: 有感报告数
            - tsunami: 是否海啸预警
            - alert: USGS alert 级别
            - affected_fabs: 受影响的半导体工厂列表
            - priority_weight: 区域权重
            - raw_data: 原始 GeoJSON Feature
        """
        now = datetime.now(timezone.utc)
        if end_time is None:
            end_time = now
        if start_time is None:
            start_time = end_time - timedelta(hours=settings.usgs_collect_interval_hours)

        params = {
            "format": "geojson",
            "minmagnitude": str(settings.usgs_min_magnitude),
            "starttime": start_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "endtime": end_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "orderby": "time",
        }

        raw_events = []
        for attempt in range(1, self._max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.get(self._endpoint, params=params)
                    resp.raise_for_status()
                    data = resp.json()

                    features = data.get("features", [])
                    raw_events = [self._parse_earthquake(f) for f in features if f]
                    break

            except httpx.HTTPStatusError as e:
                logger.warning(
                    f"USGS HTTP error (attempt {attempt}/{self._max_retries}): "
                    f"{e.response.status_code}"
                )
                if attempt == self._max_retries:
                    logger.error(f"USGS API permanently failed after {self._max_retries} retries")
                    return []
            except httpx.RequestError as e:
                logger.warning(
                    f"USGS request error (attempt {attempt}/{self._max_retries}): {e}"
                )
                if attempt == self._max_retries:
                    logger.error(f"USGS API unreachable after {self._max_retries} retries")
                    return []
            except Exception as e:
                logger.warning(f"USGS unexpected error (attempt {attempt}): {e}")
                if attempt == self._max_retries:
                    return []

        # 为每个地震匹配受影响的半导体工厂
        for evt in raw_events:
            evt["affected_fabs"] = self.match_affected_fabs(
                evt["latitude"], evt["longitude"]
            )
            evt["priority_weight"] = self._calculate_priority_weight(
                evt["latitude"], evt["longitude"]
            )

        logger.info(
            f"USGS: fetched {len(raw_events)} earthquakes "
            f"M>={settings.usgs_min_magnitude} in last "
            f"{settings.usgs_collect_interval_hours}h"
        )
        return raw_events

    def _parse_earthquake(self, feature: Dict[str, Any]) -> Dict[str, Any]:
        """解析 USGS GeoJSON Feature 为标准地震事件格式。

        Args:
            feature: GeoJSON Feature 对象

        Returns:
            标准化地震事件字典
        """
        geometry = feature.get("geometry", {})
        coordinates = geometry.get("coordinates", [0, 0, 0])
        properties = feature.get("properties", {})

        longitude = coordinates[0] if len(coordinates) > 0 else 0.0
        latitude = coordinates[1] if len(coordinates) > 1 else 0.0
        depth_km = coordinates[2] if len(coordinates) > 2 else 0.0

        # 时间戳转换（USGS 使用毫秒时间戳）
        time_ms = properties.get("time", 0)
        event_time = None
        if time_ms:
            try:
                event_time = datetime.fromtimestamp(time_ms / 1000, tz=timezone.utc)
            except (ValueError, OSError, OverflowError):
                event_time = None

        earthquake_id = feature.get("id", "")

        return {
            "earthquake_id": earthquake_id,
            "magnitude": properties.get("mag", 0.0),
            "depth_km": depth_km,
            "latitude": float(latitude),
            "longitude": float(longitude),
            "location": properties.get("place", "Unknown"),
            "time": event_time,
            "place": properties.get("place", ""),
            "felt_reports": properties.get("felt", 0),
            "tsunami": properties.get("tsunami", 0),
            "alert": properties.get("alert", None),  # green/yellow/orange/red
            "status": properties.get("status", ""),
            "updated": properties.get("updated", 0),
            "url": properties.get("url", ""),
            "raw_data": feature,
        }

    def match_affected_fabs(
        self,
        epicenter_lat: float,
        epicenter_lon: float,
    ) -> List[FabImpact]:
        """匹配震中附近的半导体工厂。

        影响范围：
        - <= 200km: 直接影响 (direct)
        - 200-500km: 间接影响 (indirect)
        - > 500km: 不受影响

        Args:
            epicenter_lat: 震中纬度
            epicenter_lon: 震中经度

        Returns:
            受影响的工厂列表（含距离和影响等级），按距离升序排列
        """
        direct_km = settings.usgs_direct_impact_km
        indirect_km = settings.usgs_indirect_impact_km
        impacts: List[FabImpact] = []

        for fab in self._fab_db:
            dist = haversine_distance_km(
                epicenter_lat, epicenter_lon,
                fab.latitude, fab.longitude,
            )

            if dist <= direct_km:
                impacts.append(FabImpact(fab=fab, distance_km=dist, impact_level="direct"))
            elif dist <= indirect_km:
                impacts.append(FabImpact(fab=fab, distance_km=dist, impact_level="indirect"))

        # 按距离升序排列
        impacts.sort(key=lambda x: x.distance_km)
        return impacts

    def _calculate_priority_weight(
        self,
        lat: float,
        lon: float,
    ) -> float:
        """计算地震的区域优先级权重。

        在特别关注区域内的地震权重加倍。

        Args:
            lat: 地震纬度
            lon: 地震经度

        Returns:
            权重乘数（1.0 为普通区域，2.0 为关注区域）
        """
        for region in PRIORITY_REGIONS:
            dist = haversine_distance_km(lat, lon, region.latitude, region.longitude)
            if dist <= region.radius_km:
                return region.weight
        return 1.0

    def to_market_event_data(self, earthquake: Dict[str, Any]) -> Dict[str, Any]:
        """将 USGS 地震事件转换为 MarketEvent 数据字典。

        Args:
            earthquake: 标准化地震事件字典

        Returns:
            可直接用于 MarketEvent 入库的数据字典
        """
        mag = earthquake["magnitude"]
        depth = earthquake["depth_km"]
        place = earthquake["place"] or earthquake["location"] or "Unknown"
        affected_fabs = earthquake.get("affected_fabs", [])

        direct_fabs = [f for f in affected_fabs if f.impact_level == "direct"]
        indirect_fabs = [f for f in affected_fabs if f.impact_level == "indirect"]
        weight = earthquake.get("priority_weight", 1.0)

        # 严重度判断
        if direct_fabs:
            severity = "critical" if mag >= 6.0 else "high"
        elif indirect_fabs:
            severity = "high" if mag >= 6.0 else "medium"
        else:
            severity = "medium" if mag >= 6.0 else "low"

        # 权重提升严重度
        if weight >= 2.0 and severity == "medium":
            severity = "high"

        # 构建标题
        fab_info = ""
        if direct_fabs:
            fab_names = ", ".join(f.fab.fab_name for f in direct_fabs[:3])
            fab_info = f" [直接影响: {fab_names}]"
        elif indirect_fabs:
            fab_names = ", ".join(f.fab.fab_name for f in indirect_fabs[:3])
            fab_info = f" [间接影响: {fab_names}]"

        title = (
            f"[USGS-地震] M{mag:.1f} {place} "
            f"深度{depth:.1f}km{fab_info}"
        )

        # 构建详细描述
        affected_text = ""
        if affected_fabs:
            lines = []
            for fi in affected_fabs[:10]:
                lines.append(
                    f"  - {fi.fab.company} {fi.fab.fab_name} "
                    f"({fi.fab.city}, {fi.fab.country}): "
                    f"{fi.distance_km:.0f}km [{fi.impact_level}]"
                )
            affected_text = "受影响半导体工厂:\n" + "\n".join(lines)

        raw_text = (
            f"USGS 地震监测\n"
            f"震级: M{mag:.1f}\n"
            f"深度: {depth:.1f} km\n"
            f"位置: {place}\n"
            f"坐标: {earthquake['latitude']:.4f}N, {earthquake['longitude']:.4f}E\n"
            f"区域权重: {weight:.1f}x\n"
            f"海啸预警: {'是' if earthquake.get('tsunami') else '否'}\n"
        )
        if affected_text:
            raw_text += affected_text + "\n"
        if earthquake.get("url"):
            raw_text += f"详情: {earthquake['url']}\n"

        # 影响估算
        if direct_fabs:
            lead_weeks = 4 if mag >= 6.0 else 2
            price_pct = 20.0 if mag >= 6.0 else 10.0
        elif indirect_fabs:
            lead_weeks = 2 if mag >= 6.0 else 1
            price_pct = 10.0 if mag >= 6.0 else 5.0
        else:
            lead_weeks = 1
            price_pct = 2.0

        # 置信度
        base_confidence = 0.85
        if direct_fabs:
            confidence = 0.95
        elif indirect_fabs:
            confidence = 0.85
        else:
            confidence = 0.7

        return {
            "source_name": self.source_name,
            "source_url": earthquake.get("url", ""),
            "raw_title": title[:512],
            "raw_text": raw_text,
            "brand": None,
            "category": "地震",
            "event_type": "disaster",
            "severity": severity,
            "confidence": confidence,
            "estimated_lead_time_impact_weeks": lead_weeks,
            "estimated_price_impact_pct": price_pct,
            "cross_validated": 1,
            "duration_start": earthquake.get("time"),
        }
