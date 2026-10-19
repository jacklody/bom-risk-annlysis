from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_risk_chain_dashboard_returns_core_sections():
    response = client.get("/api/risk-chain/dashboard")

    assert response.status_code == 200
    data = response.json()

    assert set(data.keys()) == {
        "summary",
        "categoryFilters",
        "signals",
        "materialChains",
        "bomImpacts",
        "strategies",
    }
    assert data["summary"]["highRiskBomCount"] >= 0
    assert data["summary"]["affectedItemCount"] >= 0
    assert data["summary"]["affectedCategoryCount"] >= 0
    assert data["summary"]["highConfidenceSignalCount"] >= 0
    assert data["summary"]["pendingActionCount"] >= 0
    assert data["summary"]["categoryCoverageCount"] >= 8


def test_risk_chain_dashboard_contains_traceable_sample_signal():
    response = client.get("/api/risk-chain/dashboard")

    assert response.status_code == 200
    data = response.json()
    signal = data["signals"][0]

    assert signal["id"]
    assert signal["title"]
    assert signal["signalType"] in ["price", "shortage", "tariff", "trade", "ban", "disaster", "strike", "shutdown"]
    assert signal["sourceLevel"] in ["S", "A", "B", "C"]
    assert signal["sourceType"]
    assert signal["sourceUrl"].startswith("https://")
    assert 0 <= signal["confidenceScore"] <= 100
    assert isinstance(signal["linkedMaterials"], list)
    assert isinstance(signal["linkedCategories"], list)


def test_risk_chain_dashboard_contains_material_chain_and_bom_impact():
    response = client.get("/api/risk-chain/dashboard")

    assert response.status_code == 200
    data = response.json()

    material_chain = data["materialChains"][0]
    assert material_chain["category"]
    assert material_chain["group"]
    assert isinstance(material_chain["nodes"], list)
    assert len(material_chain["nodes"]) >= 2
    assert material_chain["nodes"][0]["name"]
    assert material_chain["sourceLinks"]
    assert material_chain["sourceLinks"][0]["url"].startswith("https://")

    impact = data["bomImpacts"][0]
    assert impact["itemCode"]
    assert impact["category"]
    assert impact["riskLevel"] in ["red", "orange", "yellow", "green"]
    assert impact["reasonSummary"]
    assert isinstance(impact["linkedSignalIds"], list)
    assert isinstance(impact["linkedMaterials"], list)
    assert impact["impactBreakdown"]


def test_risk_chain_dashboard_contains_strategy_actions():
    response = client.get("/api/risk-chain/dashboard")

    assert response.status_code == 200
    data = response.json()
    strategy = data["strategies"][0]

    assert strategy["id"]
    assert strategy["group"]
    assert strategy["strategyType"] in ["price", "lead_time", "alternative", "trade", "watch"]
    assert strategy["title"]
    assert strategy["detail"]
    assert strategy["priority"] in ["P0", "P1", "P2"]
    assert strategy["ownerRole"] in ["采购", "研发", "项目经理", "供应链"]


def test_risk_chain_dashboard_covers_non_pcb_categories():
    response = client.get("/api/risk-chain/dashboard")

    assert response.status_code == 200
    data = response.json()
    groups = {chain["group"] for chain in data["materialChains"]}
    filter_keys = {item["key"] for item in data["categoryFilters"]}

    assert {"semiconductor", "passive", "connector_cable", "battery_power", "display_opto", "mechanical_thermal"}.issubset(groups)
    assert {"all", "semiconductor", "passive", "connector_cable", "battery_power"}.issubset(filter_keys)
