"""GDACS 自然灾害数据源 — 接入 Global Disaster Alert and Coordination System。

数据来源：https://www.gdacs.org/gdacsapi/api/events/geteventlist/search
完全免费、无需认证。

采集逻辑：
- 定时 4 小时
- 过滤 Orange/Red 级别
- 支持事件类型：earthquake / flood / cyclone / fire / drought
- 时间窗口 24h
- 降级策略：API 不可用时静默记录降级日志，不抛异常
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# GDACS 严重程度到系统 Severity 的映射
GDACS_SEVERITY_MAP: Dict[str, str] = {
    "Red": "critical",
    "Orange": "high",
    "Yellow": "medium",
    "Green": "low",
}

# GDACS 事件类型到系统描述的映射
GDACS_EVENT_TYPE_MAP: Dict[str, str] = {
    "earthquake": "地震",
    "flood": "洪水",
    "cyclone": "气旋/台风",
    "fire": "火灾/山火",
    "drought": "干旱",
}


class GdacsSource:
    """GDACS 自然灾害数据源采集器。

    Attributes:
        _base_url: GDACS API 基础 URL
        _timeout: HTTP 请求超时时间
        _max_retries: 最大重试次数
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> None:
        """初始化 GDACS 数据源。

        Args:
            base_url: GDACS API 基础 URL，默认从配置读取
            timeout: HTTP 请求超时（秒），默认从配置读取
            max_retries: 最大重试次数，默认从配置读取
        """
        self._base_url = base_url or settings.gdacs_api_base
        self._event_list_url = settings.gdacs_event_list_endpoint
        self._event_detail_url = settings.gdacs_event_detail_endpoint
        self._timeout = timeout or settings.gdacs_request_timeout
        self._max_retries = max_retries if max_retries is not None else settings.gdacs_max_retries

    @property
    def source_name(self) -> str:
        """数据源标识名称。"""
        return "gdacs"

    async def health_check(self) -> bool:
        """检查 GDACS API 是否可用。

        Returns:
            bool: API 可用返回 True，否则返回 False
        """
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    self._event_list_url,
                    params={"eventtype": "earthquake", "number": "1"},
                )
                return resp.status_code == 200
        except Exception as e:
            logger.warning(f"GDACS health check failed: {e}")
            return False

    async def fetch_events(self) -> List[Dict[str, Any]]:
        """从 GDACS 获取最新自然灾害事件。

        按照配置过滤：
        - 仅 Orange/Red 级别
        - 指定事件类型
        - 24h 时间窗口

        Returns:
            标准化事件列表，每个事件包含：
            - event_id: GDACS 事件 ID
            - event_type: 事件类型
            - severity: 严重程度（映射后）
            - name: 事件名称
            - description: 事件描述
            - latitude: 纬度
            - longitude: 经度
            - country: 受影响国家
            - start_date: 事件开始时间
            - end_date: 事件结束时间
            - gdacs_url: GDACS 详情页 URL
            - population_exposure: 暴露人口
            - raw_data: 原始数据
        """
        all_events: List[Dict[str, Any]] = []

        for event_type in settings.gdacs_event_types:
            try:
                events = await self._fetch_events_by_type(event_type)
                all_events.extend(events)
            except Exception as e:
                logger.warning(
                    f"GDACS fetch failed for type={event_type}: {e}",
                    exc_info=True,
                )

        # 过滤严重级别和时间窗口
        filtered = self._filter_events(all_events)
        logger.info(
            f"GDACS: fetched {len(all_events)} events, "
            f"filtered to {len(filtered)} after severity/time filter"
        )
        return filtered

    async def _fetch_events_by_type(self, event_type: str) -> List[Dict[str, Any]]:
        """按事件类型从 GDACS 获取事件列表。

        Args:
            event_type: 事件类型（earthquake/flood/cyclone/fire/drought）

        Returns:
            原始事件数据列表
        """
        params = {
            "eventtype": event_type,
            "number": "50",  # 获取最近 50 条
        }

        for attempt in range(1, self._max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.get(self._event_list_url, params=params)
                    resp.raise_for_status()
                    data = resp.json()

                    # GDACS 返回格式: {"response": [...], ...}
                    raw_events = data.get("response", [])
                    if not raw_events:
                        raw_events = data.get("features", [])

                    return [self._parse_raw_event(evt, event_type) for evt in raw_events if evt]

            except httpx.HTTPStatusError as e:
                logger.warning(
                    f"GDACS HTTP error for {event_type} (attempt {attempt}/{self._max_retries}): "
                    f"{e.response.status_code}"
                )
                if attempt == self._max_retries:
                    raise
            except httpx.RequestError as e:
                logger.warning(
                    f"GDACS request error for {event_type} (attempt {attempt}/{self._max_retries}): {e}"
                )
                if attempt == self._max_retries:
                    raise
            except Exception as e:
                logger.warning(
                    f"GDACS unexpected error for {event_type} (attempt {attempt}): {e}"
                )
                if attempt == self._max_retries:
                    raise

        return []

    def _parse_raw_event(self, raw: Dict[str, Any], event_type: str) -> Dict[str, Any]:
        """解析 GDACS 原始事件数据为标准格式。

        Args:
            raw: GDACS API 返回的单个事件数据
            event_type: 事件类型

        Returns:
            标准化事件字典
        """
        # 提取地理位置 — GDACS 使用 GeoJSON 或顶层字段
        geometry = raw.get("geometry") or {}
        coordinates = geometry.get("coordinates", [])
        if coordinates and len(coordinates) >= 2:
            longitude = coordinates[0]
            latitude = coordinates[1]
        else:
            longitude = raw.get("longitude", 0.0) or 0.0
            latitude = raw.get("latitude", 0.0) or 0.0

        # 提取属性
        properties = raw.get("properties", raw)
        alert_level = properties.get("alertlevel", "") or ""
        event_name = properties.get("name", "") or properties.get("eventname", "") or ""
        country = properties.get("country", "") or ""
        description = properties.get("description", "") or ""
        from_date = properties.get("fromdate", "") or ""
        to_date = properties.get("todate", "") or ""
        event_id = properties.get("eventid", "") or raw.get("id", "")
        gdacs_url = properties.get("url", "") or ""
        population = properties.get("populationexposure", None)

        # 解析日期
        start_date = self._parse_date(from_date)
        end_date = self._parse_date(to_date)

        return {
            "event_id": str(event_id),
            "event_type": event_type,
            "severity_raw": alert_level,
            "severity": GDACS_SEVERITY_MAP.get(alert_level, "low"),
            "name": event_name,
            "description": description,
            "latitude": float(latitude),
            "longitude": float(longitude),
            "country": country,
            "start_date": start_date,
            "end_date": end_date,
            "gdacs_url": gdacs_url,
            "population_exposure": population,
            "raw_data": raw,
        }

    def _filter_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """过滤事件：仅保留 Orange/Red 级别，且在 24h 时间窗口内。

        Args:
            events: 待过滤的事件列表

        Returns:
            过滤后的事件列表
        """
        allowed_severities = set(settings.gdacs_min_severity)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.gdacs_time_window_hours)

        filtered = []
        for evt in events:
            # 过滤级别
            if evt["severity_raw"] not in allowed_severities:
                continue

            # 过滤时间窗口：有起始日期且在窗口内，或无日期信息也保留
            start = evt.get("start_date")
            if start and start < cutoff:
                continue

            filtered.append(evt)

        return filtered

    def to_market_event_data(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """将 GDACS 事件转换为 MarketEvent 数据字典。

        转换规则：
        - event_type → "disaster" (natural_disaster)
        - severity: Red → critical, Orange → high
        - raw_text: 包含类型、位置(经纬度)、严重级别、受影响区域
        - confidence: 基于级别设定 (Red=0.9, Orange=0.8)

        Args:
            event: 标准化的 GDACS 事件字典

        Returns:
            可直接用于 MarketEvent 入库的数据字典
        """
        type_zh = GDACS_EVENT_TYPE_MAP.get(event["event_type"], event["event_type"])
        severity = event["severity"]

        # 构建标题
        title = (
            f"[GDACS-{type_zh}] {event['name'] or '未知事件'} "
            f"({event['country'] or '未知区域'}) "
            f"— {severity} 级别"
        )

        # 构建详细描述
        raw_text = (
            f"GDACS {type_zh}预警\n"
            f"事件: {event['name']}\n"
            f"级别: {event['severity_raw']} → {severity}\n"
            f"位置: 纬度 {event['latitude']:.4f}, 经度 {event['longitude']:.4f}\n"
            f"受影响国家/地区: {event['country'] or '未知'}\n"
            f"描述: {event['description']}\n"
        )
        if event.get("population_exposure"):
            raw_text += f"暴露人口: {event['population_exposure']}\n"
        if event.get("start_date"):
            raw_text += f"开始时间: {event['start_date'].isoformat()}\n"
        if event.get("end_date"):
            raw_text += f"结束时间: {event['end_date'].isoformat()}\n"

        # 严重度影响估算
        severity_impact = {
            "critical": {"lead_time_weeks": 4, "price_pct": 15.0},
            "high": {"lead_time_weeks": 2, "price_pct": 8.0},
            "medium": {"lead_time_weeks": 1, "price_pct": 3.0},
            "low": {"lead_time_weeks": 0, "price_pct": 1.0},
        }
        impact = severity_impact.get(severity, severity_impact["low"])

        confidence = 0.9 if severity == "critical" else 0.8

        return {
            "source_name": self.source_name,
            "source_url": event.get("gdacs_url", ""),
            "raw_title": title[:512],
            "raw_text": raw_text,
            "brand": None,
            "category": type_zh,
            "event_type": "disaster",
            "severity": severity,
            "confidence": confidence,
            "estimated_lead_time_impact_weeks": impact["lead_time_weeks"],
            "estimated_price_impact_pct": impact["price_pct"],
            "cross_validated": 1,
            "duration_start": event.get("start_date"),
            "duration_end": event.get("end_date"),
        }

    @staticmethod
    def _parse_date(date_str: str) -> Optional[datetime]:
        """解析 GDACS 日期字符串。

        支持格式: ISO 8601, GDACS 常见格式。

        Args:
            date_str: 日期字符串

        Returns:
            datetime 对象或 None
        """
        if not date_str:
            return None
        formats = [
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str[:len(fmt.replace("%", "").replace("T", "").replace(" ", "")) + 19], fmt)
                return dt.replace(tzinfo=timezone.utc)
            except (ValueError, IndexError):
                continue
        # 最后尝试直接解析 ISO 格式
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None
