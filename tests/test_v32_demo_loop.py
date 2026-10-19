"""v3.2 完整可演示闭环测试：样例BOM上传 → 分析 → 人工事件 → 重分析。"""

import pathlib

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal, init_db
from app.main import app
from app.models.bom import BomItem, BomProject
from app.models.event import MarketEvent

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    init_db()
    db = SessionLocal()
    db.query(BomItem).delete()
    db.query(BomProject).delete()
    db.query(MarketEvent).delete()
    db.commit()
    db.close()
    yield


def _sample_bom_path() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[1] / "demo" / "sample-bom-v32.csv"


def _upload_sample_bom() -> int:
    sample_path = _sample_bom_path()
    with sample_path.open("rb") as f:
        resp = client.post(
            "/api/bom/upload",
            files={"file": (sample_path.name, f, "text/csv")},
            data={"project_name": "v3.2演示BOM"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_items"] >= 6
    return data["upload_id"]


def _find_item(result: dict, part_prefix: str) -> dict:
    for item in result["items"]:
        if (item.get("raw_part_number") or "").startswith(part_prefix):
            return item
    raise AssertionError(f"未找到物料: {part_prefix}")


def test_v32_demo_loop_upload_manual_event_and_reanalyze():
    upload_id = _upload_sample_bom()

    first_resp = client.post(f"/api/risk/analyze/{upload_id}")
    assert first_resp.status_code == 200
    first_result = first_resp.json()
    assert first_result["total_items"] >= 6

    mlcc_before = _find_item(first_result, "C3225")
    assert mlcc_before["v32_category"] == "high_cap_mlcc"
    assert "v32_risk_level" in mlcc_before
    assert "v32_primary_track" in mlcc_before
    assert isinstance(mlcc_before["v32_evidence_chain"], list)

    manual_payload = {
        "title": "TDK高容MLCC缺货涨价通知",
        "category": "high_cap_mlcc",
        "brand": "TDK",
        "mpn": "C3225X5R1A226M250AC",
        "event_type": "price_increase",
        "increase_max_pct": 20,
        "lead_time_weeks": 16,
        "shortage_confirmed": True,
        "source_url": "file://demo/tdk-high-cap-mlcc-notice.pdf",
        "confirmed_by_user": True,
    }
    event_resp = client.post("/api/events/manual", json=manual_payload)
    assert event_resp.status_code == 200
    event_result = event_resp.json()
    assert event_result["status"] == "ok"
    assert event_result["review_recommendation"] in {"auto_confirm", "manual_review"}
    assert event_result["confidence_reason"]

    second_resp = client.post(f"/api/risk/analyze/{upload_id}")
    assert second_resp.status_code == 200
    second_result = second_resp.json()

    mlcc_after = _find_item(second_result, "C3225")
    assert mlcc_after["v32_category"] == "high_cap_mlcc"
    assert mlcc_after["v32_risk_level"] in {"yellow", "orange", "red", "gray", "green"}
    assert mlcc_after["v32_primary_track"] in {"demand_supply", "material", "information_insufficient", "buffer"}
    assert mlcc_after["v32_evidence_chain"]
    assert mlcc_after["v32_action_suggestion"]
    assert any(node["type"] == "market_event" for node in mlcc_after["v32_evidence_chain"])
    assert mlcc_after["matched_events"]
