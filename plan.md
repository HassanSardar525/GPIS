# GPIS Development Plan

## Current architecture status

LangChain and LangGraph are already implemented on the `feature/langgraph-rag-agent` branch.

- LangChain defines three controlled tools: `district_data`, `evidence_search`, and `project_knowledge`.
- LangGraph runs one bounded agent, selects tools, and maintains short-term session memory.
- Groq generates conversational answers after tool execution.
- PostgreSQL and pgvector provide structured SQL data, full-text retrieval, and vector retrieval.
- Deterministic Python rules calculate scores; the LLM can explain scores but cannot change them.
- Invalid citations, provider errors, timeouts, and rate limits use the deterministic RAG fallback.

## Phase 1 — Validate and harden the agent ✅

**Status:** Complete on 2026-08-26.

- [x] Expand tests for tool selection, greetings, factual questions, comparisons, follow-up questions, and memory.
- [x] Test prompt injection, invented and omitted citations, invalid tool arguments, Groq timeouts, and rate limits.
- [x] Add repeatable measurement for answer accuracy, retrieval recall, citation precision, tool-selection accuracy, latency, and abstention.
- [x] Record deterministic and live Groq baselines on the JSON repository backend.
- [x] Run live Groq evaluation and record the Phase 1 baseline; PostgreSQL/MiniLM revalidation is deferred to the deployment integration environment because local model initialization stalled.
- [x] Trace LangGraph nodes, tool calls, retrieval, and generation in LangSmith and optional Phoenix/OpenTelemetry spans.

**Working result:** A reliable agent whose routing, evidence use, citations, and fallbacks are measurable.

## Phase 2 — Improve comparison and explanation answers

**Status:** Implementation complete on 2026-08-27; live PostgreSQL verification pending.

### 2.1 — Deterministic comparison contract

- [x] Add typed comparison models for category, district scores, ranks, component values, score/rank differences, available periods, yearly changes, and limitations.
- [x] Implement one deterministic comparison builder shared by JSON and PostgreSQL repositories; label unknown, missing, and non-comparable states explicitly.
- [x] Return the structured result from `district_data(action="compare")` instead of relying on the LLM to derive differences from raw district records.
- [x] Add the optional structured comparison result to `ChatResponse` while preserving existing clients and deterministic fallback behavior.

### 2.2 — Grounded explanation

- [x] Give Groq the deterministic comparison result plus canonical score and trend citations.
- [x] Require explanations to identify measured strengths and weaknesses, label possible contributing factors as inference, and avoid causal or politician-attribution claims.
- [x] Validate that every score, rank, component difference, and yearly change stated by the model matches the structured result; fall back when it does not.
- [x] Produce a deterministic comparison summary when Groq is unavailable, rate-limited, or invalid.

### 2.3 — Single-chat presentation

- [x] Render an optional comparison block inside the existing chat answer, not as a separate comparison form or page.
- [x] Show side-by-side district score/rank values, signed differences, component rows, and comparable yearly changes with clear unavailable states.
- [x] Keep citations and limitations adjacent to the comparison, with responsive and keyboard-accessible markup.
- [x] Preserve HTML escaping, safe source URLs, loading states, and the current mobile layout.

### 2.4 — Verification and acceptance

- [x] Add golden unit tests for pairwise score, rank, component, and trend differences, including ties and missing/non-comparable data.
- [x] Add JSON/PostgreSQL parity tests for the structured comparison contract.
- [x] Add agent tests for comparison tool selection, numeric consistency, inference language, citations, follow-ups, invalid districts, and provider fallback.
- [x] Add API and UI tests for the optional comparison payload and inline rendering.
- [x] Extend the fixed evaluation cases and require no regression in Phase 1 routing, citation, abstention, or latency gates.
- [ ] Run the structured comparison parity test and live-agent evaluation against PostgreSQL before deployment.

### Acceptance gate

- Every displayed comparison number is produced by deterministic Python and matches repository data exactly.
- Every comparison claim has a resolvable score, methodology, or trend citation.
- Missing or non-comparable values are labeled rather than converted to zero or explained speculatively.
- The LLM explains the supplied result but cannot calculate, rank, or modify it.
- Users complete score, rank, component, and supported yearly comparisons within the existing chat flow.

**Working result:** Users can ask natural-language comparison questions and receive clear, cited answers.

## Phase 3 — Improve evidence quality

**Status:** Completed 2026-08-29. `prototype-v1` remains active; `evidence-v2` is registered but gated because required education, health activity/outcome, and audit-denominator evidence did not qualify.

### 3.1 — Qualify and register comparable sources

- [x] Acquire and checksum Punjab Health Statistics 2023 and 2024 from the official Bureau of Statistics Punjab publication flow.
- [x] Verify district geography, metric definitions, units, reporting periods, and table locators before accepting any two-period series.
- [x] Produce a metric-level compatibility matrix for facilities, beds, staffing, service activity, and outcomes; reject or label series whose definitions changed.
- [x] Evaluate Punjab Education Statistics or an earlier PBS source for a second education period without treating non-equivalent survey editions as a trend.
- [x] Confirm audit scope and expenditure denominators before using finding counts, categories, or questioned amounts in accountability scoring.
- [x] Register every accepted source with publisher, title, period, official URL, local file, SHA-256 checksum, and page/table locator.

### 3.2 — Extend the evidence and score contracts

- [x] Add explicit observation comparability metadata, including definition/version, geography level, population basis, and comparability group.
- [x] Add score reporting period, confidence, missing-component warnings, and meaningful calculated coverage to the JSON and PostgreSQL contracts.
- [x] Define coverage as available eligible component weight divided by expected component weight; never infer coverage from a stored score or convert missing observations to zero.
- [x] Define confidence from documented evidence properties such as source authority, directness, recency, and cross-period comparability—not from model probability.
- [x] Add an Alembic migration and idempotent seed metadata that preserves all `prototype-v1` definitions and results.
- [x] Add the new score version only after its formula, coverage threshold, and confidence rules pass review.
- [x] Expose the same metadata through district, ranking, comparison, score-explanation, and chat responses on both repository backends.

### 3.3 — Normalize reviewed observations

- [x] Ingest reviewed health-facility and bed observations with their original units and periods; keep staffing, activity, and outcomes excluded or pending until accepted.
- [x] Ingest district staffing, activity, or outcome observations only if they pass the compatibility review.
- [x] Derive count-based health capacity metrics per 100,000 using an explicitly recorded population denominator and period.
- [x] Ingest only education observations that pass the compatibility matrix and keep snapshots separate from comparable trends.
- [x] Normalize audit indicators by confirmed scope or expenditure denominators; keep finding categories and severity flags visible and avoid corruption or guilt labels.
- [x] Generate evidence chunks from reviewed observations with resolvable source and locator metadata.
- [x] Add validation that rejects duplicate periods/districts, incomplete metric contracts, unknown sources, invalid ranges, and accidental zero-filling.

### 3.4 — Introduce a versioned scoring methodology

- [x] Specify a new score version and publish exact components, directions, normalization cohorts, weights, minimum coverage, and confidence rules before calculation.
- [x] Stage replacement of the single facility-count health proxy with capacity/activity/outcome weights; keep it inactive because activity and outcome evidence did not qualify.
- [x] Add normalized audit signals only after comparable denominators are available; otherwise retain them as evidence and warnings outside the score.
- [x] Define unranked behavior when minimum coverage is not met and prevent partial scores from appearing equivalent to complete scores.
- [x] Keep `prototype-v1` reproducible and require callers to select or receive the active score version explicitly.
- [x] Add manually calculated golden fixtures for full, partial, missing, tied, and non-comparable cases.

### 3.5 — Explain evidence quality in existing flows

- [x] Show score version, reporting period, coverage, confidence, and missing-data warnings beside district and comparison results.
- [x] Support cited health-capacity period comparisons only for the reviewed Table 3 comparability group, with null changes and source warnings preserved.
- [x] Support education period comparisons only after an education series is marked comparable.
- [x] Update deterministic and Groq explanations to distinguish capacity, activity, outcome, and audit-risk evidence and to avoid causal claims.
- [x] Keep raw observations, derived metrics, score components, and narrative explanations traceable to the same canonical citations.

### 3.6 — Verification and acceptance

- [x] Run the Phase 3 migration, idempotent seed, pgvector round trip, and health-capacity JSON/PostgreSQL parity tests locally.
- [x] Spot-check every imported metric against the official source table for all ten districts and both accepted periods.
- [x] Test formulas, coverage/confidence rules, missing-data behavior, version selection, source validation, and trend compatibility.
- [x] Prove JSON/PostgreSQL parity for observations, scores, rankings, warnings, comparisons, and citations after migration and reseeding.
- [x] Run Alembic upgrade tests from the current schema and verify `prototype-v1` scores remain byte-for-byte equivalent to the golden fixture.
- [x] Extend the RAG evaluation with new evidence and unsupported-trend cases without regressing Phase 1 or Phase 2 gates.
- [x] Run the full PostgreSQL integration and live-agent evaluation before activating the new score version.

### Acceptance gate

- Every scored input is backed by a reviewed official source, exact locator, period, unit, and comparability decision.
- Every score reports version, period, coverage, confidence, and missing components; insufficiently covered districts are unranked.
- Missing and non-comparable observations remain explicit and never become zero, a fabricated trend, or an unsupported explanation.
- `prototype-v1` remains reproducible and its score-quality contract is identical across JSON and PostgreSQL; `evidence-v2` remains staged until its evidence gate passes.
- Year-over-year answers are available only for metrics whose definition, geography, unit, and population basis have been verified as compatible.

**Working result:** More defensible scores and meaningful year-over-year explanations.

## Phase 4 — Improve citations and user experience

- Show the exact source title, publisher, period, page/table locator, and retrieved passage.
- Add source-preview panels without creating a separate comparison form.
- Improve loading, no-evidence, fallback, accessibility, and mobile states.
- Add a visible New Chat action and explain when session memory resets.

**Working result:** Non-technical users can understand an answer and verify its evidence easily.

## Phase 5 — Persist sessions and add observability

- Replace in-memory LangGraph checkpoints with PostgreSQL-backed session storage.
- Add session expiry and deletion controls.
- Store privacy-safe tool, retrieval, citation, latency, and failure metrics.
- Keep Phoenix optional and ensure the application works when tracing is unavailable.

**Working result:** Conversations survive API restarts and the complete RAG workflow can be diagnosed.

## Phase 6 — Deployment and portfolio completion

- Add CI for unit, API, RAG evaluation, migration, and browser tests.
- Move PostgreSQL and pgvector to Neon or Supabase for deployment.
- Deploy FastAPI and the frontend with protected environment variables and health checks.
- Add a polished README, architecture diagram, evaluation report, screenshots, and a short demo video.

**Working result:** A public, reproducible CV project with a live demo and measurable RAG quality.

## Deferred until the architecture is reliable

- More districts and constituencies.
- Politician attribution or voting recommendations.
- Automatic PDF/XLSX ingestion.
- React migration or major redesign.
- Urdu interface.
