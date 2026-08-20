# Project status

**Last updated:** 2026-08-20

**Current milestone:** Architecture-first MVP v0.2

**State:** Working locally

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
- [x] Added optional Groq generation with strict citation validation and deterministic fallback.
- [x] Added deterministic FY 2022-23 to FY 2023-24 development-utilization comparisons and a cited temporal RAG route.
- [x] Live-tested Groq generation with `openai/gpt-oss-20b` and validated retrieved citations.
- [x] Built a responsive browser dashboard.
- [x] Added a 40-case RAG evaluation and adversarial/provider-failure tests.
- [x] Passed all 32 automated tests and every RAG acceptance metric locally.
- [x] Added architecture, methodology, RAG, status, backlog, and decision documentation.

## Next milestone

Add citable project/methodology knowledge and deterministic score-explanation answers without changing score formulas.

## Known limitations

- Ten districts are covered; only development-budget utilization has two comparable periods.
- Health and accountability are provisional proxies.
- Raw source acquisition is manual.
- Groq remains optional; the extractive fallback keeps the application functional without it.
- No authentication, deployment pipeline, or monitoring exists.
