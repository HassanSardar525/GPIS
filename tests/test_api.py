from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.repositories import JsonRepository


ROOT = Path(__file__).resolve().parents[1]
SETTINGS = Settings(curated_data_path=ROOT / "data/curated/districts.json")
CLIENT = TestClient(create_app(settings=SETTINGS, repository=JsonRepository(SETTINGS.curated_data_path)))


def test_health_contract_reports_fallbacks():
    response = CLIENT.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["repository"] == "json"
    assert response.json()["groq"] == "fallback"
    assert response.headers["X-Request-ID"]


def test_district_list_contract_is_versioned():
    response = CLIENT.get("/api/v1/districts")
    assert response.status_code == 200
    assert len(response.json()["districts"]) == 10


def test_invalid_district_returns_structured_error():
    response = CLIENT.get("/api/v1/districts/not-a-district")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "district_not_found"
    assert response.json()["error"]["request_id"]


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
    assert body["citations"][0]["evidence_id"] == "fact-multan-literacy_total_pct"


def test_chat_rejects_unknown_district_before_retrieval():
    response = CLIENT.post("/api/v1/chat", json={"question": "What is literacy?", "districts": ["unknown"]})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "district_not_found"


def test_development_budget_trend_contract():
    response = CLIENT.get("/api/v1/districts/layyah/trends/development-budget")
    assert response.status_code == 200
    body = response.json()
    assert body["metric"] == "development_budget_utilization_pct"
    assert body["change_percentage_points"] == 65.72
    assert body["citation"]["evidence_id"] == "layyah-development-trend"
