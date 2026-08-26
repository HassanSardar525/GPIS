"""Measure the configured LangGraph agent against fixed Phase 1 scenarios."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import time

from app.config import ROOT, Settings
from app.llm import CITATION_MARKER
from app.main import build_chat_service, build_repository
from app.observability import build_observability
from app.schemas import ChatRequest


CASES = ROOT / "tests" / "fixtures" / "agent_evaluation.json"


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * quantile) - 1)]


async def evaluate(enforce: bool) -> int:
    settings = Settings.from_env()
    if not settings.groq_api_key:
        print(
            json.dumps(
                {
                    "status": "skipped",
                    "reason": "GROQ_API_KEY is required to measure live agent tool selection.",
                },
                indent=2,
            )
        )
        return 2 if enforce else 0

    repository = build_repository(settings)
    observability = build_observability(settings)
    service = build_chat_service(settings, repository, observability)
    cases = json.loads(CASES.read_text(encoding="utf-8"))

    route_hits = 0
    tool_hits = 0
    answer_hits = 0
    abstention_total = 0
    abstention_hits = 0
    citation_total = 0
    citation_valid = 0
    latencies = []
    failures = []

    for case in cases:
        request = ChatRequest(
            question=case["question"],
            districts=case["districts"],
            session_id=case["session_id"],
        )
        started = time.perf_counter()
        response = await service.answer(request)
        latencies.append((time.perf_counter() - started) * 1000)

        route_ok = response.route.value == case["route"]
        tools_ok = set(response.tools_used) == set(case["expected_tools"])
        citations = {item.evidence_id for item in response.citations}
        citations_ok = set(case["expected_citations"]) <= citations
        answer = response.answer.casefold()
        terms_ok = all(term.casefold() in answer for term in case["answer_contains"])
        abstention_ok = response.abstained is case["abstained"]
        route_hits += route_ok
        tool_hits += tools_ok
        answer_hits += route_ok and tools_ok and citations_ok and terms_ok and abstention_ok

        markers = set(CITATION_MARKER.findall(response.answer))
        citation_total += len(markers)
        citation_valid += len(markers & citations)
        if case["abstained"]:
            abstention_total += 1
            abstention_hits += abstention_ok and not citations and not markers

        if not (route_ok and tools_ok and citations_ok and terms_ok and abstention_ok):
            failures.append(
                {
                    "id": case["id"],
                    "route": response.route.value,
                    "tools": response.tools_used,
                    "citations": sorted(citations),
                    "abstained": response.abstained,
                }
            )

    metrics = {
        "cases": len(cases),
        "answer_accuracy": answer_hits / len(cases),
        "route_accuracy": route_hits / len(cases),
        "tool_selection_accuracy": tool_hits / len(cases),
        "citation_precision": citation_valid / citation_total if citation_total else 1.0,
        "abstention_accuracy": abstention_hits / abstention_total if abstention_total else 1.0,
        "latency_ms_p50": round(statistics.median(latencies), 2),
        "latency_ms_p95": round(percentile(latencies, 0.95), 2),
    }
    print(json.dumps({"metrics": metrics, "failures": failures}, indent=2))

    thresholds = {
        "answer_accuracy": 0.80,
        "route_accuracy": 0.90,
        "tool_selection_accuracy": 0.80,
        "citation_precision": 1.0,
        "abstention_accuracy": 1.0,
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
