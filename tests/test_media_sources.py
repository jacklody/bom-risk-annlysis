from fastapi.testclient import TestClient

from app.knowledge.media_sources import get_media_source, list_media_sources
from app.main import app
from app.services.media_crawler import IndustryMediaCrawler

client = TestClient(app)


def test_media_sources_endpoint_lists_required_sources_with_status():
    resp = client.get("/api/events/media-sources")

    assert resp.status_code == 200
    data = resp.json()
    sources = {source["source_id"]: source for source in data["sources"]}

    expected = {
        "xinshiyeye_wechat": "芯师爷",
        "semiinsights_wechat": "半导体行业观察",
        "esmchina_web": "国际电子商情",
        "mantianxin_wechat": "满天芯",
        "eeworld_web": "电子工程世界 EEWorld",
        "xinzhixun_wechat": "芯智讯",
        "lcsc_jlcsearch": "立创商城 / JLCSearch",
    }
    for source_id, name in expected.items():
        assert source_id in sources
        assert sources[source_id]["name"] == name
        assert sources[source_id]["crawler_strategy"]
        assert sources[source_id]["confidence_base"] > 0
        assert sources[source_id]["status"] in {
            "active",
            "disabled",
            "waiting_for_manual_forward",
            "waiting_for_configuration",
        }


def test_manual_and_waiting_sources_do_not_directly_http_crawl():
    crawler = IndustryMediaCrawler()
    try:
        for source in list_media_sources():
            if source.crawler_strategy in {"manual_forward", "wechat_feed", "playwright_required"}:
                assert source.to_dict()["status"] in {
                    "waiting_for_manual_forward",
                    "waiting_for_configuration",
                }
                assert crawler.crawl_source(source) == []
    finally:
        crawler.close()


def test_collect_media_manual_forward_source_is_skipped_with_explainable_status():
    resp = client.post("/api/events/collect-media", params={"source_id": "xinshiyeye_wechat"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "skipped"
    assert data["source_id"] == "xinshiyeye_wechat"
    assert data["source_status"] == "waiting_for_manual_forward"
    assert data["articles_crawled"] == 0
    assert "手动转发" in data["message"]


def test_collect_media_all_reports_skipped_manual_and_waiting_sources():
    resp = client.post("/api/events/collect-media")

    assert resp.status_code == 200
    data = resp.json()
    skipped = {source["source_id"]: source for source in data["skipped_sources"]}
    assert "xinshiyeye_wechat" in skipped
    assert skipped["xinshiyeye_wechat"]["source_status"] == "waiting_for_manual_forward"
    assert "semiinsights_wechat" in skipped
    assert skipped["semiinsights_wechat"]["source_status"] == "waiting_for_manual_forward"
    assert "esmchina_web" in skipped
    assert skipped["esmchina_web"]["source_status"] == "disabled"
    assert data["skipped_count"] >= 3


def test_enabled_only_media_sources_excludes_disabled_http_sources():
    resp = client.get("/api/events/media-sources", params={"enabled_only": True})

    assert resp.status_code == 200
    source_ids = {source["source_id"] for source in resp.json()["sources"]}
    assert "lcsc_jlcsearch" in source_ids
    assert "guanxintai_search" in source_ids
    assert "esmchina_web" not in source_ids
    assert "eeworld_web" not in source_ids
