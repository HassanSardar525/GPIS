"""Exercise the release API and browser journeys against one candidate instance."""

import argparse
import os
import subprocess
import sys
from uuid import uuid4

import httpx
import pytest

from app.llm import CITATION_MARKER


def check_api(client: httpx.Client) -> None:
    health = client.get("/api/v1/health").raise_for_status().json()
    if health["repository"] != "postgres" or health["database"] != "available":
        raise ValueError("The release candidate requires PostgreSQL")
    model = client.get("/api/v1/models").raise_for_status().json()["default_model"]
    session = str(uuid4())
    scenarios = [
        ("live explanation", "Explain the total literacy rate for Multan in the 2023 census.", model),
        ("document lookup", "What does PBS Table 12 report about literacy in Multan?", "fallback"),
        ("unsupported", "Which politician caused this result?", model),
    ]
    failures = []
    try:
        for name, question, selected in scenarios:
            result = client.post("/api/v1/chat", json={
                "question": question, "districts": ["multan"], "session_id": session, "model": selected,
            }).raise_for_status().json()
            mode = result["mode"]
            citations = {item["evidence_id"]: item for item in result["citations"]}
            markers = set(CITATION_MARKER.findall(result["answer"]))
            if name == "unsupported":
                passed = mode == "abstained" and result["abstained"] and not citations and bool(result["answer"].strip())
            else:
                passed = (
                    not result["abstained"] and bool(markers) and markers <= citations.keys()
                    and "61.41" in result["answer"] and "multan" in result["answer"].lower()
                    and all(citations[key]["passage"] and citations[key]["locator"] for key in markers)
                )
                if name == "live explanation":
                    passed = passed and mode in {"groq", "gemini"}
                else:
                    passed = passed and mode == "extractive" and "doc-pbs-table-12-multan-v1" in markers
                anchors = {anchor for item in citations.values() for anchor in item["anchor_ids"]}
                for anchor in anchors:
                    client.get(f"/api/v1/evidence/{anchor}").raise_for_status()
            print(f"{name}: mode={mode} trace={result['trace_id']} passed={passed}", flush=True)
            if not passed:
                failures.append(name)
    finally:
        client.delete(f"/api/v1/sessions/{session}")
    if failures:
        raise ValueError("Failed scenarios: " + ", ".join(failures))


class RequiredChecks:
    def __init__(self):
        self.skipped = []

    def pytest_runtest_logreport(self, report):
        if report.skipped:
            self.skipped.append(report.nodeid)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="Running candidate to check")
    args = parser.parse_args()
    os.environ["GPIS_BROWSER_TEST_URL"] = args.url.rstrip("/")
    baseline = subprocess.run([sys.executable, "-m", "scripts.run_rag_evaluation", "--enforce", "--require-documents"])
    with httpx.Client(base_url=args.url.rstrip("/"), timeout=120) as client:
        try:
            check_api(client)
            api_ok = True
        except (httpx.HTTPError, ValueError) as error:
            print(f"Release API check failed: {error}")
            api_ok = False
    checks = RequiredChecks()
    browser = pytest.main(["-q", "tests/test_workspace_browser.py", "tests/test_history_browser.py",
                           "tests/test_release_browser.py", "tests/test_provider_outage.py"], plugins=[checks])
    if checks.skipped:
        print("Required tests skipped:", ", ".join(checks.skipped))
    return int(bool(baseline.returncode or not api_ok or browser or checks.skipped))


if __name__ == "__main__":
    raise SystemExit(main())
