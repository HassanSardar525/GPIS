# Project status

**Last updated:** 2026-08-20

**Current milestone:** Architecture-first MVP v0.2

**State:** Working locally

## Completed

- [x] Selected five South Punjab pilot districts.
- [x] Downloaded and inspected PBS Census and Auditor-General sources.
- [x] Created a reviewed evidence contract with source/page metadata.
- [x] Implemented deterministic education, health, accountability, and overall scores.
- [x] Migrated to versioned FastAPI district, ranking, health, and chat APIs.
- [x] Added PostgreSQL, pgvector, Alembic, Docker Compose, and idempotent seeding.
- [x] Persisted versioned score components and verified them against golden fixtures.
- [x] Added structured fact retrieval and filtered PostgreSQL full-text/vector retrieval with RRF.
- [x] Added local MiniLM embeddings and retrieval traces.
- [x] Added optional Groq generation with strict citation validation and deterministic fallback.
- [x] Live-tested Groq generation with `openai/gpt-oss-20b` and validated retrieved citations.
- [x] Built a responsive browser dashboard.
- [x] Added a 30-case RAG evaluation and adversarial/provider-failure tests.
- [x] Passed all 25 automated tests and every RAG acceptance metric locally.
- [x] Added architecture, methodology, RAG, status, backlog, and decision documentation.

## Next milestone

Polish the fixed five-district product and evidence quality without expanding scope.

## Known limitations

- Only five districts and one main period are covered.
- Health and accountability are provisional proxies.
- Raw source acquisition is manual.
- Groq remains optional; the extractive fallback keeps the application functional without it.
- No authentication, deployment pipeline, or monitoring exists.
