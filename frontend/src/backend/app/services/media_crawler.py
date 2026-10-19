# -*- coding: utf-8 -*-
"""行业媒体情报爬虫 v3.11。

爬虫从媒体源注册表读取渠道配置，并按策略采集：
- api_json：适用于 LCSC/JLCSearch 等 JSON API
- keyword_search：http 页面关键词搜索
- http_html：普通官网 HTML 列表页
- manual_forward / wechat_feed / playwright_required：已规划但本阶段不直接 HTTP 抓取

微信公众号类来源没有公开 API，不在这里伪造成直接抓取；后续通过 Feed、手动转发、浏览器登录态或企业入口接入。
"""

from __future__ import annotations

import hashlib
import logging
import random
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.knowledge.media_sources import MediaSource, get_media_source, list_media_sources
from app.services.upstream.market_notice_parser import parse_market_notice

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


@dataclass
class CrawledArticle:
    """爬取到的单篇文章。"""

    url: str = ""
    title: str = ""
    text: str = ""
    source_name: str = ""
    published_date: str = ""
    source_type: str = "website"  # website / wechat_mp / rss
    content_hash: str = ""
    raw_html: str = ""

    def __post_init__(self):
        if not self.content_hash and self.text:
            self.content_hash = hashlib.sha256(
                (self.title + self.text[:500]).encode("utf-8")
            ).hexdigest()[:16]


class IndustryMediaCrawler:
    """行业媒体情报爬虫引擎。"""

    SEARCH_KEYWORDS = [
        "MLCC涨价", "MCU缺货", "IGBT交期", "DRAM产能", "PCB紧缺",
        "MOSFET涨价", "晶圆产能", "分立器件", "存储芯片", "功率模块",
        "电容缺货", "电阻涨价", "晶振交期", "连接器供应",
    ]

    def __init__(self):
        self._client: Optional[httpx.Client] = None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                timeout=httpx.Timeout(20.0),
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            )
        return self._client

    # ── 主入口 ───────────────────────────────────────────────

    def crawl_all(self, source_id: str | None = None) -> list[CrawledArticle]:
        """爬取所有启用数据源，或按 source_id 爬取单个数据源。"""
        if source_id:
            source = get_media_source(source_id)
            if not source:
                logger.warning(f"Media crawler: unknown source_id={source_id}")
                return []
            sources = [source] if source.enabled else []
        else:
            sources = list_media_sources(enabled_only=True)

        all_articles: list[CrawledArticle] = []
        for source in sources:
            try:
                articles = self.crawl_source(source)
                all_articles.extend(articles)
                logger.info(
                    f"Media crawler: {source.name}({source.source_id}) "
                    f"→ {len(articles)} articles"
                )
            except Exception as e:
                logger.warning(
                    f"Media crawler: {source.name}({source.source_id}) failed: {e}"
                )
        return all_articles

    def crawl_source(self, source: MediaSource) -> list[CrawledArticle]:
        """按源策略采集单个媒体源。"""
        strategy = source.crawler_strategy
        if strategy in {"api_json", "keyword_search"}:
            return self._crawl_keyword_source(source)
        if strategy == "http_html":
            return self._crawl_source(source)
        if strategy in {"manual_forward", "wechat_feed", "playwright_required"}:
            logger.info(
                f"Media crawler: {source.name} uses {strategy}; "
                "no direct HTTP crawl in this stage"
            )
            return []
        logger.warning(f"Media crawler: unsupported strategy={strategy} for {source.source_id}")
        return []

    def _crawl_keyword_source(self, source: MediaSource) -> list[CrawledArticle]:
        """通过关键词搜索爬取数据源。"""
        all_articles: list[CrawledArticle] = []
        max_total = source.max_articles
        keywords = source.keywords or self.SEARCH_KEYWORDS
        per_keyword = max(1, max_total // max(1, len(keywords)))

        for keyword in keywords:
            if len(all_articles) >= max_total:
                break
            try:
                encoded_keyword = quote(keyword, safe="")
                url = source.url_template.replace("{keyword}", encoded_keyword)
                if source.crawler_strategy == "api_json":
                    articles = self._crawl_api_json(url, keyword, source, per_keyword)
                else:
                    articles = self._crawl_html_page(url, keyword, source, per_keyword)
                all_articles.extend(articles[:per_keyword])
            except Exception as e:
                logger.debug(f"Keyword '{keyword}' for {source.source_id}: {e}")
                continue
            time.sleep(random.uniform(0.2, 0.5))
        return all_articles[:max_total]

    def _crawl_api_json(
        self,
        url: str,
        keyword: str,
        source: MediaSource,
        limit: int,
    ) -> list[CrawledArticle]:
        """从 JSON API 爬取。"""
        client = self._get_client()
        try:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
            components = data.get("components", [])
            articles = []
            for comp in components[:limit]:
                mfr = comp.get("mfr", "")
                stock = comp.get("stock", 0)
                lcsc = comp.get("lcsc", "")
                title = f"[{keyword}] {mfr} LCSC:{lcsc} 库存:{stock}"
                text = f"搜索关键词'{keyword}'命中：{mfr}，当前立创商城库存{stock}"
                article = CrawledArticle(
                    url=url,
                    title=title,
                    text=text,
                    source_name=source.source_id,
                    source_type=source.source_type,
                )
                articles.append(article)
            return articles
        except Exception:
            return []

    def _crawl_html_page(
        self,
        url: str,
        keyword: str,
        source: MediaSource,
        limit: int,
    ) -> list[CrawledArticle]:
        """从 HTML 搜索页面爬取。"""
        client = self._get_client()
        try:
            resp = client.get(url)
            resp.raise_for_status()
        except Exception:
            return []

        if resp.status_code != 200 or len(resp.text) < 200:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        selectors = source.selectors or {}
        article_selector = selectors.get("article", "tr")

        articles: list[CrawledArticle] = []
        for elem in soup.select(article_selector):
            if len(articles) >= limit:
                break
            text = elem.get_text(" ", strip=True)
            if len(text) < 10:
                continue
            skip = ["首页", "下一页", "上一页", "搜索", "登录"]
            if any(w in text for w in skip):
                continue

            articles.append(CrawledArticle(
                url=url,
                title=text[:200],
                text=text,
                source_name=source.source_id,
                source_type=source.source_type,
            ))
        return articles

    def _crawl_source(self, source: MediaSource) -> list[CrawledArticle]:
        """爬取单个普通 HTML 数据源。"""
        client = self._get_client()
        selectors = source.selectors or {}
        url = source.url_template or source.website_url
        if not url:
            return []

        try:
            resp = client.get(url)
            resp.raise_for_status()
        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        article_selector = selectors.get("article", "article, li")

        articles: list[CrawledArticle] = []
        seen_urls: set[str] = set()
        max_articles = source.max_articles

        for elem in soup.select(article_selector):
            if len(articles) >= max_articles:
                break

            title_elem = elem.select_one(selectors.get("title", "a"))
            link_elem = elem.select_one(selectors.get("link", "a"))
            if not link_elem:
                link_elem = title_elem

            href = link_elem.get("href", "") if link_elem else ""
            if not href:
                continue

            full_url = urljoin(url, href)

            parsed = urlparse(full_url)
            if not parsed.path or parsed.path in ("/", ""):
                continue
            path_lower = parsed.path.lower()
            skip_suffixes = (".jpg", ".png", ".gif", ".pdf", ".zip", ".css", ".js")
            if any(path_lower.endswith(s) for s in skip_suffixes):
                continue

            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            title_text = title_elem.get_text(" ", strip=True) if title_elem else ""
            if len(title_text) < 6:
                continue

            skip_words = ["广告", "关于我们", "联系我们", "隐私", "登录", "注册", "招聘"]
            if any(w in title_text for w in skip_words):
                continue

            article = self._fetch_article(full_url, title_text, source)
            if article:
                articles.append(article)

            time.sleep(random.uniform(2.0, 4.0))

        return articles

    def _fetch_article(
        self, url: str, title: str, source: MediaSource
    ) -> Optional[CrawledArticle]:
        """抓取单篇文章详情。"""
        client = self._get_client()
        try:
            resp = client.get(url)
            resp.raise_for_status()
        except Exception:
            return CrawledArticle(
                url=url,
                title=title,
                text=title,
                source_name=source.source_id,
                source_type=source.source_type,
            )

        soup = BeautifulSoup(resp.text, "html.parser")

        content_selectors = [
            "article", ".article-content", ".article-body",
            ".content", ".post-content", ".entry-content",
            ".news-content", ".text", "#content",
            "main", ".main",
        ]
        text_parts = []
        for selector in content_selectors:
            container = soup.select_one(selector)
            if container:
                for tag in container.select("script, style, nav, footer, .ad, .share"):
                    tag.decompose()
                paragraphs = container.select("p, li, h1, h2, h3, h4")
                text_parts = [p.get_text(" ", strip=True) for p in paragraphs]
                break

        if not text_parts:
            for p in soup.select("body p"):
                text_parts.append(p.get_text(" ", strip=True))

        text = " ".join(text_parts[:30])

        date_selectors = [
            "time", ".date", ".time", ".published", ".post-date",
            "meta[property='article:published_time']",
        ]
        published_date = ""
        for ds in date_selectors:
            d_elem = soup.select_one(ds)
            if d_elem:
                published_date = (
                    d_elem.get("datetime")
                    or d_elem.get("content")
                    or d_elem.get_text(strip=True)
                    or ""
                )
                if published_date:
                    break

        source_type = source.source_type
        page_text = resp.text.lower()
        if any(w in page_text for w in ["微信公众号", "mp.weixin.qq.com", "wechat"]):
            source_type = "wechat_mp"

        article = CrawledArticle(
            url=url,
            title=title,
            text=text if text else title,
            source_name=source.source_id,
            published_date=published_date,
            source_type=source_type,
        )
        return article

    # ── NLP 解析 ──────────────────────────────────────────────

    def parse_to_signals(self, articles: list[CrawledArticle]) -> list[dict]:
        """将爬取文章批量转为 ParsedMarketSignal，用于行情收件箱入库。"""
        signals: list[dict] = []
        for article in articles:
            parsed_list = parse_market_notice(
                raw_text=article.text,
                title=article.title,
                source_type=article.source_type,
                source_name=article.source_name,
            )
            for signal in parsed_list:
                d = signal.to_dict()
                d["source_url"] = article.url
                d["source_name"] = article.source_name
                d["source_type"] = article.source_type
                if article.source_type == "wechat_mp":
                    d["confidence"] = round(d.get("confidence", 0) * 0.6, 2)
                    d["confidence_reason"] = (
                        (d.get("confidence_reason", "") or "")
                        + "；公众号/社交来源降权"
                    )
                signals.append(d)
        return signals

    def close(self):
        if self._client:
            self._client.close()
            self._client = None
