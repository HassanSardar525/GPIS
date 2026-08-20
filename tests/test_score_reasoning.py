from pathlib import Path

import pytest

from app.llm import FailingProvider
from app.repositories import JsonRepository
from app.routing import classify_question
from app.schemas import ChatRequest, QuestionRoute
from app.services import ChatService, HybridRetriever
ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = JsonRepository(ROOT / "data/curated/districts.json")


def test_score_reason_route_is_distinct_from_formula_route():
    assert classify_question("Why did Multan receive this education score?") == QuestionRoute.SCORE_EXPLANATION
    assert classify_question("How is the education score calculated?") == QuestionRoute.METHODOLOGY


def test_score_explanation_contains_stored_result_and_components():
    results = REPOSITORY.score_search("Why is the health score this value?", ["layyah"], "health", 6)
    assert results[0].id == "score-layyah-health-prototype-v1"
    assert "93.8" in results[0].text
    assert "per 100,000" in results[0].text


def test_project_knowledge_is_global_when_district_filter_is_present():
    results = REPOSITORY.keyword_search("GPIS RAG architecture", ["multan"], None, None, 6)
    assert any(item.id == "gpis-rag-architecture" for item in results)


@pytest.mark.asyncio
async def test_score_explanation_fallback_is_cited_and_deterministic():
    service = ChatService(REPOSITORY, HybridRetriever(REPOSITORY, None), FailingProvider())
    response = await service.answer(
        ChatRequest(question="Why did Vehari receive its accountability score?", districts=["vehari"])
    )
    assert response.route == QuestionRoute.SCORE_EXPLANATION
    assert "98.5" in response.answer
    assert response.citations[0].evidence_id == "score-vehari-accountability-prototype-v1"


@pytest.mark.asyncio
async def test_project_question_uses_citable_project_evidence():
    service = ChatService(REPOSITORY, HybridRetriever(REPOSITORY, None), FailingProvider())
    response = await service.answer(ChatRequest(question="What is the GPIS project?"))
    assert response.route == QuestionRoute.PROJECT
    assert any(citation.evidence_id == "gpis-project-scope" for citation in response.citations)
    assert response.abstained is False
