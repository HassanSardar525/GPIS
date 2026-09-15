# Project status

**Last updated:** 2026-09-15

**Current milestone:** Phase 6 — Deployment and portfolio completion

**State:** All development phases complete; deployment and documentation in progress

## Completed

- [x] Selected ten South Punjab pilot districts.
- [x] Downloaded and inspected PBS Census and Auditor-General sources.
- [x] Created a reviewed evidence contract with source/page metadata.
- [x] Implemented deterministic education, health, accountability, and overall scores.
- [x] Migrated to versioned FastAPI district, ranking, health, and chat APIs.
- [x] Added PostgreSQL, pgvector, Alembic, Docker Compose, and idempotent seeding.
- [x] Persisted versioned score components and verified them against golden fixtures.
- [x] Added structured fact retrieval and filtered PostgreSQL full-text/vector retrieval with RRF.
- [x] Added local MiniLM embeddings and retrieval traces.
- [x] Added optional self-hosted Phoenix/OpenTelemetry tracing plus detailed PostgreSQL trace records.
- [x] Added optional Groq generation with strict citation validation and deterministic fallback.
- [x] Added a single LangGraph agent with district-data, hybrid-evidence, and project-knowledge tools.
- [x] Added bounded tool calls, conversational replies, and browser-session memory.
- [x] Added deterministic FY 2022-23 to FY 2023-24 development-utilization comparisons and a cited temporal RAG route.
- [x] Added global citable project/methodology evidence and deterministic score-component explanations.
- [x] Live-tested Groq generation with `openai/gpt-oss-20b` and validated retrieved citations.
- [x] Built a responsive browser dashboard.
- [x] Reconnected the dashboard to ten-district ranks, period trends, score explanations, comparisons, RAG modes, and trace IDs.
- [x] Added a 63-case RAG evaluation and adversarial/provider-failure tests.
- [x] Passed all local automated tests and every RAG acceptance metric locally.
- [x] Added architecture, methodology, RAG, status, backlog, and decision documentation.
- [x] Added deterministic refusal for prompt injection and unsafe/out-of-scope requests.
- [x] Enforced real inline citations after evidence-bearing agent tools.
- [x] Added agent/tool/retrieval/generation spans plus LangSmith run metadata.
- [x] Expanded hardening coverage to 144 passing tests and added deterministic and live-agent metric gates.
- [x] Recorded and passed the first JSON-backed Phase 1 evaluation baseline.
- [x] Added deterministic pairwise score, rank, component, and supported trend comparisons.
- [x] Added numeric/district association and causal-language validation with grounded fallback.
- [x] Added structured comparison responses and an inline responsive chat renderer.
- [x] Expanded comparison coverage across unit, agent, API, UI, and PostgreSQL parity tests.
- [x] Acquired and verified Punjab Health Statistics 2023/2024 with stable hashes and official source paths.
- [x] Curated two comparable Table 3 health-capacity snapshots for all ten pilot districts with exact page/table locators.
- [x] Added a typed evidence-quality contract that preserves printed dashes as null and exposes reviewed source anomalies.
- [x] Classified district staffing and outcomes as unsupported and patient activity as pending review rather than forcing them into scoring.
- [x] Added an additive Alembic migration for observation comparability and score reporting-period, confidence, missing-component, and warning metadata.
- [x] Kept `prototype-v1` scores unchanged while seeding explicit periods and proxy warnings; confidence remains unassessed rather than fabricated.
- [x] Normalized 183 non-null health-capacity cells into a dedicated PostgreSQL comparability group and generated 20 cited evidence chunks.
- [x] Added a typed `/api/v1/districts/{slug}/trends/health-capacity` route with JSON/PostgreSQL parity coverage.
- [x] Passed the Phase 3 Alembic upgrade, idempotent seed, pgvector, trace, comparison, and health-capacity parity tests against local PostgreSQL.
- [x] Added exact source title, publisher, period, page/table locator, and retrieved passage to all citations.
- [x] Added expandable source-preview panels inside chat and comparison flows.
- [x] Improved loading, no-evidence, deterministic fallback, retry, stale-request, and empty-data states.
- [x] Added live-region announcements, semantic controls, visible focus, reduced-motion behavior, and mobile stacking.
- [x] Added a visible New Chat action with session ID change and in-flight request handling.
- [x] Passed the 63-case deterministic RAG gate with 92.06% answer accuracy, 98.31% retrieval recall at 5, 100% citation precision, and 100% unsupported-question abstention.
- [x] Replaced in-memory LangGraph checkpoints with the official asynchronous PostgreSQL checkpointer.
- [x] Persisted session creation, activity, expiry, message count, and status metadata across API recreation.
- [x] Added validated session status and permanent deletion APIs; deletion removes checkpoints and linked telemetry.
- [x] Added configurable sliding expiry and idempotent expired-session cleanup.
- [x] Stored privacy-safe telemetry metadata without questions, answers, passages, prompts, or exception dumps.
- [x] Added failure-safe Redis cache-aside for query embeddings and ranked evidence with corpus-version invalidation.
- [x] Expanded PBS Census 2023 ingestion to all 36 Punjab districts with population, literacy, and out-of-school data.
- [x] Added three hash-routed views: Overview, District Profile with Ask GPIS, and Compare & Trends.
- [x] Added 36-district census comparison bars, two-district factual tables, and accessible budget-utilization graphs.
- [x] Added official health and DHA budget facts for all Punjab districts.
- [x] Added GitHub Actions CI with PostgreSQL/pgvector service.

## Known limitations

- Ten districts are scored; the remaining 26 census districts have population and literacy facts only.
- Development-budget utilization and reviewed public health-capacity counts have two comparable periods.
- Health and accountability are provisional proxies, not comprehensive outcome measures.
- Raw source acquisition is manual.
- Groq remains optional; the extractive fallback keeps the application functional without it.
- Free-tier deployment includes cold starts after idle periods.
- Phoenix is optional and local; no hosted monitoring exists.
