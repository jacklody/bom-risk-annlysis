# -*- coding: utf-8 -*-
"""行业媒体/行情数据源注册表。

这里登记“可以采集什么”和“如何采集”，不直接执行网络请求。
微信公众号类源没有公开 API，必须显式标记为 feed/manual/playwright 等待配置策略。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class MediaSource:
    """单个行业媒体/行情源的接入配置。"""

    source_id: str
    name: str
    channel_type: str
    access_method: str
    crawler_strategy: str
    confidence_base: float
    enabled: bool = True
    website_url: str = ""
    wechat_name: str = ""
    url_template: str = ""
    source_type: str = "website"
    max_articles: int = 8
    keywords: list[str] = field(default_factory=list)
    selectors: dict[str, str] = field(default_factory=dict)
    notes: str = ""

    def status(self) -> str:
        if not self.enabled:
            return "disabled"
        if self.crawler_strategy == "manual_forward":
            return "waiting_for_manual_forward"
        if self.crawler_strategy in {"wechat_feed", "playwright_required"}:
            return "waiting_for_configuration"
        return "active"

    def to_dict(self) -> dict:
        data = asdict(self)
        data["status"] = self.status()
        return data


CRAWL_KEYWORDS = [
    "MLCC缺货", "MCU交期", "DRAM产能", "PCB紧缺",
    "MOSFET涨价", "晶圆产能", "IGBT交期", "存储芯片",
]


MEDIA_SOURCES: list[MediaSource] = [
    MediaSource(
        source_id="xinshiyeye_wechat",
        name="芯师爷",
        channel_type="wechat_mp",
        access_method="微信公众号搜索「芯师爷」关注；无公开 API，优先接入 Feed/手动转发",
        crawler_strategy="manual_forward",
        confidence_base=0.48,
        enabled=True,
        wechat_name="芯师爷",
        source_type="wechat_mp",
        notes="每日芯闻/行情来源；单源默认降权，进入观察或待复核。",
    ),
    MediaSource(
        source_id="semiinsights_wechat",
        name="半导体行业观察",
        channel_type="wechat_mp",
        access_method="微信公众号搜索关注；无公开 API，优先接入 Feed/手动转发",
        crawler_strategy="manual_forward",
        confidence_base=0.50,
        enabled=True,
        wechat_name="半导体行业观察",
        source_type="wechat_mp",
        notes="行业深度分析来源；适合提取产业趋势，不单独触发强预警。",
    ),
    MediaSource(
        source_id="esmchina_web",
        name="国际电子商情",
        channel_type="website_and_wechat",
        access_method="官网 esmchina.com + 公众号",
        crawler_strategy="http_html",
        confidence_base=0.68,
        enabled=False,
        website_url="https://www.esmchina.com/",
        wechat_name="国际电子商情",
        url_template="https://www.esmchina.com/",
        source_type="website",
        max_articles=8,
        keywords=CRAWL_KEYWORDS,
        selectors={"article": "article, .item, li", "title": "a", "link": "a"},
        notes="元器件行情/分销商动态；官网 JS 渲染无法直接抓取，当前暂停自动采集，可通过手动转发输入。",
    ),
    MediaSource(
        source_id="mantianxin_wechat",
        name="满天芯",
        channel_type="wechat_mp",
        access_method="微信公众号搜索关注；无公开 API，优先接入 Feed/手动转发",
        crawler_strategy="manual_forward",
        confidence_base=0.52,
        enabled=True,
        wechat_name="满天芯",
        source_type="wechat_mp",
        notes="IC 交易网旗下每日元器件行情；用于补充分销市场情绪。",
    ),
    MediaSource(
        source_id="eeworld_web",
        name="电子工程世界 EEWorld",
        channel_type="website_and_wechat",
        access_method="eeworld.com.cn + 公众号",
        crawler_strategy="http_html",
        confidence_base=0.62,
        enabled=False,
        website_url="https://www.eeworld.com.cn/",
        wechat_name="电子工程世界",
        url_template="https://www.eeworld.com.cn/",
        source_type="website",
        max_articles=8,
        keywords=CRAWL_KEYWORDS,
        selectors={"article": "article, .news-list li, li", "title": "a", "link": "a"},
        notes="行业资讯/技术趋势；当前无法稳定抓取 HTML，暂停自动采集，可通过手动转发输入。",
    ),
    MediaSource(
        source_id="xinzhixun_wechat",
        name="芯智讯",
        channel_type="wechat_mp",
        access_method="微信公众号搜索关注；无公开 API，优先接入 Feed/手动转发",
        crawler_strategy="manual_forward",
        confidence_base=0.50,
        enabled=True,
        wechat_name="芯智讯",
        source_type="wechat_mp",
        notes="芯片产业新闻；先登记为待接入公众号源。",
    ),
    MediaSource(
        source_id="lcsc_jlcsearch",
        name="立创商城 / JLCSearch",
        channel_type="api_and_wechat",
        access_method="JLCSearch API 已接入；公众号促销/活动后续通过手动转发或 Feed 接入",
        crawler_strategy="api_json",
        confidence_base=0.60,
        enabled=True,
        website_url="https://www.szlcsc.com/",
        wechat_name="立创商城",
        url_template="https://jlcsearch.tscircuit.com/api/search?q={keyword}",
        source_type="website",
        max_articles=6,
        keywords=CRAWL_KEYWORDS,
        notes="API 用于库存/热词趋势，公众号用于促销和活动补充。",
    ),
    MediaSource(
        source_id="guanxintai_search",
        name="观芯台行情搜索",
        channel_type="website",
        access_method="网页关键词搜索",
        crawler_strategy="keyword_search",
        confidence_base=0.72,
        enabled=True,
        website_url="https://www.guanxintai.com/",
        url_template="https://www.guanxintai.com/index?keyword={keyword}",
        source_type="website",
        max_articles=6,
        keywords=CRAWL_KEYWORDS,
        selectors={"article": "tr", "title": "td:first-child", "link": "a"},
        notes="当前已验证可作为关键词行情源之一。",
    ),
]


def list_media_sources(enabled_only: bool = False) -> list[MediaSource]:
    """列出媒体源。"""
    if enabled_only:
        return [source for source in MEDIA_SOURCES if source.enabled]
    return list(MEDIA_SOURCES)


def get_media_source(source_id: str) -> MediaSource | None:
    """按 source_id 获取媒体源。"""
    for source in MEDIA_SOURCES:
        if source.source_id == source_id:
            return source
    return None
