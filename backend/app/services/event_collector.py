"""事件采集器 v3.11：多源行情情报爬取 + 行情知识库增强。

数据源：
- market_intel_kb: 内置行情知识库（每次启动/手动触发均可播种）
- industry_media: 行业媒体爬虫（国际电子商情/华强电子网/满天芯/EEWorld/观芯台公告）
- lcsc_new: LCSC 新品/热门物料趋势（通过 jlcsearch API）

工作流程：
collect_all() → 遍历所有源 → 每条情报 NLP 提取品牌/品类/事件类型 → 去重 → 入库
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List

import asyncio
import httpx
from sqlalchemy.orm import Session

from app.models.event import MarketEvent, EventType, Severity
from app.models.media_source import MediaSourceRun
from app.knowledge.market_intel import MARKET_INTEL_ENTRIES
from app.knowledge.media_sources import get_media_source, list_media_sources
from app.services.nlp_extractor import NLPExtractor
from app.services.media_crawler import IndustryMediaCrawler
from app.services.sources.gdacs_source import GdacsSource
from app.services.sources.usgs_earthquake_source import UsgsEarthquakeSource
from app.config import settings

logger = logging.getLogger(__name__)


class EventCollector:
    """多源行情事件采集器。"""

    def __init__(self, db: Session):
        self.db = db
        self.extractor = NLPExtractor()

    # ── 主入口 ──────────────────────────────────────────────

    def collect_all(self) -> List[MarketEvent]:
        """拉取所有数据源，提取事件并入库"""
        new_events: List[MarketEvent] = []

        # 1) 行情知识库播种（去重后不会重复插入）
        kb_events = self._seed_knowledge_base()
        new_events.extend(kb_events)

        # 2) 行业媒体爬虫
        try:
            media_events = self._collect_from_industry_media()
            new_events.extend(media_events)
        except Exception as e:
            logger.warning(f"Industry media crawl failed: {e}")

        # 3) LCSC 热词趋势
        lcsc_event_count = 0
        try:
            lcsc_items = self._collect_lcsc_new_arrivals()
            for evt_data in lcsc_items:
                saved = self._save_event(evt_data)
                if saved:
                    new_events.append(saved)
                    lcsc_event_count += 1
        except Exception as e:
            logger.warning(f"LCSC trends failed: {e}")

        # 4) GDACS 自然灾害事件
        try:
            gdacs_events = self.collect_gdacs_events()
            new_events.extend(gdacs_events)
        except Exception as e:
            logger.warning(f"GDACS disaster collection failed: {e}")

        # 5) USGS 地震事件
        try:
            usgs_events = self.collect_usgs_earthquake_events()
            new_events.extend(usgs_events)
        except Exception as e:
            logger.warning(f"USGS earthquake collection failed: {e}")

        # 记录全量采集运行
        self.record_source_run(
            source_id="all",
            status="success" if new_events else "empty",
            articles_crawled=0,
            signals_parsed=0,
            events_created=len(new_events),
        )

        return new_events

    # ── 播种行情知识库 ──────────────────────────────────────

    def _seed_knowledge_base(self) -> List[MarketEvent]:
        """将 MARKET_INTEL_ENTRIES 中尚未入库的条目写入 market_events"""
        new_events = []
        for entry in MARKET_INTEL_ENTRIES:
            title = (entry.summary or "")[:200]
            existing = self.db.query(MarketEvent).filter(
                MarketEvent.raw_title == title,
                MarketEvent.source_name == "market_intel_kb",
            ).first()
            if existing:
                continue

            evt_data = {
                "source_name": "market_intel_kb",
                "source_url": "kb://market_intel",
                "raw_title": title,
                "raw_text": f"{entry.summary}\n\n业务建议：{entry.business_advice}",
                "brand": entry.brand or None,
                "category": entry.category or None,
                "event_type": entry.event_type,
                "severity": entry.severity,
                "confidence": entry.confidence,
                "estimated_lead_time_impact_weeks": entry.lead_time_impact_weeks,
                "estimated_price_impact_pct": entry.price_impact_pct,
                "cross_validated": max(1, len(entry.sources)),
            }
            saved = self._save_event(evt_data)
            if saved:
                new_events.append(saved)
        return new_events

    # ── 行业媒体爬虫 ──────────────────────────────────────

    def _collect_from_industry_media(self, source_id: str | None = None) -> List[MarketEvent]:
        """通过 IndustryMediaCrawler 爬取多源行业媒体，NLP 解析后入库。

        单源采集：只记录该源的运行结果。
        全量采集：按源拆分，每个启用源独立记录运行结果。
        """
        new_events: List[MarketEvent] = []

        if source_id:
            return self._collect_one_media_source(source_id)

        # 全量采集：逐个源采集并记录
        sources = list_media_sources(enabled_only=True)
        for src in sources:
            try:
                evts = self._collect_one_media_source(src.source_id)
                new_events.extend(evts)
            except Exception as exc:
                logger.warning(f"Media source {src.source_id} failed: {exc}")
                self.record_source_run(
                    source_id=src.source_id,
                    status="failed",
                    articles_crawled=0,
                    signals_parsed=0,
                    events_created=0,
                    error_message=str(exc)[:500],
                )
        return new_events

    def _collect_one_media_source(self, source_id: str) -> List[MarketEvent]:
        """对单个媒体源执行采集、NLP 解析、入库并记录运行结果。"""
        source = get_media_source(source_id)
        if not source:
            return []

        crawler = IndustryMediaCrawler()
        run = self._start_source_run(source_id)
        new_events: List[MarketEvent] = []
        articles: list = []
        signals: list = []

        try:
            articles = crawler.crawl_all(source_id=source_id)
            if not articles:
                logger.info(f"Media crawler: {source_id} no articles")
                self._finish_source_run(run, "empty", 0, 0, 0)
                return new_events

            signals = crawler.parse_to_signals(articles)
            logger.info(f"Media crawler {source_id}: {len(articles)} articles → {len(signals)} signals")

            for sig in signals:
                if sig.get("confidence", 0) < settings.min_confidence_threshold:
                    continue

                evt_data = {
                    "source_name": sig.get("source_name", "industry_media"),
                    "source_url": sig.get("source_url", ""),
                    "raw_title": (sig.get("evidence_text") or "")[:200],
                    "raw_text": sig.get("evidence_text", ""),
                    "brand": sig.get("brand"),
                    "category": sig.get("category"),
                    "event_type": sig.get("event_type", "other"),
                    "severity": "medium" if sig.get("confidence", 0) < 0.7 else "high",
                    "confidence": sig.get("confidence", 0.55),
                    "estimated_lead_time_impact_weeks": sig.get("lead_time_weeks"),
                    "estimated_price_impact_pct": sig.get("increase_max_pct"),
                }
                saved = self._save_event(evt_data)
                if saved:
                    new_events.append(saved)

            self._finish_source_run(run, "success", len(articles), len(signals), len(new_events))
        except Exception as exc:
            logger.warning(f"Media source {source_id} error: {exc}")
            self._finish_source_run(run, "failed", 0, 0, 0, error_message=str(exc)[:500])
        finally:
            crawler.close()
        return new_events

    # ── 媒体源运行记录 ──────────────────────────────────────

    def _start_source_run(self, source_id: str) -> MediaSourceRun:
        run = MediaSourceRun(source_id=source_id, status="running")
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def _finish_source_run(
        self,
        run: MediaSourceRun,
        status: str,
        articles_crawled: int,
        signals_parsed: int,
        events_created: int,
        error_message: str | None = None,
    ):
        run.status = status
        run.articles_crawled = articles_crawled
        run.signals_parsed = signals_parsed
        run.events_created = events_created
        run.error_message = error_message
        run.completed_at = datetime.now(timezone.utc)
        self.db.commit()

    def record_source_run(
        self,
        source_id: str,
        status: str,
        articles_crawled: int = 0,
        signals_parsed: int = 0,
        events_created: int = 0,
        error_message: str | None = None,
    ) -> MediaSourceRun:
        """外部可直接调用的运行记录入口。"""
        run = MediaSourceRun(
            source_id=source_id,
            status=status,
            articles_crawled=articles_crawled,
            signals_parsed=signals_parsed,
            events_created=events_created,
            error_message=error_message,
            completed_at=datetime.now(timezone.utc),
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    # ── LCSC 新品/热门趋势 ──────────────────────────────────

    def _collect_lcsc_new_arrivals(self) -> List[Dict]:
        """通过 LCSC 热门搜索获取需求侧信号"""
        items = []
        hot_queries = [
            "STM32", "MCU", "MOSFET", "IGBT", "MLCC", "DRAM",
            "SDRAM", "PCB", "电源IC", "晶振", "二极管", "三极管",
        ]
        try:
            client = httpx.Client(timeout=10.0, follow_redirects=True)
            for query in hot_queries:
                try:
                    resp = client.get(
                        "https://jlcsearch.tscircuit.com/api/search",
                        params={"q": query, "limit": 3},
                    )
                    data = resp.json()
                    comps = data.get("components", [])
                    if comps:
                        stock_total = sum((c.get("stock", 0) or 0) for c in comps)
                        items.append({
                            "source_name": "lcsc_trends",
                            "source_url": f"https://jlcsearch.tscircuit.com/api/search?q={query}",
                            "raw_title": f"LCSC搜索热词 '{query}' 返回{len(comps)}条，总库存{stock_total}",
                            "raw_text": f"LCSC搜索 '{query}' 结果: {comps[0].get('mfr','')}库存{comps[0].get('stock',0)}",
                            "confidence": 0.55,
                        })
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"LCSC trends failed: {e}")
        return items

    # ── 事件保存/去重 ──────────────────────────────────────

    def _save_event(self, event_data: Dict, min_confidence: float | None = None) -> MarketEvent | None:
        confidence = event_data.get("confidence", 0)
        threshold = min_confidence if min_confidence is not None else settings.min_confidence_threshold
        if confidence < threshold:
            return None

        source_url = event_data.get("source_url")
        brand = event_data.get("brand")
        category = event_data.get("category")

        existing = None
        if source_url and source_url != "kb://market_intel":
            query = self.db.query(MarketEvent).filter(
                MarketEvent.source_url == source_url,
            )
            if brand:
                query = query.filter(MarketEvent.brand == brand)
            if category:
                query = query.filter(MarketEvent.category == category)
            existing = query.first()

        if existing:
            if not existing.cross_validated:
                existing.cross_validated = 1
            elif existing.cross_validated < 5:
                # v3.3: cross_validated 上限 5，防止旧事件无限"权威化"
                existing.cross_validated += 1
            existing.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            return None

        evt_type = event_data.get("event_type", "other")
        severity = event_data.get("severity", "unknown")

        evt = MarketEvent(
            source_name=event_data.get("source_name", "unknown"),
            source_url=source_url or "",
            raw_text=event_data.get("raw_text", ""),
            raw_title=event_data.get("raw_title", ""),
            brand=event_data.get("brand"),
            category=event_data.get("category"),
            event_type=EventType(evt_type) if evt_type in {e.value for e in EventType} else EventType.OTHER,
            severity=Severity(severity) if severity in {s.value for s in Severity} else Severity.UNKNOWN,
            confidence=confidence,
            estimated_lead_time_impact_weeks=event_data.get("estimated_lead_time_impact_weeks"),
            estimated_price_impact_pct=event_data.get("estimated_price_impact_pct"),
            cross_validated=event_data.get("cross_validated", 0),
            is_active=1,
        )
        self.db.add(evt)
        self.db.commit()
        self.db.refresh(evt)
        return evt

    def add_manual_event(self, event_data: Dict) -> MarketEvent | None:
        event_data["source_name"] = "manual"
        event_data.setdefault("confidence", 0.5)
        return self._save_event(event_data)

    # ── v3.4: 原材料价格事件采集 ──────────────────────────────

    def collect_material_price_events(
        self, material_alerts: List[Dict]
    ) -> List[MarketEvent]:
        """将 MaterialTracker 检测到的价格异常转换为 MarketEvent。

        去重规则：同一 material_key + 同一天已有活跃 material_price 事件，
        则仅递增 cross_validated，不新增事件。上限 5。
        """
        new_events: List[MarketEvent] = []
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        from app.knowledge.material_mapping import get_categories_for_material

        for alert in material_alerts:
            material_key = alert.get("material_key", "")
            risk_level = alert.get("risk_level", "")

            # 仅 ORANGE 及以上生成事件
            if risk_level not in ("ORANGE", "RED"):
                continue

            categories = get_categories_for_material(material_key)
            category_str = ",".join(categories) if categories else ""

            # 去重：同 material_key + 当天
            existing = self.db.query(MarketEvent).filter(
                MarketEvent.event_type == EventType.MATERIAL_PRICE,
                MarketEvent.brand == material_key,
                MarketEvent.category == category_str,
                MarketEvent.is_active == 1,
                MarketEvent.created_at >= today,
            ).first()

            if existing:
                if existing.cross_validated < 5:
                    existing.cross_validated += 1
                existing.updated_at = datetime.now(timezone.utc)
                self.db.commit()
                continue

            change_pct = alert.get("change_pct", 0)
            severity = Severity.HIGH if risk_level == "RED" else Severity.MEDIUM
            direction = "涨" if change_pct > 0 else "跌"

            evt_data = {
                "source_name": alert.get("source_name", "material_tracker"),
                "source_url": "",
                "raw_title": f"[原材料] {alert.get('material_name_zh', material_key)} {direction}{abs(change_pct):.1f}%",
                "raw_text": (
                    f"{alert.get('material_name_zh', material_key)}"
                    f"价格{direction}{abs(change_pct):.1f}%，"
                    f"当前价格：{alert.get('current_price', 'N/A')}{alert.get('price_unit', '')}，"
                    f"30日基线：{alert.get('baseline_30d', 'N/A')}{alert.get('price_unit', '')}，"
                    f"影响品类：{category_str}"
                ),
                "brand": material_key,
                "category": category_str,
                "event_type": "material_price",
                "severity": severity.value,
                "confidence": 0.85,
                "estimated_price_impact_pct": abs(change_pct),
                "cross_validated": 1,
            }
            saved = self._save_event(evt_data, min_confidence=0.0)
            if saved:
                new_events.append(saved)

        return new_events

    # ── T2-002: GDACS 自然灾害事件采集 ──────────────────────────

    def collect_gdacs_events(self) -> List[MarketEvent]:
        """从 GDACS 采集自然灾害事件并转换为 MarketEvent。

        采集策略：
        - 定时 4 小时
        - 过滤 Orange/Red 级别
        - 事件类型: earthquake/flood/cyclone/fire/drought
        - 时间窗口 24h

        降级策略：API 不可用时不报错，记录降级日志。

        Returns:
            新增的 MarketEvent 列表
        """
        if not settings.gdacs_enabled:
            logger.info("GDACS data source disabled, skipping")
            return []

        new_events: List[MarketEvent] = []
        source = GdacsSource()

        try:
            # 运行异步采集
            loop = asyncio.new_event_loop()
            try:
                events = loop.run_until_complete(source.fetch_events())
            finally:
                loop.close()

            logger.info(f"GDACS: collected {len(events)} filtered events")

            for evt in events:
                evt_data = source.to_market_event_data(evt)
                saved = self._save_event(evt_data, min_confidence=0.0)
                if saved:
                    new_events.append(saved)

            self.record_source_run(
                source_id="gdacs",
                status="success" if events else "empty",
                events_created=len(new_events),
            )

        except Exception as e:
            logger.warning(
                f"GDACS collection degraded gracefully: {e}",
                exc_info=True,
            )
            self.record_source_run(
                source_id="gdacs",
                status="failed",
                events_created=0,
                error_message=str(e)[:500],
            )

        return new_events

    # ── T2-003: USGS 地震事件采集 ──────────────────────────

    def collect_usgs_earthquake_events(self) -> List[MarketEvent]:
        """从 USGS 采集地震事件并转换为 MarketEvent。

        采集策略：
        - 定时 2 小时
        - 震级 >= 5.0
        - 特别关注区域权重加倍
        - 半导体工厂匹配（<=200km 直接，200-500km 间接）

        降级策略：API 不可用时不报错，记录降级日志。

        Returns:
            新增的 MarketEvent 列表
        """
        if not settings.usgs_enabled:
            logger.info("USGS data source disabled, skipping")
            return []

        new_events: List[MarketEvent] = []
        source = UsgsEarthquakeSource()

        try:
            # 运行异步采集
            loop = asyncio.new_event_loop()
            try:
                earthquakes = loop.run_until_complete(source.fetch_earthquakes())
            finally:
                loop.close()

            logger.info(
                f"USGS: collected {len(earthquakes)} earthquakes M>="
                f"{settings.usgs_min_magnitude}"
            )

            for eq in earthquakes:
                evt_data = source.to_market_event_data(eq)
                saved = self._save_event(evt_data, min_confidence=0.0)
                if saved:
                    new_events.append(saved)

            self.record_source_run(
                source_id="usgs",
                status="success" if earthquakes else "empty",
                events_created=len(new_events),
            )

        except Exception as e:
            logger.warning(
                f"USGS collection degraded gracefully: {e}",
                exc_info=True,
            )
            self.record_source_run(
                source_id="usgs",
                status="failed",
                events_created=0,
                error_message=str(e)[:500],
            )

        return new_events
