"""Application services for districts, hybrid retrieval, and grounded chat."""

from __future__ import annotations

import time
import uuid
from collections import defaultdict

from app.embeddings import Embedder
from app.llm import LLMProvider, validate_generated_answer
from app.repositories import GPISRepository
from app.routing import classify_question, expand_semantic_query
from app.schemas import (
    AnswerMode,
    ChatRequest,
    ChatResponse,
    Citation,
    QuestionRoute,
    RetrievedEvidence,
)


METHODOLOGY_TEXT = {
    "education": "Education is the mean of total literacy, female literacy, and 100 minus the male-female literacy gap.",
    "health": "Health is a min-max normalized comparison of listed public health facilities per 100,000 residents within the fixed five-district cohort.",
    "accountability": "Accountability is the mean of overall budget utilization and development-budget utilization.",
    "overall": "Overall is the equal-weight mean of education, health, and accountability scores.",
}


class DistrictService:
    def __init__(self, repository: GPISRepository):
        self.repository = repository

    def list_districts(self) -> list[dict]:
        return self.repository.list_districts()

    def get_district(self, slug: str) -> dict:
        return self.repository.get_district(slug)

    def rankings(self, category: str) -> list[dict]:
        return self.repository.rankings(category)


class HybridRetriever:
    def __init__(
        self,
        repository: GPISRepository,
        embedder: Embedder | None,
        semantic_threshold: float = 0.35,
        rrf_k: int = 60,
    ):
        self.repository = repository
        self.embedder = embedder
        self.semantic_threshold = semantic_threshold
        self.rrf_k = rrf_k

    def retrieve(self, request: ChatRequest, route: QuestionRoute, limit: int = 6) -> list[RetrievedEvidence]:
        districts = request.selected_districts()
        facts = self.repository.fact_search(request.question, districts, limit)
        keyword = facts + self.repository.keyword_search(
            request.question, districts, request.category, request.period, limit
        )
        if route == QuestionRoute.METHODOLOGY:
            method_query = request.category or next(
                (category for category in ("education", "health", "accountability") if category in request.question.casefold()),
                "education health accountability",
            )
            keyword += self.repository.keyword_search(method_query, districts, request.category, request.period, limit)
        elif route == QuestionRoute.COMPARISON and not keyword:
            keyword += self.repository.keyword_search(
                "education health accountability", districts, request.category, request.period, limit
            )
        keyword = list({item.id: item for item in keyword}.values())[:limit]
        vector: list[RetrievedEvidence] = []
        if self.embedder and route not in {QuestionRoute.UNSUPPORTED, QuestionRoute.METHODOLOGY}:
            query_vector = self.embedder.embed([expand_semantic_query(request.question)])[0]
            vector = self.repository.vector_search(
                query_vector, districts, request.category, request.period, limit
            )

        combined: dict[str, RetrievedEvidence] = {}
        scores: defaultdict[str, float] = defaultdict(float)
        for rank, item in enumerate(keyword, start=1):
            item.keyword_rank = rank
            combined[item.id] = item
            scores[item.id] += 1 / (self.rrf_k + rank)
        for rank, item in enumerate(vector, start=1):
            if item.semantic_similarity is not None and item.semantic_similarity < self.semantic_threshold:
                continue
            item.vector_rank = rank
            if item.id in combined:
                combined[item.id].vector_rank = rank
                combined[item.id].semantic_similarity = item.semantic_similarity
            else:
                combined[item.id] = item
            scores[item.id] += 1 / (self.rrf_k + rank)

        ordered = sorted(combined.values(), key=lambda item: (-scores[item.id], item.id))
        for item in ordered:
            item.rrf_score = round(scores[item.id], 6)
        return ordered[:limit]


class ChatService:
    def __init__(
        self,
        repository: GPISRepository,
        retriever: HybridRetriever,
        provider: LLMProvider,
    ):
        self.repository = repository
        self.retriever = retriever
        self.provider = provider

    async def answer(self, request: ChatRequest) -> ChatResponse:
        started = time.perf_counter()
        trace_id = str(uuid.uuid4())
        route = classify_question(request.question)
        for slug in request.selected_districts():
            self.repository.get_district(slug)
        if route == QuestionRoute.UNSUPPORTED:
            response = ChatResponse(
                answer=(
                    "I could not find support for that question in the GPIS evidence. "
                    "Ask about district literacy, health facilities, budgets, scores, rankings, or sources."
                ),
                mode=AnswerMode.ABSTAINED,
                route=route,
                citations=[],
                warnings=["The question is outside the current evidence scope."],
                trace_id=trace_id,
                abstained=True,
            )
            self._record_trace(request, response, [], started)
            return response

        evidence = self.retriever.retrieve(request, route)
        if not evidence:
            response = ChatResponse(
                answer="I could not find enough evidence in the current sources to answer that question.",
                mode=AnswerMode.ABSTAINED,
                route=route,
                citations=[],
                warnings=["No evidence passed the retrieval threshold."],
                trace_id=trace_id,
                abstained=True,
            )
            self._record_trace(request, response, [], started)
            return response

        structured_context = self._structured_context(request, route)
        try:
            generated = await self.provider.generate(request.question, evidence, structured_context)
            if validate_generated_answer(generated, evidence):
                selected = [item for item in evidence if item.id in set(generated.evidence_ids)]
                response = ChatResponse(
                    answer=generated.answer,
                    mode=AnswerMode.GROQ,
                    route=route,
                    citations=self._citations(selected),
                    warnings=generated.warnings + self._standard_warnings(route, request.question),
                    trace_id=trace_id,
                    abstained=False,
                )
                self._record_trace(request, response, evidence, started)
                return response
        except Exception:
            pass

        response = ChatResponse(
            answer=self._fallback_answer(request, route, evidence),
            mode=AnswerMode.EXTRACTIVE,
            route=route,
            citations=self._citations(evidence[:3]),
            warnings=["The LLM was unavailable or returned invalid citations."] + self._standard_warnings(route, request.question),
            trace_id=trace_id,
            abstained=False,
        )
        self._record_trace(request, response, evidence, started)
        return response

    def _structured_context(self, request: ChatRequest, route: QuestionRoute) -> str:
        selected = request.selected_districts()
        if route not in {QuestionRoute.EXACT_FACT, QuestionRoute.COMPARISON, QuestionRoute.METHODOLOGY}:
            return ""
        if selected:
            records = [self.repository.get_district(slug) for slug in selected]
        else:
            records = [self.repository.get_district(item["slug"]) for item in self.repository.list_districts()]
        lines = []
        if route == QuestionRoute.METHODOLOGY:
            lines.extend(f"{name}_formula={formula}" for name, formula in METHODOLOGY_TEXT.items())
        for district in records:
            scores = district["derived"]["scores"]
            lines.append(
                f"{district['name']}: population={district['population_2023']}; "
                f"education_score={scores['education']}; health_score={scores['health']}; "
                f"accountability_score={scores['accountability']}; overall_score={scores['overall']}"
            )
        return "\n".join(lines)

    def _fallback_answer(
        self,
        request: ChatRequest,
        route: QuestionRoute,
        evidence: list[RetrievedEvidence],
    ) -> str:
        if route == QuestionRoute.METHODOLOGY:
            category = next(
                (name for name in ("education", "health", "accountability", "overall") if name in request.question.casefold()),
                "overall",
            )
            markers = " ".join(f"[{item.id}]" for item in evidence[:3])
            return f"{METHODOLOGY_TEXT[category]} {markers}".strip()
        if route == QuestionRoute.COMPARISON and any(
            word in request.question.casefold() for word in ("rank", "best", "worst", "overall", "score")
        ):
            category = next(
                (name for name in ("education", "health", "accountability") if name in request.question.casefold()),
                "overall",
            )
            ranked = self.repository.rankings(category)
            evidence_by_slug = {item.district_slug: item for item in evidence[:3]}
            statements = []
            for item in ranked[:3]:
                citation = evidence_by_slug.get(item["slug"])
                if citation:
                    statements.append(f"Rank {item['rank']}: {item['name']} scores {item['score']} [{citation.id}].")
            if statements:
                return " ".join(statements)
        return " ".join(f"{item.text} [{item.id}]" for item in evidence[:3])

    @staticmethod
    def _citations(evidence: list[RetrievedEvidence]) -> list[Citation]:
        seen = set()
        citations = []
        for item in evidence:
            if item.id not in seen:
                citations.append(item.citation)
                seen.add(item.id)
        return citations

    @staticmethod
    def _standard_warnings(route: QuestionRoute, question: str) -> list[str]:
        warnings = []
        if route == QuestionRoute.COMPARISON:
            warnings.append("District comparisons describe available indicators, not causation by an individual politician.")
        if "corruption" in question.casefold():
            warnings.append("An audit observation is not, by itself, proof of corruption or fraud.")
        return warnings

    def _record_trace(
        self,
        request: ChatRequest,
        response: ChatResponse,
        evidence: list[RetrievedEvidence],
        started: float,
    ) -> None:
        self.repository.record_trace(
            {
                "id": response.trace_id,
                "question": request.question,
                "filters": {
                    "districts": request.selected_districts(),
                    "category": request.category,
                    "period": request.period,
                },
                "route": response.route.value,
                "retrieved_ids": [item.id for item in evidence],
                "mode": response.mode.value,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        )
