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
```

Database integration tests use separate disposable databases in GPIS_TEST_DATABASE_URL and GPIS_PUNJAB_TEST_DATABASE_URL. Set GPIS_SCORE_VERSION=punjab-v1 for the release and disable LANGSMITH_TRACING on the app. The agent runner requires a valid Groq key.

## Browser acceptance

Install Chrome or run `python -m playwright install chromium` and set GPIS_BROWSER_CHANNEL=chromium. Point GPIS_BROWSER_TEST_URL to the running candidate. Browser checks are opt-in during normal development.

```powershell
python -m pytest -q tests/test_workspace_browser.py tests/test_history_browser.py
```

Open Multan through search, compare its Census 2023 literacy with Lahore, inspect the original table, check archived representation and ask a cited follow-up. Verify both district names and their values. Repeat after switching district. A skipped browser or document case is pending release evidence.

## Release candidate

Use the same PostgreSQL database for the API and the release runner. The target database must have pgvector enabled and the candidate must use punjab-v1. The legacy agent fixture uses prototype-v1; run it only against its matching seeded database.

1. Set GPIS_DATABASE_URL and GPIS_REPOSITORY=postgres in the release operator's environment. Use the same commit and score version as the service.
2. Run `python -m alembic upgrade head` and `python -m app.cli bootstrap`. Bootstrap seeds reviewed observations and embeds missing chunks.
3. Place the two registered originals at the paths in `data/curated/document_sources.json` and run `python -m app.cli ingest-documents --source all` from this checkout with the ingestion extra installed. This verifies checksums before persisting chunks and embeddings. The web image does not ship raw documents.
4. Run the following from the release checkout, replacing the local URL with the actual hosted candidate URL for pre-merge sign-off.

```powershell
python -m scripts.check_release --url http://127.0.0.1:8000
```

The runner requires the document baseline and all browser tests to execute. It exercises the service's default live model, a document lookup and unsupported attribution over HTTP. An isolated FastAPI test injects a provider outage without disrupting visitor traffic. Set GPIS_BROWSER_CHANNEL=chromium if using Playwright's bundled browser. For Windows PostgreSQL use `python -m app.server` (selector event loop).

Record the URL, candidate revision, actual answer modes, and test counts in PLANS.md. Point production Render at the merged main branch and rerun the same checks after rollout.
