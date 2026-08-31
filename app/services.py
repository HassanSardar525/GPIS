"""Application services for districts, hybrid retrieval, and grounded chat."""

from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict

from app.comparisons import (
    build_comparison,
    comparison_language_is_safe,
    comparison_numbers_are_grounded,
    format_comparison_summary,
    requested_comparison_category,
)
from app.embeddings import Embedder
from app.llm import LLMProvider, validate_generated_answer
from app.observability import NoopObservability, Observability
from app.repositories import GPISRepository
from app.routing import classify_question, expand_semantic_query
from app.schemas import (
    AnswerMode,
    ChatRequest,
    ChatResponse,
    Citation,
    ComparisonResult,
    QuestionRoute,
    RetrievedEvidence,
)
from app.score_explanations import requested_score_category


LOGGER = logging.getLogger(__name__)


METHODOLOGY_TEXT = {
    "education": "Education is the mean of total literacy, female literacy, and 100 minus the male-female literacy gap.",
    "health": "Health is a min-max normalized comparison of listed public health facilities per 100,000 residents within the fixed ten-district cohort.",
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

    def development_trend(self, slug: str) -> dict:
        return self.repository.development_trend(slug)

    def health_capacity_trend(self, slug: str, facility: str) -> dict:
        return self.repository.health_capacity_trend(slug, facility)


class HybridRetriever:
    def __init__(
        self,
        repository: GPISRepository,
        embedder: Embedder | None,
        semantic_threshold: float = 0.35,
        rrf_k: int = 60,
        observability: Observability | None = None,
    ):
        self.repository = repository
        self.embedder = embedder
        self.semantic_threshold = semantic_threshold
        self.rrf_k = rrf_k
        self.observability = observability or NoopObservability()

    def retrieve(self, request: ChatRequest, route: QuestionRoute, limit: int = 6) -> list[RetrievedEvidence]:
        with self.observability.span(
            "gpis.retrieve",
            "RETRIEVER",
            {
                "gpis.question_length": len(request.question),
                "gpis.route": route.value,
                "gpis.districts": request.selected_districts(),
                "gpis.category": request.category,
                "gpis.period": request.period,
                "gpis.limit": limit,
            },
        ) as span:
            results = self._retrieve(request, route, limit)
            span.set_attributes(
                {
                    "retrieval.document_count": len(results),
                    "retrieval.document_ids": [item.id for item in results],
                    "gpis.keyword_ranks": {
                        item.id: item.keyword_rank for item in results if item.keyword_rank is not None
                    },
                    "gpis.vector_ranks": {
                        item.id: item.vector_rank for item in results if item.vector_rank is not None
                    },
                    "gpis.semantic_similarity": {
                        item.id: item.semantic_similarity
                        for item in results
                        if item.semantic_similarity is not None
                    },
                    "gpis.rrf_scores": {item.id: item.rrf_score for item in results},
                }
            )
            return results

    def _retrieve(self, request: ChatRequest, route: QuestionRoute, limit: int) -> list[RetrievedEvidence]:
        districts = request.selected_districts()
        if route == QuestionRoute.TEMPORAL_COMPARISON:
            facts = self.repository.trend_search(request.question, districts, limit)
        elif route == QuestionRoute.SCORE_EXPLANATION or (
            route == QuestionRoute.COMPARISON
            and (
                request.category is not None
                or any(word in request.question.casefold() for word in ("score", "rank", "position"))
            )
        ):
            facts = self.repository.score_search(request.question, districts, request.category, limit)
        else:
            facts = self.repository.fact_search(request.question, districts, limit)
        keyword = facts + self.repository.keyword_search(
            request.question, districts, request.category, request.period, limit
        )
        if route == QuestionRoute.METHODOLOGY:
            lowered = request.question.casefold()
            if request.category:
                method_query = request.category
            elif "development" in lowered and "utilization" in lowered:
                method_query = "development utilization"
            elif "overall" in lowered:
                method_query = "overall"
            else:
                method_query = next(
                    (category for category in ("education", "health", "accountability") if category in lowered),
                    "education health accountability",
                )
            keyword += self.repository.keyword_search(method_query, districts, None, request.period, limit)
        elif route == QuestionRoute.SCORE_EXPLANATION:
            score_category = requested_score_category(request.question, request.category)
            keyword += self.repository.keyword_search(
                f"{score_category} formula score components", districts, None, request.period, limit
            )
        elif route == QuestionRoute.PROJECT:
            project_query = (
                "RAG architecture"
                if any(word in request.question.casefold() for word in ("architecture", "pipeline", "rag", "retrieval"))
                else "project"
            )
            keyword += self.repository.keyword_search(
                project_query, [], None, None, limit
            )
        elif route == QuestionRoute.COMPARISON and not keyword:
            keyword += self.repository.keyword_search(
                "education health accountability", districts, request.category, request.period, limit
            )
        elif route == QuestionRoute.TEMPORAL_COMPARISON:
            keyword += self.repository.keyword_search(
                "development grant expenditure FY 2022-23 FY 2023-24",
                districts,
                "accountability",
                request.period,
                limit,
            )
        deduplicated = {}
        for item in keyword:
            deduplicated.setdefault(item.id, item)
        keyword = list(deduplicated.values())[:limit]
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
        observability: Observability | None = None,
    ):
        self.repository = repository
        self.retriever = retriever
        self.provider = provider
        self.observability = observability or NoopObservability()

    async def answer(self, request: ChatRequest) -> ChatResponse:
        started = time.perf_counter()
        trace_id = str(uuid.uuid4())
        route = classify_question(request.question)
        with self.observability.span(
            "gpis.chat",
            "CHAIN",
            {
                "session.id": request.session_id or "anonymous",
                "gpis.trace_id": trace_id,
                "gpis.question_length": len(request.question),
                "gpis.route": route.value,
                "gpis.districts": request.selected_districts(),
                "gpis.category": request.category,
                "gpis.period": request.period,
            },
        ) as span:
            response = await self._answer(request, route, trace_id, started)
            span.set_attributes(
                {
                    "gpis.answer_mode": response.mode.value,
                    "gpis.abstained": response.abstained,
                    "gpis.citation_ids": [item.evidence_id for item in response.citations],
                    "gpis.warning_count": len(response.warnings),
                }
            )
            return response

    async def _answer(
        self,
        request: ChatRequest,
        route: QuestionRoute,
        trace_id: str,
        started: float,
    ) -> ChatResponse:
        for slug in request.selected_districts():
            self.repository.get_district(slug)
        if route == QuestionRoute.CONVERSATION:
            response = ChatResponse(
                answer=(
                    "Hello! I can help with GPIS district scores, rankings, comparisons, trends, "
                    "methodology, and supporting evidence."
                ),
                mode=AnswerMode.EXTRACTIVE,
                route=route,
                citations=[],
                warnings=[],
                trace_id=trace_id,
                abstained=False,
            )
            self._record_trace(request, response, [], started)
            return response
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

        comparison = self._comparison(request, route)
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

        structured_context = self._structured_context(request, route, comparison)
        try:
            with self.observability.span(
                "gpis.generate",
                "LLM",
                {
                    "llm.provider": self.provider.name,
                    "gpis.question_length": len(request.question),
                    "gpis.evidence_ids": [item.id for item in evidence],
                },
            ) as generation_span:
                generated = await self.provider.generate(request.question, evidence, structured_context)
                valid = validate_generated_answer(generated, evidence) and (
                    comparison is None
                    or (
                        comparison_numbers_are_grounded(generated.answer, comparison)
                        and comparison_language_is_safe(generated.answer)
                    )
                )
                generation_span.set_attributes(
                    {
                        "gpis.generated_evidence_ids": generated.evidence_ids,
                        "gpis.citation_validation": valid,
                    }
                )
                if valid:
                    selected = [item for item in evidence if item.id in set(generated.evidence_ids)]
                    response = ChatResponse(
                        answer=generated.answer,
                        mode=AnswerMode.GROQ,
                        route=route,
                        citations=self._citations_with_comparison(selected, comparison),
                        warnings=generated.warnings
                        + self._response_warnings(request, route, comparison),
                        trace_id=trace_id,
                        abstained=False,
                        comparison=comparison,
                    )
                    self._record_trace(request, response, evidence, started)
                    return response
                LOGGER.warning("LLM response failed citation validation", extra={"trace_id": trace_id})
        except Exception as error:
            if self.provider.name != "unavailable":
                LOGGER.warning(
                    "LLM generation failed: %s", type(error).__name__, extra={"trace_id": trace_id}
                )

        response = ChatResponse(
            answer=self._fallback_answer(request, route, evidence, comparison),
            mode=AnswerMode.EXTRACTIVE,
            route=route,
            citations=self._citations_with_comparison(evidence[:3], comparison),
            warnings=["The LLM was unavailable or returned invalid citations."]
            + self._response_warnings(request, route, comparison),
            trace_id=trace_id,
            abstained=False,
            comparison=comparison,
        )
        self._record_trace(request, response, evidence, started)
        return response

    def _structured_context(
        self,
        request: ChatRequest,
        route: QuestionRoute,
        comparison: ComparisonResult | None = None,
    ) -> str:
        if comparison:
            return f"DETERMINISTIC_COMPARISON={comparison.model_dump_json()}"
        selected = request.selected_districts()
        if route not in {
            QuestionRoute.EXACT_FACT,
            QuestionRoute.COMPARISON,
            QuestionRoute.METHODOLOGY,
            QuestionRoute.SCORE_EXPLANATION,
            QuestionRoute.PROJECT,
            QuestionRoute.TEMPORAL_COMPARISON,
        }:
            return ""
        if route == QuestionRoute.TEMPORAL_COMPARISON:
            slugs = selected or [item["slug"] for item in self.repository.list_districts()]
            lines = []
            for slug in slugs:
                trend = self.repository.development_trend(slug)
                previous, current = trend["periods"]
                lines.append(
                    f"{trend['district_name']}: {previous['period']} utilization={previous['utilization_pct']}%; "
                    f"{current['period']} utilization={current['utilization_pct']}%; "
                    f"change={trend['change_percentage_points']} percentage points; direction={trend['direction']}"
                )
            return "\n".join(lines)
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
                f"accountability_score={scores['accountability']}; overall_score={scores['overall']}; "
                f"score_details={district['score_details']}"
            )
        return "\n".join(lines)

    def _fallback_answer(
        self,
        request: ChatRequest,
        route: QuestionRoute,
        evidence: list[RetrievedEvidence],
        comparison: ComparisonResult | None = None,
    ) -> str:
        if comparison:
            return format_comparison_summary(comparison)
        if route == QuestionRoute.METHODOLOGY:
            category = next(
                (name for name in ("education", "health", "accountability", "overall") if name in request.question.casefold()),
                "overall",
            )
            markers = " ".join(f"[{item.id}]" for item in evidence[:3])
            return f"{METHODOLOGY_TEXT[category]} {markers}".strip()
        if route in {QuestionRoute.SCORE_EXPLANATION, QuestionRoute.PROJECT}:
            return " ".join(f"{item.text} [{item.id}]" for item in evidence[:3])
        if route == QuestionRoute.TEMPORAL_COMPARISON:
            return " ".join(f"{item.text} [{item.id}]" for item in evidence[:3])
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

    def _comparison(self, request: ChatRequest, route: QuestionRoute) -> ComparisonResult | None:
        selected = request.selected_districts()
        if len(selected) != 2:
            return None
        if route == QuestionRoute.TEMPORAL_COMPARISON:
            category = "accountability"
        elif route == QuestionRoute.COMPARISON:
            lowered = request.question.casefold()
            structured_intent = request.category is not None or any(
                word in lowered for word in ("score", "rank", "ranking", "position", "performance", "overall")
            )
            if not structured_intent:
                return None
            category = requested_comparison_category(request.question, request.category)
        else:
            return None
        return build_comparison(self.repository, selected, category)

    @staticmethod
    def _citations(evidence: list[RetrievedEvidence]) -> list[Citation]:
        seen = set()
        citations = []
        for item in evidence:
            if item.id not in seen:
                citations.append(item.citation.model_copy(update={"passage": item.text}))
                seen.add(item.id)
        return citations

    @classmethod
    def _citations_with_comparison(
        cls,
        evidence: list[RetrievedEvidence],
        comparison: ComparisonResult | None,
    ) -> list[Citation]:
        citations = cls._citations(evidence)
        if comparison:
            citations.extend(comparison.citations)
        unique: dict[str, Citation] = {}
        for citation in citations:
            existing = unique.get(citation.evidence_id)
            if existing is None or (existing.passage is None and citation.passage is not None):
                unique[citation.evidence_id] = citation
        return list(unique.values())

    @staticmethod
    def _standard_warnings(route: QuestionRoute, question: str) -> list[str]:
        warnings = []
        if route == QuestionRoute.COMPARISON:
            warnings.append("District comparisons describe available indicators, not causation by an individual politician.")
        if route == QuestionRoute.TEMPORAL_COMPARISON:
            warnings.append(
                "The supported trend is development-budget utilization only; it is not an overall GPIS score or proof of impact."
            )
        if "corruption" in question.casefold():
            warnings.append("An audit observation is not, by itself, proof of corruption or fraud.")
        return warnings

    def _response_warnings(
        self,
        request: ChatRequest,
        route: QuestionRoute,
        comparison: ComparisonResult | None,
    ) -> list[str]:
        warnings = self._standard_warnings(route, request.question)
        if comparison:
            for district in comparison.districts:
                warnings.extend(district.score_detail.warnings)
        elif route in {QuestionRoute.SCORE_EXPLANATION, QuestionRoute.METHODOLOGY} or any(
            word in request.question.casefold() for word in ("score", "rank", "ranking")
        ):
            category = requested_score_category(request.question, request.category)
            selected = request.selected_districts()
            if selected:
                for slug in selected:
                    warnings.extend(
                        self.repository.get_district(slug)["score_details"][category]["warnings"]
                    )
            else:
                ranked = self.repository.rankings(category)
                if ranked:
                    warnings.extend(ranked[0]["score_detail"]["warnings"])
        return list(dict.fromkeys(warnings))

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
                "question": "",
                "session_id": request.session_id,
                "filters": {
                    "districts": request.selected_districts(),
                    "category": request.category,
                    "period": request.period,
                },
                "route": response.route.value,
                "retrieved_ids": [item.id for item in evidence],
                "mode": response.mode.value,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                "outcome": "abstained" if response.abstained else "success",
                "provider_status": "generated" if response.mode == AnswerMode.GROQ else "fallback",
                "failure_category": (
                    "unsupported_question"
                    if response.route == QuestionRoute.UNSUPPORTED
                    else "no_evidence"
                    if response.abstained
                    else "provider_fallback"
                    if response.mode == AnswerMode.EXTRACTIVE and self.provider.name != "unavailable"
                    else None
                ),
                "details": {
                    "provider": self.provider.name,
                    "citations": [item.evidence_id for item in response.citations],
                    "warning_count": len(response.warnings),
                    "abstained": response.abstained,
                    "comparison_category": response.comparison.category if response.comparison else None,
                    "retrieval": [
                        {
                            "id": item.id,
                            "keyword_rank": item.keyword_rank,
                            "vector_rank": item.vector_rank,
                            "semantic_similarity": item.semantic_similarity,
                            "rrf_score": item.rrf_score,
                        }
                        for item in evidence
                    ],
                },
            }
        )
