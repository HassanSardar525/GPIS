# Project status

**Last updated:** 2026-08-26

**Current milestone:** Phase 2 comparison and explanation answers

**State:** Planned

The active expansion is tracked in [RAG_ROADMAP.md](RAG_ROADMAP.md).

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
- [x] Added a 60-case RAG evaluation and adversarial/provider-failure tests.
- [x] Passed all local automated tests and every RAG acceptance metric locally.
- [x] Added architecture, methodology, RAG, status, backlog, and decision documentation.
- [x] Added deterministic refusal for prompt injection and unsafe/out-of-scope requests.
- [x] Enforced real inline citations after evidence-bearing agent tools.
- [x] Added agent/tool/retrieval/generation spans plus LangSmith run metadata.
- [x] Expanded hardening coverage to 53 passing tests and added deterministic and live-agent metric gates.
- [x] Recorded and passed the first JSON-backed Phase 1 evaluation baseline.

## Next milestone

Implement deterministic structured comparison results and grounded explanation output in the single chat interface.

## Known limitations

- Ten districts are covered; only development-budget utilization has two comparable periods.
- Health and accountability are provisional proxies.
- Raw source acquisition is manual.
- Groq remains optional; the extractive fallback keeps the application functional without it.
- Agent sessions are currently in memory and reset when the API process restarts.
- Phoenix is optional and local; no hosted monitoring, authentication, or deployment pipeline exists.
