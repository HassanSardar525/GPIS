# RAG-first expansion roadmap

**Primary goal:** Make GPIS a trustworthy RAG portfolio project that answers project, methodology, score-explanation, district-comparison, and period-change questions with structured calculations and source-linked explanations.

## Phase status

| Phase | Deliverable | Status |
|---|---|---|
| 0 | FastAPI, PostgreSQL/pgvector, deterministic scoring, Groq, citations and baseline evaluation | Done (`51f40b9`) |
| 1 | Verify ten-district and two-period source coverage; lock temporal metric definitions | Done |
| 2 | Add five districts and FY 2022-23/FY 2023-24 structured observations | Next |
| 3 | Add deterministic temporal comparison API and question route | Pending |
| 4 | Expand project/methodology RAG and score-reasoning answers | Pending |
| 5 | Add Phoenix tracing and a larger RAG evaluation suite | Pending |
| 6 | Reconnect UI trends/comparisons and complete end-to-end verification | Pending |

## Locked decisions

- Add Khanewal, Layyah, Lodhran, Rajanpur, and Vehari, producing a ten-district cohort.
- Keep current education, health, accountability, and overall formulas unchanged until the expanded cohort has golden fixtures.
- Use the audit report's comparable FY 2022-23 and FY 2023-24 development grant/expenditure table for the first temporal metric.
- Calculate development-budget utilization and period deltas in deterministic Python/SQL, never in the LLM.
- Do not claim year-over-year education, health, accountability-composite, or overall-score improvement until equivalent period inputs exist.
- RAG may explain changes and likely contributing evidence, but must distinguish correlation, audit observations, and proven causation.
- Add project and methodology knowledge as versioned, citable first-party evidence chunks.

## Phase acceptance gates

### Phase 2 - Data expansion

- Ten districts have complete current-period education, health, and accountability inputs.
- All ten have FY 2022-23 and FY 2023-24 development grant, expenditure, utilization, source, period, and locator.
- Seed remains idempotent and all expanded scores have golden fixtures.

### Phase 3 - Temporal comparison

- API returns both periods, absolute change, percentage-point change, and direction.
- Questions such as "How did Vehari development-budget utilization change?" use structured facts.
- Missing or incomparable periods produce explicit abstention rather than inferred improvement.

### Phase 4 - RAG reasoning

- Chat answers what GPIS is, how every score is calculated, why a district received a score, how districts compare, and why a reported period change occurred.
- Each factual sentence cites retrieved facts, methodology, or source evidence.
- The LLM cannot calculate scores or temporal deltas.

### Phase 5 - Observability and evaluation

- Trace routing, SQL facts, keyword/vector results, RRF ranks, Groq calls, citation validation, fallbacks, latency, and errors.
- Evaluate at least 60 fixed questions across ten districts and two periods.
- Preserve 100% golden calculations and unsupported-question abstention; require retrieval recall@5 >= 90% and citation precision >= 95%.

### Phase 6 - UI and final verification

- District pages show current scores and the supported two-period development-utilization trend.
- Chat exposes Groq, fallback, or abstained mode with complete citations.
- API, database, RAG evaluation, and browser flows pass before expanding scope again.
