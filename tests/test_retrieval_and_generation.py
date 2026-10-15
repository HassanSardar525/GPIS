import json
from pathlib import Path

import pytest

from app.config import Settings
from app.llm import FailingProvider, GeminiProvider, GeneratedAnswer, GroqProvider, validate_generated_answer
from app.repositories import JsonRepository
from app.routing import classify_question
from app.schemas import ChatRequest, QuestionRoute
from app.services import ChatService, HybridRetriever


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = JsonRepository(ROOT / "data/curated/districts.json")


class ValidProvider:
    name = "test"

    async def generate(self, question, evidence, structured_context):
        evidence_id = evidence[0].id
        return GeneratedAnswer(f"The retrieved record supports this answer [{evidence_id}].", [evidence_id], [])


class InventedCitationProvider:
    name = "test"

    async def generate(self, question, evidence, structured_context):
        return GeneratedAnswer("An unsupported claim [invented].", ["invented"], [])


def test_evaluation_fixture_has_phase_three_cases_and_expected_routes():
    cases = json.loads((ROOT / "tests/fixtures/rag_evaluation.json").read_text(encoding="utf-8"))
    assert len(cases) == 63
    for case in cases:
        assert classify_question(case["question"]).value == case["route"], case["id"]


def test_agent_evaluation_fixture_covers_phase_one_scenarios():
    cases = json.loads((ROOT / "tests/fixtures/agent_evaluation.json").read_text(encoding="utf-8"))
    ids = {case["id"] for case in cases}

    assert len(cases) == 12
    assert {"greeting", "score-fact", "comparison", "memory-follow-up", "prompt-injection"} <= ids
    for case in cases:
        if case["abstained"]:
            assert classify_question(case["question"]) == QuestionRoute.UNSUPPORTED, case["id"]


def test_direct_score_question_routes_to_exact_fact():
    assert classify_question("What is Multan's education score?") == QuestionRoute.EXACT_FACT


def test_structured_fact_retrieval_uses_exact_observation():
    results = REPOSITORY.fact_search("What is female literacy?", ["multan"], 6)
    assert results[0].id == "fact-multan-literacy_female_pct"
    assert "55.27%" in results[0].text
    assert results[0].citation.passage == results[0].text


def test_hybrid_retrieval_is_district_scoped_and_deduplicated():
    retriever = HybridRetriever(REPOSITORY, embedder=None)
    results = retriever.retrieve(ChatRequest(question="literacy and education", districts=["multan"]), QuestionRoute.EXACT_FACT)
    assert results
    assert all(item.district_slug in {"multan", "project"} for item in results)
    assert any(item.district_slug == "multan" for item in results)
    assert len({item.id for item in results}) == len(results)


def test_generated_answer_rejects_invented_citation():
    evidence = REPOSITORY.fact_search("literacy", ["multan"], 1)
    generated = GeneratedAnswer("The value is 61.41%. [invented-source]", ["invented-source"], [])
    assert validate_generated_answer(generated, evidence) is False


def test_generated_answer_accepts_only_retrieved_markers():
    evidence = REPOSITORY.fact_search("literacy", ["multan"], 1)
    evidence_id = evidence[0].id
    generated = GeneratedAnswer(f"The value is 61.41% [{evidence_id}].", [evidence_id], [])
    assert validate_generated_answer(generated, evidence) is True


@pytest.mark.asyncio
async def test_missing_groq_key_uses_extractive_fallback():
    service = ChatService(REPOSITORY, HybridRetriever(REPOSITORY, None), FailingProvider())
    response = await service.answer(ChatRequest(question="What is literacy?", districts=["multan"]))
    assert response.mode == "extractive"
    assert response.citations
    assert response.abstained is False


@pytest.mark.asyncio
async def test_valid_grounded_provider_answer_uses_groq_mode():
    service = ChatService(REPOSITORY, HybridRetriever(REPOSITORY, None), ValidProvider())
    response = await service.answer(ChatRequest(question="What is literacy?", districts=["multan"]))
    assert response.mode == "groq"
    assert response.citations[0].evidence_id.startswith("fact-multan-")


@pytest.mark.asyncio
async def test_invalid_provider_citation_always_falls_back():
    service = ChatService(REPOSITORY, HybridRetriever(REPOSITORY, None), InventedCitationProvider())
    response = await service.answer(ChatRequest(question="What is literacy?", districts=["multan"]))
    assert response.mode == "extractive"
    assert all(citation.evidence_id != "invented" for citation in response.citations)


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [429, 503])
async def test_groq_retries_temporary_failures_then_raises(monkeypatch, status_code):
    calls = 0

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            nonlocal calls
            calls += 1
            import httpx

            return httpx.Response(status_code, request=httpx.Request("POST", "https://example.test"))

    monkeypatch.setattr("app.llm.httpx.AsyncClient", lambda **kwargs: FakeClient())
    provider = GroqProvider("key", "model", "https://example.test", timeout_seconds=0.01)
    with pytest.raises(RuntimeError):
        await provider.generate("question", REPOSITORY.fact_search("literacy", ["multan"], 1), "")
    assert calls == 2


@pytest.mark.asyncio
async def test_groq_retries_timeout_then_raises(monkeypatch):
    calls = 0

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            nonlocal calls
            calls += 1
            import httpx

            raise httpx.ReadTimeout("request timed out")

    async def no_sleep(_delay):
        return None

    monkeypatch.setattr("app.llm.httpx.AsyncClient", lambda **kwargs: FakeClient())
    monkeypatch.setattr("app.llm.asyncio.sleep", no_sleep)
    provider = GroqProvider("key", "model", "https://example.test", timeout_seconds=0.01)

    with pytest.raises(RuntimeError):
        await provider.generate("question", REPOSITORY.fact_search("literacy", ["multan"], 1), "")

    assert calls == 2


@pytest.mark.asyncio
async def test_unsupported_question_abstains_without_citations():
    service = ChatService(REPOSITORY, HybridRetriever(REPOSITORY, None), FailingProvider())
    response = await service.answer(ChatRequest(question="What is tomorrow's weather?", districts=["multan"]))
    assert response.mode == "abstained"
    assert response.citations == []
    assert response.abstained is True


@pytest.mark.asyncio
async def test_gemini_provider_parses_json_and_citations(monkeypatch):
    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            import httpx
            content = json.dumps({
                "answer": "Multan has a total literacy rate of 60.1% [fact-multan-literacy_total_pct].",
                "evidence_ids": ["fact-multan-literacy_total_pct"],
                "warnings": [],
            })
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": content}}]},
                request=httpx.Request("POST", "https://example.test"),
            )

    monkeypatch.setattr("app.llm.httpx.AsyncClient", lambda **kwargs: FakeClient())
    provider = GeminiProvider("key", "gemini-1.5-flash", "https://example.test", timeout_seconds=0.1)
    evidence = REPOSITORY.fact_search("literacy", ["multan"], 1)
    result = await provider.generate("What is literacy?", evidence, "")

    assert result.evidence_ids == ["fact-multan-literacy_total_pct"]
    assert validate_generated_answer(result, evidence) is True


@pytest.mark.asyncio
async def test_gemini_provider_retries_and_raises_on_error(monkeypatch):
    calls = 0

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            nonlocal calls
            calls += 1
            import httpx
            return httpx.Response(500, request=httpx.Request("POST", "https://example.test"))

    async def no_sleep(_delay):
        return None

    monkeypatch.setattr("app.llm.httpx.AsyncClient", lambda **kwargs: FakeClient())
    monkeypatch.setattr("app.llm.asyncio.sleep", no_sleep)
    provider = GeminiProvider("key", "gemini-1.5-flash", "https://example.test", timeout_seconds=0.1)
    evidence = REPOSITORY.fact_search("literacy", ["multan"], 1)

    with pytest.raises(RuntimeError):
        await provider.generate("What is literacy?", evidence, "")

    assert calls == 2
