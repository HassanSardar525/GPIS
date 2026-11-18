# Testing GPIS

Run from the repository root in the environment described in [AGENTS.md](../AGENTS.md).

| Level | Verification |
| --- | --- |
| Component | Test extraction against reviewed cells, routing, district/period filters, retrieval IDs and officeholder tenure boundaries. |
| Pipeline | Measure recall at five, generation mode, exact district/value associations, dates, abstention and whether the cited passage supports the claim. |
| Application | Run API and browser journeys at desktop and mobile widths, switch districts during a conversation, open evidence and exercise fallback. |

## Baseline

```powershell
python -m compileall -q app scripts tests
python scripts/check_markdown_links.py
git diff --check
python -m pytest -q
python -m scripts.run_rag_evaluation --enforce
python -m scripts.run_agent_evaluation --enforce
```

Database integration tests use separate disposable databases in GPIS_TEST_DATABASE_URL and GPIS_PUNJAB_TEST_DATABASE_URL. Set GPIS_SCORE_VERSION=punjab-v1 for the release and disable LANGSMITH_TRACING on the app. The agent runner requires a valid Groq key.

## Browser acceptance

Install Chrome or run `python -m playwright install chromium` and set GPIS_BROWSER_CHANNEL=chromium. Point GPIS_BROWSER_TEST_URL to the running candidate. Browser checks are opt-in during normal development.

```powershell
python -m pytest -q tests/test_workspace_browser.py tests/test_history_browser.py
```

Open Multan through search, compare its Census 2023 literacy with Lahore, inspect the original table, check archived representation and ask a cited follow-up. Verify both district names and their values. Repeat after switching district. A skipped browser or document case is pending release evidence.
