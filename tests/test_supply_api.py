import asyncio

import httpx
import pytest

from app.models.event import EventType, MarketEvent, Severity
from app.services.sources.base import SourceResult
from app.services.sources.lcsc import LCSCSource


class FakeResponse:
    def __init__(self, payload=None, status_code=200, json_error=None):
        self.payload = payload or {}
        self.status_code = status_code
        self.json_error = json_error

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    def json(self):
        if self.json_error:
            raise self.json_error
        return self.payload


class FakeClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []
        self.is_closed = False

    async def get(self, url, params=None):
        self.calls.append({"url": url, "params": params})
        if self.error:
            raise self.error
        return self.response

    async def aclose(self):
        self.is_closed = True


@pytest.mark.asyncio
async def test_lcsc_query_rebuilds_closed_or_cross_loop_cached_client(monkeypatch):
    created_clients = []

    def fake_async_client(*args, **kwargs):
        client = FakeClient(FakeResponse({"results": []}))
        created_clients.append(client)
        return client

    stale_loop = asyncio.new_event_loop()
    monkeypatch.setattr(httpx, "AsyncClient", fake_async_client)
    source = LCSCSource(request_delay=0)
    source._client = FakeClient(error=RuntimeError("Event loop is closed"))
    source._client_loop = stale_loop
    source._client.is_closed = True

    try:
        result = await source.query_by_mpn("STM32F103C8T6")
    finally:
        stale_loop.close()

    assert result.match_status == "not_found"
    assert result.error_reason == "LCSC 暂未命中该型号"
    assert "Event loop is closed" not in (result.error_reason or "")
    assert source._client is created_clients[0]
    assert len(created_clients) == 1


@pytest.mark.asyncio
async def test_lcsc_query_rebuilds_stale_loop_client_even_when_not_closed(monkeypatch):
    created_clients = []

    def fake_async_client(*args, **kwargs):
        client = FakeClient(FakeResponse({"results": []}))
        created_clients.append(client)
        return client

    stale_loop = asyncio.new_event_loop()
    stale_client = FakeClient(error=RuntimeError("Event loop is closed"))
    stale_client.is_closed = False
    monkeypatch.setattr(httpx, "AsyncClient", fake_async_client)
    source = LCSCSource(request_delay=0)
    source._client = stale_client
    source._client_loop = stale_loop

    try:
        result = await source.query_by_mpn("STM32F103C8T6")
    finally:
        stale_loop.close()

    assert result.match_status == "not_found"
    assert result.error_reason == "LCSC 暂未命中该型号"
    assert "Event loop is closed" not in (result.error_reason or "")
    assert stale_client.calls == []
    assert source._client is created_clients[0]
    assert source._client_loop is asyncio.get_running_loop()
    assert len(created_clients) == 1


@pytest.mark.asyncio
async def test_lcsc_query_returns_hit_with_stock_price_and_summary():
    source = LCSCSource(request_delay=0)
    source._client = FakeClient(FakeResponse({
        "components": [{
            "lcsc": "C12345",
            "partNumber": "STM32F103C8T6",
            "mfr": "STMicroelectronics",
            "package": "MCU",
            "stock": 120,
            "price": 12.34,
            "moq": 1,
            "is_basic": True,
        }]
    }))

    result = await source.query_by_mpn("STM32F103C8T6")

    assert isinstance(result, SourceResult)
    assert result.source == "lcsc"
    assert result.match_status == "hit"
    assert result.is_available is True
    assert result.total_stock == 120
    assert result.supplier_count == 1
    assert result.unit_price == 12.34
    assert result.currency == "CNY"
    assert "库存120" in result.raw_summary


@pytest.mark.asyncio
async def test_lcsc_query_returns_not_found_without_exception():
    source = LCSCSource(request_delay=0)
    source._client = FakeClient(FakeResponse({"results": []}))

    result = await source.query_by_mpn("NO_SUCH_PART")

    assert result.match_status == "not_found"
    assert result.is_available is False
    assert result.total_stock == 0
    assert result.error_reason == "LCSC 暂未命中该型号"


@pytest.mark.asyncio
async def test_lcsc_query_returns_parse_failed_for_bad_json():
    source = LCSCSource(request_delay=0)
    source._client = FakeClient(FakeResponse(json_error=ValueError("bad json")))

    result = await source.query_by_mpn("BAD_JSON")

    assert result.match_status == "parse_failed"
    assert result.is_available is False
    assert "bad json" in result.error_reason


@pytest.mark.asyncio
async def test_lcsc_query_returns_timeout_for_httpx_timeout():
    source = LCSCSource(request_delay=0)
    source._client = FakeClient(error=httpx.TimeoutException("read timed out"))

    result = await source.query_by_mpn("TIMEOUT_PART")

    assert result.match_status == "timeout"
    assert result.is_available is False
    assert "read timed out" in result.error_reason


@pytest.mark.asyncio
async def test_lcsc_query_returns_parse_failed_for_invalid_numeric_field():
    source = LCSCSource(request_delay=0)
    source._client = FakeClient(FakeResponse({
        "components": [{
            "lcsc": "C_PARSE_FAIL",
            "partNumber": "BAD_QTY",
            "mfr": "Broken Supplier",
            "stock": "not-a-number",
            "price": 1.23,
        }]
    }))

    result = await source.query_by_mpn("BAD_QTY")

    assert result.match_status == "parse_failed"
    assert result.is_available is False
    assert "not-a-number" in result.error_reason


from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.database import SessionLocal, init_db
from app.main import app
from app.models.bom import BomItem, BomProject, RiskLevel
from app.services.supply_data import AggregatedResult

client = TestClient(app)


def _clean_supply_data():
    init_db()
    db = SessionLocal()
    db.query(BomItem).delete()
    db.query(BomProject).delete()
    db.commit()
    db.close()


def _seed_supply_project_with_item(part_number="STM32F103C8T6"):
    db = SessionLocal()
    try:
        project = BomProject(
            filename="supply-demo.xlsx",
            project_name="供应数据验证项目",
            total_items=1,
            items_analyzed=1,
            last_analysis_at=datetime.now(timezone.utc),
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        item = BomItem(
            bom_upload_id=project.id,
            row_number=1,
            raw_part_number=part_number,
            raw_brand="ST",
            raw_category="MCU",
            normalized_brand="ST",
            normalized_category="MCU",
            risk_level=RiskLevel.YELLOW,
            risk_score=60,
            risk_reason="市场事件风险保留",
            total_stock=7,
            supplier_count=1,
            lead_time_days=30,
            unit_price=8.8,
            lifecycle_status="Active",
            commonality_score=72,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return project.id, item.id
    finally:
        db.close()


class StubSupplyService:
    def __init__(self, result):
        self.result = result

    async def query_one(self, mpn):
        return self.result

    async def query_batch(self, mpns, concurrency=3):
        return {mpn: self.result for mpn in mpns}

    def apply_to_bom_item(self, item, aggregated, db, save=True):
        if not aggregated.is_available:
            return False
        item.total_stock = aggregated.total_stock
        item.supplier_count = aggregated.supplier_count
        item.lead_time_days = aggregated.lead_time_days
        item.unit_price = aggregated.unit_price
        item.lifecycle_status = aggregated.lifecycle_status
        item.production_risk_level = "green"
        item.production_risk_score = 10
        item.supply_risk_reason = "LCSC 有库存，供应风险低"
        item.procurement_suggestion = "按需采购"
        if save:
            db.commit()
        return True


def _override_supply_service(result):
    from app.api import supply
    app.dependency_overrides[supply.get_supply_service] = lambda: StubSupplyService(result)


def _clear_overrides():
    app.dependency_overrides.clear()


def test_supply_query_does_not_write_database():
    _clean_supply_data()
    project_id, item_id = _seed_supply_project_with_item()
    _override_supply_service(AggregatedResult(
        mpn_queried="STM32F103C8T6",
        source_name="LCSC",
        is_available=True,
        match_status="hit",
        total_stock=120,
        supplier_count=1,
        unit_price=12.34,
        currency="CNY",
        lifecycle_status="Unknown",
    ))

    resp = client.get("/api/supply/query", params={"mpn": "STM32F103C8T6"})

    assert resp.status_code == 200
    assert resp.json()["match_status"] == "hit"
    db = SessionLocal()
    try:
        item = db.query(BomItem).filter(BomItem.id == item_id).first()
        assert item.total_stock == 7
        assert item.unit_price == 8.8
    finally:
        db.close()
        _clear_overrides()


def test_refresh_item_writes_supply_fields_but_keeps_market_risk():
    _clean_supply_data()
    project_id, item_id = _seed_supply_project_with_item()
    _override_supply_service(AggregatedResult(
        mpn_queried="STM32F103C8T6",
        source_name="LCSC",
        is_available=True,
        match_status="hit",
        total_stock=120,
        supplier_count=1,
        unit_price=12.34,
        currency="CNY",
        lifecycle_status="Unknown",
    ))

    resp = client.post(f"/api/supply/items/{item_id}/refresh")

    assert resp.status_code == 200
    data = resp.json()
    assert data["updated"] is True
    assert data["item"]["total_stock"] == 120
    db = SessionLocal()
    try:
        item = db.query(BomItem).filter(BomItem.id == item_id).first()
        assert item.total_stock == 120
        assert item.unit_price == 12.34
        assert item.risk_level == RiskLevel.YELLOW
        assert item.risk_score == 60
        assert item.risk_reason == "市场事件风险保留"
    finally:
        db.close()
        _clear_overrides()


def test_refresh_item_failure_does_not_clear_old_supply_fields():
    _clean_supply_data()
    project_id, item_id = _seed_supply_project_with_item()
    _override_supply_service(AggregatedResult(
        mpn_queried="STM32F103C8T6",
        source_name="LCSC",
        is_available=False,
        match_status="not_found",
        error_reason="LCSC 暂未命中该型号",
    ))

    resp = client.post(f"/api/supply/items/{item_id}/refresh")

    assert resp.status_code == 200
    data = resp.json()
    assert data["updated"] is False
    assert data["failure_reason"] == "LCSC 暂未命中该型号"
    assert data["result"]["error_reason"] == "LCSC 暂未命中该型号"
    db = SessionLocal()
    try:
        item = db.query(BomItem).filter(BomItem.id == item_id).first()
        assert item.total_stock == 7
        assert item.supplier_count == 1
        assert item.unit_price == 8.8
        assert item.lifecycle_status == "Active"
    finally:
        db.close()
        _clear_overrides()


def test_project_supply_status_counts_coverage_zero_stock_long_lead_and_eol():
    _clean_supply_data()
    project_id, item_id = _seed_supply_project_with_item()
    db = SessionLocal()
    try:
        item = db.query(BomItem).filter(BomItem.id == item_id).first()
        item.total_stock = 0
        item.lead_time_days = 70
        item.lifecycle_status = "EOL"
        item.eol_status = "confirmed"
        db.commit()
    finally:
        db.close()

    resp = client.get(f"/api/supply/projects/{project_id}/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_items"] == 1
    assert data["items_with_mpn"] == 1
    assert data["items_with_supply_data"] == 1
    assert data["zero_stock_count"] == 1
    assert data["long_lead_count"] == 1
    assert data["eol_count"] == 1
    assert data["coverage_rate"] == 1.0


def test_bom_project_detail_includes_supply_fields():
    _clean_supply_data()
    project_id, item_id = _seed_supply_project_with_item()

    resp = client.get(f"/api/bom/projects/{project_id}")

    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert item["total_stock"] == 7
    assert item["supplier_count"] == 1
    assert item["lead_time_days"] == 30
    assert item["unit_price"] == 8.8
    assert item["lifecycle_status"] == "Active"
    assert item["commonality_score"] == 72


def test_risk_analysis_items_include_id_for_row_supply_refresh(monkeypatch):
    _clean_supply_data()
    project_id, item_id = _seed_supply_project_with_item()

    async def fake_query_batch(mpns, concurrency=3):
        return {}

    class FakeSupplyService:
        async def query_batch(self, mpns, concurrency=3):
            return await fake_query_batch(mpns, concurrency)

    from app.api import risk_analysis
    monkeypatch.setattr(risk_analysis, "get_supply_data_service", lambda: FakeSupplyService())

    resp = client.post(f"/api/risk/analyze/{project_id}")

    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert item["id"] == item_id


def test_risk_analysis_supplemental_category_match_updates_green_item(monkeypatch):
    _clean_supply_data()
    project_id, item_id = _seed_supply_project_with_item()
    db = SessionLocal()
    try:
        item = db.query(BomItem).filter(BomItem.id == item_id).first()
        item.raw_part_number = "ECW-FD2W105K"
        item.raw_brand = "Panasonic"
        item.normalized_brand = "松下/Panasonic"
        item.raw_category = ""
        item.raw_spec = ""
        item.normalized_category = "Film"
        item.risk_level = RiskLevel.GREEN
        event = MarketEvent(
            source_name="行情收件箱",
            raw_text="松下薄膜电容全线涨价，涨幅预期10%以上",
            raw_title="松下薄膜电容涨价通知",
            brand="松下",
            category="film_capacitor",
            event_type=EventType.PRICE_INCREASE,
            severity=Severity.MEDIUM,
            confidence=0.8,
            estimated_price_impact_pct=10.0,
            is_active=1,
        )
        db.add(event)
        db.commit()
    finally:
        db.close()

    class FakeSupplyService:
        _initialized = True

        async def query_batch(self, mpns, concurrency=3):
            return {}

    from app.api import risk_analysis
    monkeypatch.setattr(risk_analysis, "get_supply_data_service", lambda: FakeSupplyService())

    resp = client.post(f"/api/risk/analyze/{project_id}")

    assert resp.status_code == 200
    payload = resp.json()["items"][0]
    assert payload["risk_level"] in {"yellow", "red"}
    assert payload["matched_events"]
    assert "松下" in payload["risk_reason"] or "film_capacitor" in payload["risk_reason"]


def test_risk_analysis_initializes_supply_service_before_query_batch(monkeypatch):
    _clean_supply_data()
    project_id, item_id = _seed_supply_project_with_item()
    calls = []

    class FakeSupplyService:
        _initialized = False

        async def initialize(self):
            calls.append("initialize")
            self._initialized = True

        async def query_batch(self, mpns, concurrency=3):
            calls.append("query_batch_initialized" if self._initialized else "query_batch_uninitialized")
            return {}

    from app.api import risk_analysis
    monkeypatch.setattr(risk_analysis, "get_supply_data_service", lambda: FakeSupplyService())

    resp = client.post(f"/api/risk/analyze/{project_id}")

    assert resp.status_code == 200
    assert calls == ["initialize", "query_batch_initialized"]


def test_supply_sources_status_endpoint_exposes_configuration_and_health(monkeypatch):
    from app.services.sources.base import SourceResult
    from app.services.supply_data import SupplyDataService

    class StatusSource:
        def __init__(self, name, configured=True, result=None):
            self.source_name = name
            self._configured = configured
            self._result = result

        @property
        def is_configured(self):
            return self._configured

        async def query_by_mpn(self, mpn):
            return self._result or SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                match_status="not_configured",
                error_reason="未配置",
            )

    service = SupplyDataService()
    service._lcsc = StatusSource("lcsc", configured=True, result=SourceResult(source="lcsc", mpn_queried="STM32", match_status="hit", is_available=True, total_stock=88))
    service._mouser = StatusSource("mouser", configured=False)
    service._digikey = StatusSource("digikey", configured=False)
    service._guanxintai = StatusSource("guanxintai", configured=True, result=SourceResult(source="guanxintai", mpn_queried="STM32", match_status="request_failed", error_reason="timeout"))
    service._all_sources = [service._lcsc, service._mouser, service._digikey, service._guanxintai]
    service._enabled_sources = [service._lcsc, service._mouser, service._digikey, service._guanxintai]

    monkeypatch.setattr("app.api.supply._service", service)

    resp = client.get("/api/supply/sources/status", params={"sample_mpn": "STM32"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["sample_mpn"] == "STM32"
    sources = {source["source"]: source for source in data["sources"]}
    assert set(sources) >= {"lcsc", "mouser", "digikey", "guanxintai"}
    assert sources["lcsc"]["status"] == "active"
    assert sources["lcsc"]["configured"] is True
    assert sources["lcsc"]["match_status"] == "hit"
    assert sources["mouser"]["status"] == "not_configured"
    assert sources["digikey"]["status"] == "not_configured"
    assert sources["guanxintai"]["status"] == "degraded"
    assert sources["guanxintai"]["error_reason"] == "timeout"
    assert data["summary"]["total_sources"] >= 4
    assert data["summary"]["active_sources"] == 1
    assert data["summary"]["not_configured_sources"] == 2
    assert data["summary"]["degraded_sources"] == 1


def test_risk_report_high_risk_items_include_supply_evidence():
    _clean_supply_data()
    project_id, item_id = _seed_supply_project_with_item()
    db = SessionLocal()
    try:
        project = db.query(BomProject).filter(BomProject.id == project_id).first()
        project.items_red = 1
        project.items_yellow = 0
        project.items_green = 0
        item = db.query(BomItem).filter(BomItem.id == item_id).first()
        item.risk_level = RiskLevel.RED
        item.total_stock = 120
        item.supplier_count = 2
        item.lead_time_days = 21
        item.unit_price = 3.14
        item.lifecycle_status = "Active"
        item.supply_sources_summary = "lcsc:库存120 mouser:库存80"
        db.commit()
    finally:
        db.close()

    resp = client.get(f"/api/risk/report/{project_id}")

    assert resp.status_code == 200
    item = resp.json()["high_risk_items"][0]
    assert item["supplier_count"] == 2
    assert item["unit_price"] == 3.14
    assert item["lifecycle_status"] == "Active"
    assert item["supply_sources_summary"] == "lcsc:库存120 mouser:库存80"


def test_risk_report_high_risk_items_include_market_evidence_and_risk_tags():
    _clean_supply_data()
    project_id, item_id = _seed_supply_project_with_item()
    db = SessionLocal()
    try:
        project = db.query(BomProject).filter(BomProject.id == project_id).first()
        project.items_red = 1
        project.items_yellow = 0
        project.items_green = 0
        item = db.query(BomItem).filter(BomItem.id == item_id).first()
        item.raw_brand = "TDK"
        item.normalized_brand = "TDK"
        item.raw_category = "capacitor"
        item.normalized_category = "high_cap_mlcc"
        item.risk_level = RiskLevel.RED
        item.supply_risk_tags = "stockout,lead_time_long,lifecycle_risk"
        item.procurement_suggestion = "行情涨价缺货叠加交期延长，建议提前锁单并准备替代料"
        event = MarketEvent(
            source_name="采购邮箱",
            raw_title="TDK高容MLCC涨价缺货",
            raw_text="TDK高容MLCC涨价缺货，交期延长到16周",
            brand="TDK",
            category="high_cap_mlcc",
            event_type=EventType.PRICE_INCREASE,
            severity=Severity.HIGH,
            confidence=0.92,
            estimated_price_impact_pct=18,
            estimated_lead_time_impact_weeks=16,
            is_active=1,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        event_id = event.id
        item.matched_event_ids = str(event_id)
        db.commit()
    finally:
        db.close()

    resp = client.get(f"/api/risk/report/{project_id}")

    assert resp.status_code == 200
    item = resp.json()["high_risk_items"][0]
    assert item["supply_risk_tags"] == "stockout,lead_time_long,lifecycle_risk"
    assert item["procurement_suggestion"] == "行情涨价缺货叠加交期延长，建议提前锁单并准备替代料"
    assert item["market_evidence"] == [
        {
            "id": event_id,
            "title": "TDK高容MLCC涨价缺货",
            "source_name": "采购邮箱",
            "event_type": "price_increase",
            "severity": "high",
            "confidence": 0.92,
            "price_impact_pct": 18.0,
            "lead_time_impact_weeks": 16,
        }
    ]


def test_risk_report_high_risk_items_include_v32_evidence_chain_after_analysis(monkeypatch):
    _clean_supply_data()
    project_id, item_id = _seed_supply_project_with_item(part_number="C3216X5R1A476M160AC")
    db = SessionLocal()
    try:
        project = db.query(BomProject).filter(BomProject.id == project_id).first()
        project.items_red = 1
        project.items_yellow = 0
        project.items_green = 0
        item = db.query(BomItem).filter(BomItem.id == item_id).first()
        item.raw_brand = "TDK"
        item.normalized_brand = "TDK"
        item.raw_category = "capacitor"
        item.normalized_category = "high_cap_mlcc"
        item.raw_spec = "47uF 10V X5R 1206 MLCC"
        item.risk_level = RiskLevel.RED
        event = MarketEvent(
            source_name="人工录入",
            raw_title="TDK高容MLCC涨价缺货",
            raw_text="TDK高容MLCC缺货涨价，交期16周",
            brand="TDK",
            category="high_cap_mlcc",
            event_type=EventType.PRICE_INCREASE,
            severity=Severity.HIGH,
            confidence=0.9,
            estimated_price_impact_pct=20,
            estimated_lead_time_impact_weeks=16,
            is_active=1,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        item.matched_event_ids = str(event.id)
        item.risk_trigger_event_ids = str(event.id)
        db.commit()
    finally:
        db.close()

    resp = client.get(f"/api/risk/report/{project_id}")

    assert resp.status_code == 200
    item = resp.json()["high_risk_items"][0]
    assert item["v32_risk_level"] in {"orange", "red"}
    assert item["v32_evidence_summary"]
    assert "高容MLCC" in item["v32_evidence_summary"]
    assert item["v32_action_suggestion"]
    assert any(node["type"] == "market_event" for node in item["v32_evidence_chain"])
    assert any(node["type"] == "dual_track" for node in item["v32_evidence_chain"])
