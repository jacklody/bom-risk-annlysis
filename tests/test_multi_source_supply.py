"""多源供应数据聚合测试"""
import pytest
import httpx
from app.services.sources.base import SourceResult
from app.services.sources.mouser import MouserSource


class FakeResponse2:
    def __init__(self, payload=None, status_code=200):
        self.payload = payload or {}
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


class FakeClient2:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []
        self.is_closed = False

    async def post(self, url, params=None, json=None, headers=None):
        self.calls.append({"url": url, "params": params, "json": json, "headers": headers})
        if self.error:
            raise self.error
        return self.response


@pytest.mark.asyncio
async def test_mouser_query_returns_hit_with_stock_price_leadtime_lifecycle():
    source = MouserSource(api_key="test-key")
    source._client = FakeClient2(FakeResponse2({
        "SearchResults": {
            "Parts": [{
                "ManufacturerPartNumber": "STM32F103C8T6",
                "Manufacturer": "STMicroelectronics",
                "Availability": "1,234 In Stock. 10 Days Factory Lead Time.",
                "LifecycleStatus": "Active",
                "PriceBreaks": [
                    {"Quantity": 1, "Price": "$12.34"},
                    {"Quantity": 10, "Price": "$10.50"},
                ],
                "Min": 1,
            }]
        }
    }))

    result = await source.query_by_mpn("STM32F103C8T6")

    assert isinstance(result, SourceResult)
    assert result.source == "mouser"
    assert result.match_status == "hit"
    assert result.is_available is True
    assert result.total_stock == 1234
    assert result.lead_time_days == 10
    assert result.unit_price == 12.34
    assert result.currency == "USD"
    assert result.lifecycle_status == "Active"
    assert result.manufacturer == "STMicroelectronics"


@pytest.mark.asyncio
async def test_mouser_query_returns_not_found_without_exception():
    source = MouserSource(api_key="test-key")
    source._client = FakeClient2(FakeResponse2({"SearchResults": {"Parts": []}}))

    result = await source.query_by_mpn("NO_SUCH")

    assert result.match_status == "not_found"
    assert result.is_available is False


from app.services.sources.guanxintai import GuanxintaiSource


@pytest.mark.asyncio
async def test_guanxintai_parse_table_yields_stock_price():
    html = """
<table>
<tr><td>STM32F103C8T6</td><td>ST</td><td>1+:¥6.98</td><td>1,063</td><td>立即发货</td><td>立创商城</td></tr>
<tr><td>STM32F103C8T6</td><td>ST</td><td>1+:¥6.98</td><td>33,688</td><td>立即发货</td><td>华秋商城</td></tr>
</table>
"""
    class FakeGuanxinClient:
        async def get(self, url, params=None):
            return FakeResponse2({}, status_code=200)
        async def aclose(self): pass

    source = GuanxintaiSource()
    source._client = FakeGuanxinClient()
    result = source._parse_html_to_result(html, "STM32F103C8T6")

    assert result.source == "guanxintai"
    assert result.is_available is True
    assert result.total_stock == 33688
    assert result.unit_price == 6.98
    assert result.match_status == "hit"


@pytest.mark.asyncio
async def test_mouser_query_returns_timeout_for_httpx_timeout():
    source = MouserSource(api_key="test-key")
    source._client = FakeClient2(error=httpx.TimeoutException("timeout"))

    result = await source.query_by_mpn("TIMED_OUT")

    assert result.match_status == "timeout"
    assert result.is_available is False
    assert "timeout" in result.error_reason


@pytest.mark.asyncio
async def test_mouser_not_configured_returns_unconfigured():
    source = MouserSource(api_key="")

    result = await source.query_by_mpn("STM32")

    assert result.match_status == "not_configured"
    assert result.is_available is False


from app.services.sources.digikey import DigiKeySource


class FakeDigiKeyClient:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls = []
        self.is_closed = False

    def _match(self, url):
        for key, val in self.responses.items():
            if url.endswith(key) or key in url:
                return val
        return FakeResponse2({})

    async def post(self, url, data=None, json=None, headers=None):
        self.calls.append({"url": url, "data": data, "json": json, "headers": headers})
        if url.endswith("/oauth2/token") or "/v1/oauth2/token" in url:
            return FakeResponse2({"access_token": "fake-token", "expires_in": 600})
        return self._match(url)


@pytest.mark.asyncio
async def test_digikey_query_returns_hit_with_all_fields():
    source = DigiKeySource(client_id="test-id", client_secret="test-secret")
    digi_resp = FakeResponse2({
        "Products": [{
            "ManufacturerProductNumber": "STM32F103C8T6TR",
            "Manufacturer": {"Name": "STMicroelectronics"},
            "QuantityAvailable": 4034,
            "UnitPrice": 54.66,
            "ManufacturerLeadWeeks": "20",
            "ProductStatus": {"Id": 0, "Status": "在售"},
        }]
    })
    fake = FakeDigiKeyClient({"/products/v4/search/keyword": digi_resp})
    source._client = fake

    result = await source.query_by_mpn("STM32F103C8T6")

    assert isinstance(result, SourceResult)
    assert result.source == "digikey"
    assert result.match_status == "hit"
    assert result.is_available is True
    assert result.total_stock == 4034
    assert result.unit_price == 54.66
    assert result.lead_time_days == 140
    assert result.lifecycle_status == "在售"
    assert result.manufacturer == "STMicroelectronics"


@pytest.mark.asyncio
async def test_digikey_query_returns_not_found_for_empty_products():
    source = DigiKeySource(client_id="test-id", client_secret="test-secret")
    digi_resp = FakeResponse2({"Products": []})
    fake = FakeDigiKeyClient({"/products/v4/search/keyword": digi_resp})
    source._client = fake

    result = await source.query_by_mpn("NO_SUCH")

    assert result.match_status == "not_found"
    assert result.is_available is False


# ──────────────────────────────────────────────
# 多源合并测试
# ──────────────────────────────────────────────
from app.services.supply_data import SupplyDataService, AggregatedResult


class StubSource:
    def __init__(self, name, result=None, configured=True):
        self.source_name = name
        self._result = result
        self._configured = configured

    @property
    def is_configured(self):
        return self._configured

    async def query_by_mpn(self, mpn):
        if isinstance(self._result, Exception):
            raise self._result
        if self._result is None:
            return SourceResult(
                source=self.source_name,
                mpn_queried=mpn,
                match_status="not_found",
            )
        return self._result


def make_hit(name, stock=0, price=None, lead=None, lifecycle="Unknown"):
    return SourceResult(
        source=name, mpn_queried="TEST",
        total_stock=stock, unit_price=price, lead_time_days=lead,
        lifecycle_status=lifecycle, currency="CNY" if name in ("lcsc","digikey","guanxintai") else "USD",
        match_status="hit", is_available=True,
        raw_summary=f"{name}:测试",
    )


@pytest.mark.asyncio
async def test_merge_best_picks_max_stock_min_price_min_lead():
    service = SupplyDataService()
    service._lcsc = StubSource("lcsc", make_hit("lcsc", stock=120, price=6.50, lifecycle="Unknown"))
    service._mouser = StubSource("mouser", make_hit("mouser", stock=18058, price=4.60, lead=7, lifecycle=""))
    service._digikey = StubSource("digikey", make_hit("digikey", stock=4034, price=54.66, lead=140, lifecycle="在售"))
    service._guanxintai = StubSource("guanxintai", make_hit("guanxintai", stock=33688, price=6.98))
    service._enabled_sources = [service._lcsc, service._mouser, service._digikey, service._guanxintai]
    service._all_sources = service._enabled_sources

    result = await service.query_one("TEST")

    assert result.is_available is True
    assert result.total_stock == 33688  # max
    assert result.unit_price == 4.60  # min (Mouser USD)
    assert result.lead_time_days == 7  # min
    assert result.lifecycle_status == "在售"  # DigiKey priority
    assert result.supplier_count == 4
    assert result.match_status == "hit"
    assert len(result.sources) == 4


@pytest.mark.asyncio
async def test_merge_all_not_found_returns_unavailable():
    service = SupplyDataService()
    service._lcsc = StubSource("lcsc", None)
    service._mouser = StubSource("mouser", None)
    service._enabled_sources = [service._lcsc, service._mouser]

    result = await service.query_one("NONE")

    assert result.is_available is False
    assert result.match_status == "not_found"
    assert result.total_stock == 0


@pytest.mark.asyncio
async def test_merge_mixed_some_hit_some_not():
    service = SupplyDataService()
    service._lcsc = StubSource("lcsc", make_hit("lcsc", stock=120, price=6.50))
    service._mouser = StubSource("mouser", None)
    service._digikey = StubSource("digikey", None)
    service._enabled_sources = [service._lcsc, service._mouser, service._digikey]

    result = await service.query_one("MIX")

    assert result.is_available is True
    assert result.total_stock == 120
    assert result.supplier_count == 1


@pytest.mark.asyncio
async def test_query_one_keeps_source_exception_as_auditable_source_result():
    service = SupplyDataService()
    service._lcsc = StubSource("lcsc", make_hit("lcsc", stock=120, price=6.50))
    service._mouser = StubSource("mouser", RuntimeError("mouser 503"))
    service._enabled_sources = [service._lcsc, service._mouser]

    result = await service.query_one("MIXED")

    assert result.is_available is True
    assert result.total_stock == 120
    failed_sources = [source for source in result.sources if source.source == "mouser"]
    assert failed_sources
    assert failed_sources[0].match_status == "request_failed"
    assert "mouser 503" in failed_sources[0].error_reason


def test_source_configured_flags_respect_enabled_settings(monkeypatch):
    from app.services.sources.lcsc import LCSCSource
    from app.services.sources.mouser import MouserSource
    from app.services.sources.digikey import DigiKeySource
    from app.services.sources.guanxintai import GuanxintaiSource

    import app.services.sources.lcsc as lcsc_module
    import app.services.sources.mouser as mouser_module
    import app.services.sources.digikey as digikey_module
    import app.services.sources.guanxintai as guanxintai_module

    monkeypatch.setattr(lcsc_module.settings, "lcsc_enabled", False)
    monkeypatch.setattr(mouser_module.settings, "mouser_enabled", False)
    monkeypatch.setattr(digikey_module.settings, "digikey_enabled", False)
    monkeypatch.setattr(guanxintai_module.settings, "guanxintai_enabled", False)

    assert LCSCSource().is_configured is False
    assert MouserSource(api_key="configured-key").is_configured is False
    assert DigiKeySource(client_id="configured-id", client_secret="configured-secret").is_configured is False
    assert GuanxintaiSource().is_configured is False
