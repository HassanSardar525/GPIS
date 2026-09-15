# Changelog

All notable user-visible changes will be documented here.

## [0.2.0] - 2026-09-15

### Added

#### Phase 1 — Agent hardening
- LangGraph agent with district-data, evidence-search, and project-knowledge tools.
- Bounded tool calls, conversational replies, and browser-session memory.
- Deterministic refusal for prompt injection and unsafe/out-of-scope requests.
- Agent/tool/retrieval/generation spans plus LangSmith run metadata.
- 53-test hardening suite with deterministic and live-agent metric gates.

#### Phase 2 — Structured comparisons
- Deterministic pairwise score, rank, component, and trend comparisons.
- Numeric/district association and causal-language validation with grounded fallback.
- Structured comparison responses and an inline responsive chat renderer.

#### Phase 3 — Evidence quality
- Punjab Health Statistics 2023/2024 with stable hashes and official source paths.
- Two comparable Table 3 health-capacity snapshots for all ten pilot districts.
- Typed evidence-quality contract with observation comparability and source anomalies.
- Score reporting period, coverage, confidence, missing-component, and warning metadata.
- Alembic migration for observation comparability and score quality fields.
- Normalized 183 health-capacity cells and 20 cited evidence chunks.

#### Phase 4 — Citation UX
- Exact source title, publisher, period, page/table locator, and retrieved passage in all citations.
- Expandable source-preview panels inside chat and comparison flows.
- Improved loading, no-evidence, deterministic fallback, retry, and stale-request states.
- Live-region announcements, semantic controls, visible focus, and reduced-motion behavior.
- New Chat action with session ID change and in-flight request handling.
- 63-case deterministic RAG gate: 92.06% answer accuracy, 98.31% retrieval recall, 100% citation precision.

#### Phase 5 — Session persistence and observability
- PostgreSQL-backed LangGraph session checkpoints replacing in-memory storage.
- Session lifecycle APIs with sliding expiry, status, and permanent deletion.
- Privacy-safe telemetry without questions, answers, passages, or prompts.
- Configurable session TTL and idempotent expired-session cleanup.

#### Phase 6 — Caching, census expansion, and UI
- Failure-safe Redis cache-aside for query embeddings and ranked evidence.
- Corpus-version invalidation and cache observability.
- PBS Census 2023 ingestion for all 36 Punjab districts.
- Three hash-routed views: Overview, District Profile with Ask GPIS, and Compare & Trends.
- 36-district census comparison bars, two-district factual tables, and budget-utilization graphs.
- Official health and DHA budget facts for all Punjab districts.
- GitHub Actions CI with PostgreSQL/pgvector service.

### Changed

- Expanded from 5 to 10 scored districts and 36 census districts.
- Test suite expanded from initial coverage to 144 passing tests across 19 modules.
- RAG evaluation expanded from 30 to 63 deterministic cases plus 12 live-agent scenarios.

## [0.1.0] - 2026-08-20

### Added

- Five-district South Punjab dashboard.
- Education, health-access, financial-management, and overall scores.
- District/category rankings.
- Official source links and evidence locators.
- Citation-grounded evidence assistant with abstention.
- Dependency-free Python server and responsive browser UI.
- Initial automated test suite and project documentation.
