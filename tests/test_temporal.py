import json
from pathlib import Path

import pytest

from app.llm import FailingProvider
from app.repositories import JsonRepository
from app.routing import classify_question
from app.schemas import ChatRequest, QuestionRoute
from app.services import ChatService, HybridRetriever
from app.temporal import development_budget_trend


ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "data/curated/districts.json").read_text(encoding="utf-8"))
REPOSITORY = JsonRepository(ROOT / "data/curated/districts.json")


def periods(slug: str) -> dict:
    return next(item for item in DATA["districts"] if item["slug"] == slug)["accountability_periods"]


def test_temporal_calculation_is_deterministic():
    trend = development_budget_trend(periods("vehari"))
    assert trend["periods"][0]["utilization_pct"] == 72.46
    assert trend["periods"][1]["utilization_pct"] == 97.73
    assert trend["change_percentage_points"] == 25.27
    assert trend["direction"] == "increased"


def test_above_one_hundred_utilization_is_preserved_with_warning():
    trend = development_budget_trend(periods("rajanpur"))
    assert trend["periods"][0]["utilization_pct"] == 112.11
    assert trend["change_percentage_points"] == -99.21
    assert trend["warnings"]


def test_temporal_question_has_dedicated_route():
    assert classify_question("How much improvement came from last year in Vehari?") == QuestionRoute.TEMPORAL_COMPARISON


def test_json_repository_returns_source_linked_trend():
    trend = REPOSITORY.development_trend("multan")
    assert trend["change_percentage_points"] == 24.92
    assert trend["citation"]["evidence_id"] == "multan-development-trend"


@pytest.mark.asyncio
async def test_temporal_chat_uses_calculated_facts_and_citation():
    service = ChatService(REPOSITORY, HybridRetriever(REPOSITORY, None), FailingProvider())
    response = await service.answer(
        ChatRequest(question="How did development utilization change from last year?", districts=["vehari"])
    )
    assert response.route == QuestionRoute.TEMPORAL_COMPARISON
    assert response.mode == "extractive"
    assert "25.27 percentage points" in response.answer
    assert response.citations[0].evidence_id == "vehari-development-trend"
