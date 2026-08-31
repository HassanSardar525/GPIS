from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.repositories import JsonRepository
from app.database.repository import PostgresRepository


ROOT = Path(__file__).resolve().parents[1]
SETTINGS = Settings(curated_data_path=ROOT / "data/curated/districts.json")
CLIENT = TestClient(create_app(settings=SETTINGS, repository=JsonRepository(SETTINGS.curated_data_path)))


def test_health_contract_reports_fallbacks():
    response = CLIENT.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["repository"] == "json"
    assert response.json()["groq"] == "fallback"
    assert response.json()["phoenix"] == "disabled"
    assert response.headers["X-Request-ID"]


def test_district_list_contract_is_versioned():
    response = CLIENT.get("/api/v1/districts")
    assert response.status_code == 200
    assert len(response.json()["districts"]) == 10
    body = response.json()
    detail = body["districts"][0]["score_details"]["health"]
    assert detail["version"] == "prototype-v1"
    assert detail["coverage"] == 1.0
    assert detail["confidence"] == 0.8125
    assert detail["reporting_period"]
    assert "directness" in detail["confidence_factors"]
    assert body["metadata"]["active_score_version"] == "prototype-v1"
    assert body["metadata"]["evidence_v2_gate"]["activation_ready"] is False


def test_district_and_ranking_preserve_numeric_scores_and_add_details():
    district = CLIENT.get("/api/v1/districts/multan").json()
    ranking = CLIENT.get("/api/v1/rankings?category=health").json()["rankings"][0]

    assert isinstance(district["derived"]["scores"]["health"], float)
    assert district["score_details"]["health"]["score"] == district["derived"]["scores"]["health"]
    assert district["score_details"]["health"]["calculated_at"] == "2026-08-20T00:00:00+00:00"
    assert ranking["score_detail"]["score"] == ranking["score"]
    assert ranking["score_detail"]["warnings"]


def test_invalid_district_returns_structured_error():
    response = CLIENT.get("/api/v1/districts/not-a-district")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "district_not_found"
    assert response.json()["error"]["request_id"]


def test_evidence_v2_cannot_be_selected_before_activation_gate_passes():
    with pytest.raises(ValueError, match="remains staged"):
        JsonRepository(SETTINGS.curated_data_path, "evidence-v2")
    with pytest.raises(ValueError, match="remains staged"):
        PostgresRepository("postgresql+psycopg://unused", "evidence-v2")


def test_invalid_ranking_category_returns_structured_error():
    response = CLIENT.get("/api/v1/rankings?category=corruption")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_category"


def test_blank_chat_question_fails_contract():
    response = CLIENT.post("/api/v1/chat", json={"question": "   ", "districts": ["multan"]})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_chat_compatibility_alias_and_citations():
    response = CLIENT.post("/api/v1/chat", json={"question": "What is literacy?", "district": "multan"})
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "extractive"
    citation = body["citations"][0]
    assert citation["evidence_id"] == "fact-multan-literacy_total_pct"
    assert {"source_id", "publisher", "title", "period", "url", "locator"} <= citation.keys()
    assert "Total literacy for Multan is 61.41%." == citation["passage"]
    assert "local_file" not in citation


def test_session_lifecycle_contract_and_deletion():
    session_id = "session-api-lifecycle"
    response = CLIENT.post(
        "/api/v1/chat",
        json={"question": "Hello", "session_id": session_id},
    )
    assert response.status_code == 200
    assert response.json()["session_id"] == session_id

    status = CLIENT.get(f"/api/v1/sessions/{session_id}")
    assert status.status_code == 200
    assert status.json()["message_count"] == 1
    assert status.json()["status"] == "active"

    deleted = CLIENT.delete(f"/api/v1/sessions/{session_id}")
    assert deleted.status_code == 200
    assert deleted.json() == {"session_id": session_id, "deleted": True}
    assert CLIENT.get(f"/api/v1/sessions/{session_id}").status_code == 404


def test_session_identifier_rejects_unsafe_characters():
    response = CLIENT.post(
        "/api/v1/chat",
        json={"question": "Hello", "session_id": "unsafe session/id"},
    )
    assert response.status_code == 422


def test_chat_rejects_unknown_district_before_retrieval():
    response = CLIENT.post("/api/v1/chat", json={"question": "What is literacy?", "districts": ["unknown"]})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "district_not_found"


def test_chat_comparison_contract_is_structured_and_backward_compatible():
    response = CLIENT.post(
        "/api/v1/chat",
        json={
            "question": "Compare the overall scores of Multan and Bahawalpur.",
            "districts": ["multan", "bahawalpur"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["answer"], str)
    assert body["comparison"]["category"] == "overall"
    assert body["comparison"]["score_delta"] == 43.3
    assert body["comparison"]["rank_delta"] == -7
    assert len(body["comparison"]["components"]) == 3
    assert body["comparison"]["districts"][0]["score_detail"]["version"] == "prototype-v1"
    assert any("different reporting periods" in item for item in body["warnings"])


def test_development_budget_trend_contract():
    response = CLIENT.get("/api/v1/districts/layyah/trends/development-budget")
    assert response.status_code == 200
    body = response.json()
    assert body["metric"] == "development_budget_utilization_pct"
    assert body["change_percentage_points"] == 65.72
    assert body["citation"]["evidence_id"] == "layyah-development-trend"
    assert body["citation"]["passage"]


def test_health_capacity_trend_contract_preserves_periods_and_citations():
    response = CLIENT.get("/api/v1/districts/multan/trends/health-capacity?facility=hospitals")
    assert response.status_code == 200
    body = response.json()
    assert body["facility"] == "hospitals"
    assert body["periods"][0]["snapshot_date"] == "2023-01-01"
    assert body["periods"][1]["snapshot_date"] == "2023-12-31"
    assert body["count_change"] == -2
    assert body["bed_change"] == 1470
    assert body["periods"][0]["citation"]["evidence_id"] == "multan-health-capacity-2023-01-01"


def test_health_capacity_trend_rejects_unknown_facility():
    response = CLIENT.get("/api/v1/districts/multan/trends/health-capacity?facility=doctors")
    assert response.status_code == 422
