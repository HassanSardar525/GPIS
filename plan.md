# GPIS One-Week MVP Plan

> This is the original delivery plan. For the implemented state and current priorities, use [docs/STATUS.md](docs/STATUS.md) and [docs/BACKLOG.md](docs/BACKLOG.md).

## Goal

Build a working Punjab District Development and Accountability platform where a user can:

1. Search for a district and view its health, education, and accountability performance.
2. Compare districts and view best/worst rankings and year-over-year change where comparable data exists.
3. Click any score to inspect its calculation, original sources, and an LLM-written explanation.
4. Chat with a citation-backed RAG system about the available district evidence.

The project is a CV-ready MVP, not a nationwide production system.

![GPIS architecture](docs/assets/gpis-architecture.png)

## Fixed MVP scope

- Five Punjab districts.
- Three scorecards: education, health, and accountability.
- One current period and one previous period only where definitions are comparable.
- Punjab official statistics plus one AGP audit report.
- English interface; simple Urdu labels are a stretch goal.
- Read-only public application with no user accounts or administration panel.
- Deterministic scoring; the LLM cannot calculate or modify scores.

## Important geography decision

Districts and electoral constituencies are different geographic units and may overlap imperfectly.

For the MVP:

- Users search by **district** because the performance datasets are district-based.
- A district page may display related National Assembly and Provincial Assembly constituencies and representatives as context.
- Results are attributed primarily to the responsible provincial government and reporting period.
- The application must not claim that one MPA or MNA caused a district outcome.
- Constituency-level scoring is deferred until trustworthy constituency-level outcome data is available.

## Decisions required before coding

Spend no more than two to three hours resolving these items:

- [ ] Select the five pilot districts.
- [ ] Select the exact source files and reporting periods using [the official document survey](docs/DOCUMENT_SURVEY.md).
- [ ] Confirm the small set of metrics available consistently across those districts.
- [ ] Define transparent weights and missing-data behavior.
- [ ] Select the LLM and embedding provider.
- [ ] Confirm whether the final demo requires Urdu.

Once these decisions are made, further architecture discussion should not block the first vertical slice.

---

## Phase 0 — Project skeleton and evidence contract

**Time:** Half day
**Modules:** Repository, configuration, data contracts

### Work

- [ ] Create `backend`, `frontend`, `pipelines`, `data`, `methodology`, and `tests` directories.
- [ ] Add Docker Compose for PostgreSQL with pgvector.
- [ ] Define identifiers for district, sector, metric, period, source, and score.
- [ ] Define source metadata: publisher, document title, URL, retrieval date, checksum, page/table reference.
- [ ] Create one small manually reviewed fixture containing one district, one metric, and one source passage.
- [ ] Add environment-variable templates without committing secrets.

### Working result

A clean checkout can start PostgreSQL and load one traceable observation linked to one source.

### Acceptance check

- [ ] The observation can be queried by district and traced to its source/page.
- [ ] No secret or large raw document is committed accidentally.

---

## Phase 1 — Data ingestion vertical slice

**Time:** Day 1
**Modules:** Data pipeline, source registry, validation

### Work

- [ ] Download or register the selected official statistical files and AGP audit PDF.
- [ ] Build a Python pipeline that imports the selected CSV/Excel/table data.
- [ ] Extract audit paragraphs with district, category, amount, recommendation, and page number.
- [ ] Standardize district names, reporting periods, units, and missing values.
- [ ] Store raw source metadata and normalized observations in PostgreSQL.
- [ ] Produce a validation report showing accepted, rejected, duplicate, and missing records.

### Working result

A command loads real official data for at least one district and produces a source-linked database record.

### Acceptance check

- [ ] At least five source values have been manually checked against the original document.
- [ ] Missing values remain missing and are never converted to zero.
- [ ] Every value has a source and reporting period.

---

## Phase 2 — Deterministic scoring and rankings

**Time:** Day 2
**Modules:** Methodology, scoring engine, ranking engine

### Work

- [ ] Define the selected health, education, and accountability metrics in versioned configuration.
- [ ] Define directionality: higher-is-better or lower-is-better.
- [ ] Implement normalization and weighted aggregation as pure Python functions.
- [ ] Store score components, coverage, formula version, and exclusion reason.
- [ ] Implement district rankings for each sector and period.
- [ ] Implement year-over-year change only for indicators with matching definitions and periods.
- [ ] Add hand-calculated golden tests.

### Working result

A command or test prints the three scorecards and ranking positions for the pilot districts.

### Acceptance check

- [ ] The same inputs always produce the same scores.
- [ ] Clicking through a score will be able to expose every input and weight.
- [ ] Districts with insufficient data are marked unranked rather than assigned a misleading score.
- [ ] Best/worst and year-over-year claims are based on comparable records.

---

## Phase 3 — Search, district pages, comparison, and API

**Time:** Day 3
**Modules:** FastAPI, district search, comparison endpoints, basic React UI

### Backend work

- [ ] Implement district search and autocomplete.
- [ ] Add district profile, sector score, score breakdown, ranking, comparison, source, and methodology endpoints.
- [ ] Add filters for sector and period.
- [ ] Return explicit states such as `available`, `missing`, `not_comparable`, and `insufficient_coverage`.
- [ ] Add ECP/Assembly constituency and representative context where available.

### Frontend work

- [ ] Create a home page with district search.
- [ ] Create a district page with three scorecards.
- [ ] Create ranking lists for best and worst performance.
- [ ] Create a comparison view for two districts.
- [ ] Make every score clickable to show components and source links.

### Working result

A user can search for a district, inspect its three scores, compare it with another district, and view its ranking without using AI.

### Acceptance check

- [ ] A user can reach any pilot district in two or fewer interactions.
- [ ] Score components, period, units, methodology version, and missing-data state are visible.
- [ ] The application distinguishes district outcomes from representative identity.

---

## Phase 4 — RAG evidence pipeline

**Time:** Day 4
**Modules:** Document parsing, chunking, embeddings, pgvector retrieval

### Recommended RAG architecture

Use **hybrid structured-data and document RAG**:

```text
User question
    ↓
Query router: district + sector + period + intent
    ├── PostgreSQL retrieval → exact metrics, scores, rankings, components
    └── pgvector retrieval   → supporting report passages and audit paragraphs
                                  ↓
                         Evidence/context builder
                                  ↓
                         LLM explanation request
                                  ↓
                    Citation and numeric consistency check
                                  ↓
                       Answer with sources or abstention
```

Pure vector RAG is unsuitable because embeddings should not be trusted to retrieve or calculate exact scores and rankings.

### Work

- [ ] Extract PDF text while preserving document, page, district, sector, period, and audit-paragraph metadata.
- [ ] Chunk by meaningful paragraph/table section rather than arbitrary character count where possible.
- [ ] Generate embeddings and store them in pgvector.
- [ ] Implement metadata-filtered retrieval by district, sector, period, and source type.
- [ ] Create a small evaluation set of 15–20 questions with expected source pages.
- [ ] Measure whether the correct evidence appears in the top retrieved results.

### Chunk record

Each chunk should contain:

```text
chunk_id
source_id
document_title
publisher
page_number
section_or_audit_paragraph
district_id
sector
reporting_period
text
embedding
```

### Working result

Given a district question, the backend returns the most relevant official passages with correct page metadata—without generating an answer yet.

### Acceptance check

- [ ] Expected evidence is retrieved for at least 80% of the small evaluation set.
- [ ] Retrieval is restricted to the requested district/sector/period when those filters exist.
- [ ] Every retrieved chunk has a resolvable source and page.

---

## Phase 5 — Score explanations and conversational RAG

**Time:** Day 5
**Modules:** RAG orchestrator, LLM, citations, chat API and UI

### Query types

The router should support four controlled intents:

1. **Lookup:** “What is Multan’s health score?”
2. **Explanation:** “Why is Multan ranked lower?”
3. **Comparison:** “Why is Bahawalpur above Multan?”
4. **Evidence:** “Which report supports this audit finding?”

Questions outside the loaded evidence should receive an honest limitation response.

### Work

- [ ] Parse district, sector, period, and comparison target from the question.
- [ ] Retrieve exact numeric facts through fixed database functions—not unrestricted LLM-generated SQL.
- [ ] Retrieve supporting document chunks through filtered pgvector search.
- [ ] Build a prompt containing score components, evidence passages, and citation identifiers.
- [ ] Require structured output containing answer, claims, citations, and limitations.
- [ ] Validate that cited chunks exist and that generated numbers match database values.
- [ ] Cache explanations for score pages.
- [ ] Add a chat panel with a small conversation history and suggested questions.
- [ ] Show source title, page, reporting period, and “open source” action beside answers.

### RAG rules

- The LLM explains; it never calculates or writes scores.
- The answer must use only retrieved database facts and document evidence.
- Every factual claim must have a citation.
- Audit observations must not be described as proven corruption.
- District outcomes must not be presented as proof that one politician caused them.
- If sources conflict or evidence is absent, the system says so.
- Invalid citations or mismatched numbers cause the response to be rejected or marked unverified.

### Working result

A user can click a score to receive a cited explanation and can ask follow-up questions about the loaded district evidence.

### Acceptance check

- [ ] Answers reproduce stored numbers exactly.
- [ ] Every displayed citation opens the correct source/page or source record.
- [ ] Unsupported questions return “insufficient evidence” instead of invented content.
- [ ] The score page remains functional if the LLM provider fails.

---

## Phase 6 — Polish, trust, and deployment

**Time:** Days 6–7
**Modules:** UX, testing, deployment, documentation

### Work

- [ ] Improve mobile layout, colors, icons, tooltips, and plain-language labels.
- [ ] Add simple Urdu labels or an Urdu explanation option if time permits.
- [ ] Add methodology, data coverage, limitations, and source catalog pages.
- [ ] Test search, rankings, comparisons, score breakdowns, RAG citations, and failure states.
- [ ] Add rate limits to chat and secure API keys.
- [ ] Containerize frontend, API, worker, and PostgreSQL/pgvector.
- [ ] Deploy the demo and seed it with a reproducible data release.
- [ ] Record a two-minute demo video and add architecture and screenshots to the README.

### Working result

A publicly accessible, CV-ready MVP demonstrates the complete source-to-score-to-explanation workflow.

### Acceptance check

- [ ] A new user can complete search, comparison, score explanation, and chat flows.
- [ ] No visible score lacks methodology and source information.
- [ ] No RAG answer contains an unresolved citation or invented number.
- [ ] The application can be started from a clean checkout using documented commands.

---

## Module ownership map

| Module | Main responsibility | Depends on |
|---|---|---|
| Source registry | Source identity and provenance | Official files |
| Ingestion pipeline | Parsing, cleaning, validation | Source registry |
| Scoring engine | Deterministic sector scores | Normalized observations, methodology |
| Ranking engine | Position and comparable change | Valid scores and periods |
| FastAPI | Search, profiles, comparisons, chat endpoint | Database and services |
| RAG retrieval | Evidence chunks and semantic search | Parsed documents, pgvector |
| RAG orchestrator | SQL facts + evidence + LLM response | API, PostgreSQL, pgvector |
| Citation validator | Reject unsupported claims | RAG structured output |
| React dashboard | Search, rankings, comparisons, score details | FastAPI |
| Chat interface | Questions, answers, citations | RAG endpoint |

## Deferred until after the MVP

- Nationwide coverage.
- Constituency-level performance scoring.
- A single definitive politician score.
- Real-time scraping and automatic data updates.
- User accounts, comments, or public submissions.
- Blockchain-based audit trail.
- Advanced agents or unrestricted text-to-SQL.
- Complex reranking, knowledge graphs, or multiple vector databases.
- Native mobile application.

## Final success demonstration

The demo should show this exact sequence:

1. Search for a pilot district.
2. Open its education, health, and accountability scorecards.
3. Compare it with another district or open its ranking.
4. Click a score and inspect its inputs and original sources.
5. Generate a citation-backed plain-language explanation.
6. Ask a follow-up question in chat.
7. Open the cited report page and verify the evidence.

If this sequence works reliably, the MVP has achieved its purpose.
