"""Run the fixed RAG evaluation set against the configured repository."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import time
from pathlib import Path

from app.config import ROOT, Settings
from app.llm import FailingProvider
from app.main import build_repository
from app.schemas import ChatRequest, QuestionRoute
from app.services import ChatService, HybridRetriever
from app.embeddings import MiniLMEmbedder
from app.routing import classify_question


CASES = ROOT / "tests" / "fixtures" / "rag_evaluation.json"


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * quantile) - 1)]


async def evaluate(enforce: bool) -> int:
    settings = Settings.from_env()
    repository = build_repository(settings)
    embedder = MiniLMEmbedder(settings.embedding_model) if repository.name == "postgres" else None
    retriever = HybridRetriever(repository, embedder, settings.semantic_threshold)
    service = ChatService(repository, retriever, FailingProvider())
    cases = json.loads(CASES.read_text(encoding="utf-8"))

    route_hits = 0
    expected_total = 0
    retrieval_hits = 0
    unsupported_total = 0
    unsupported_hits = 0
    citation_total = 0
    citation_valid = 0
    answer_hits = 0
    retrieval_latencies = []
    answer_latencies = []
    failures = []

    for case in cases:
        route = classify_question(case["question"])
        route_hits += route.value == case["route"]
        request = ChatRequest(question=case["question"], districts=case["districts"])
        retrieval_started = time.perf_counter()
        evidence = retriever.retrieve(request, route)
        retrieval_latencies.append((time.perf_counter() - retrieval_started) * 1000)
        retrieved_ids = {item.id for item in evidence[:5]}
        for expected in case["expected"]:
            expected_total += 1
            if expected in retrieved_ids:
                retrieval_hits += 1
            else:
                failures.append(f"{case['id']}: missing {expected}")
        answer_started = time.perf_counter()
        response = await service.answer(request)
        answer_latencies.append((time.perf_counter() - answer_started) * 1000)
        allowed_citations = retrieved_ids
        response_citations = {citation.evidence_id for citation in response.citations}
        for citation in response.citations:
            citation_total += 1
            citation_valid += citation.evidence_id in allowed_citations
        if route == QuestionRoute.UNSUPPORTED:
            unsupported_total += 1
            unsupported_hits += response.abstained and not response.citations
            answer_hits += response.abstained and not response.citations
        else:
            answer_hits += (
                response.route == route
                and not response.abstained
                and set(case["expected"]) <= response_citations
            )

    metrics = {
        "cases": len(cases),
        "route_accuracy": route_hits / len(cases),
        "answer_accuracy": answer_hits / len(cases),
        "retrieval_recall_at_5": retrieval_hits / expected_total if expected_total else 1,
        "citation_precision": citation_valid / citation_total if citation_total else 1,
        "unsupported_abstention": unsupported_hits / unsupported_total if unsupported_total else 1,
        "retrieval_latency_ms_p50": round(statistics.median(retrieval_latencies), 2),
        "retrieval_latency_ms_p95": round(percentile(retrieval_latencies, 0.95), 2),
        "answer_latency_ms_p50": round(statistics.median(answer_latencies), 2),
        "answer_latency_ms_p95": round(percentile(answer_latencies, 0.95), 2),
    }
    print(json.dumps(metrics, indent=2))
    if failures:
        print("Retrieval misses:")
        print("\n".join(f"- {failure}" for failure in failures))
    thresholds = {
        "route_accuracy": 1.0,
        "answer_accuracy": 0.90,
        "retrieval_recall_at_5": 0.90,
        "citation_precision": 0.95,
        "unsupported_abstention": 1.0,
    }
    if enforce and any(metrics[name] < threshold for name, threshold in thresholds.items()):
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--enforce", action="store_true", help="Fail when an acceptance threshold is missed")
    arguments = parser.parse_args()
    raise SystemExit(asyncio.run(evaluate(arguments.enforce)))


if __name__ == "__main__":
    main()
