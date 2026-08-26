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

- Add a second comparable period for education and health where definitions and geography match.
- Add stronger health indicators such as beds, staffing, service activity, and outcomes when trustworthy sources exist.
- Expand accountability beyond budget utilization using carefully normalized audit indicators.
- Add score coverage, confidence, reporting period, and missing-data warnings.

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
