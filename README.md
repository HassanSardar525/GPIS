<p align="center">
  <img src="docs/assets/social-preview.jpg" alt="GPIS — Government Performance Intelligence System" width="600">
</p>

<p align="center">
  <strong>Citation-first RAG dashboard for district governance in Punjab, Pakistan</strong>
</p>

<p align="center">
  <a href="https://github.com/HassanSardar525/GPIS/actions/workflows/ci.yml"><img src="https://github.com/HassanSardar525/GPIS/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License">
  <img src="https://img.shields.io/badge/tests-versioned_regression_suite-brightgreen.svg" alt="Regression suite">
  <img src="https://img.shields.io/badge/districts-36_census_%7C_36_scored-orange.svg" alt="Districts">
</p>

---

## What is GPIS?

District profiles now connect measured changes to named provincial officeholders
and clickable original-page/cell evidence. Health history covers 36 districts;
comparative development spending covers 17 South DHAs. Officeholder dates and
earlier-year coverage remain explicitly partial. See
[historical evidence and coverage](docs/HISTORICAL_EVIDENCE.md).

Election debate often focuses on promises and personalities. Official district data exists — literacy rates, health facilities, budget audits — but it is scattered across government spreadsheets and PDF reports that ordinary citizens rarely read.

**GPIS** gives citizens, journalists, and civic researchers a simple, evidence-backed view of how districts are actually performing, with enough source detail to verify every claim. Every displayed number traces to an official Pakistani government publication with exact page and table locators.

## ✨ Key Features

- 📊 **Deterministic scoring** — Education, health-access, and budget-accountability scores calculated by versioned Python rules, never by the LLM
- 🤖 **Tool-using RAG agent** — LangGraph agent with three controlled tools: district-data, evidence-search, and project-knowledge
- 📎 **Citation-first design** — Every factual sentence cites a retrieved evidence passage with publisher, period, and page locator
- 🔍 **Hybrid retrieval** — PostgreSQL full-text search + pgvector MiniLM embeddings combined through Reciprocal Rank Fusion
- 📄 **Document-native evidence** — Checksum-pinned PBS XLSX and Punjab Health Statistics PDF tables become district-row chunks with parent table context
- ⚡ **Redis caching** — Failure-safe cache-aside for query embeddings and ranked evidence with corpus-version invalidation
- 💬 **Conversational memory** — PostgreSQL-backed LangGraph session checkpoints that survive API restarts
- 🛡️ **Guardrails** — Source-backed officeholder names are allowed; unsupported personal causation, prompt injection and score manipulation are blocked
- 📈 **36 census districts** — Source-aligned data; 36 scored under punjab-v1 with education, health-capacity, and DHA budget-utilization indicators
- 🔬 **Measurable quality** — 63-case deterministic RAG evaluation with enforced accuracy, recall, and citation gates

## 📸 Screenshots

<details>
<summary><strong>Overview — District scorecards at a glance</strong></summary>
<br>
<img src="docs/assets/screenshot-overview.jpg" alt="GPIS Overview Page" width="100%">
</details>

<details>
<summary><strong>District Profile — Scores, sources, and Ask GPIS chat</strong></summary>
<br>
<img src="docs/assets/screenshot-district.jpg" alt="GPIS District Profile with Ask GPIS" width="100%">
</details>

<details>
<summary><strong>Compare & Trends — 36-district rankings and budget trends</strong></summary>
<br>
<img src="docs/assets/screenshot-compare.jpg" alt="GPIS Compare and Trends" width="100%">
</details>

## 🏗️ Architecture

<img src="docs/assets/gpis-system-architecture.png" alt="GPIS System Architecture" width="100%">

```mermaid
flowchart LR
    S["Official PDF/XLSX sources"] --> J["Reviewed observations + source-specific table parsers"]
    J --> T["Document row chunks + parent table context"]
    J --> I["Idempotent seed + MiniLM embeddings"]
    T --> I
    I --> P["PostgreSQL + pgvector"]
    P --> D1["District-data tool: SQL facts"]
    P --> R["Filtered full-text + vector RRF"]
    R --> C1["Redis cache-aside: query vectors + ranked evidence"]
    C1 --> E1["Evidence-search tool"]
    J --> K1["Project-knowledge tool"]
    D1 --> L["LangGraph agent + session memory"]
    E1 --> L
    K1 --> L
    L --> G["Groq tool calling + grounded generation"]
    L --> F["Extractive fallback / abstention"]
    L --> X["Phoenix/OpenTelemetry traces"]
    G --> A["FastAPI /api/v1"]
    F --> A
    P --> D["Deterministic scoring"]
    D --> A
    A --> U["HTML/CSS/JavaScript UI"]
```

Scores are calculated by versioned Python rules and stored in PostgreSQL. RAG and Groq may explain scores but cannot calculate or change them.

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.11, FastAPI, Pydantic v2, Uvicorn |
| **Database** | PostgreSQL 16, pgvector, Alembic migrations |
| **RAG Agent** | LangGraph, LangChain, Gemini / Groq with source-based fallback |
| **Embeddings** | sentence-transformers/all-MiniLM-L6-v2 (local, 384D) |
| **Caching** | Redis 7 with failure-safe cache-aside |
| **Observability** | Phoenix/OpenTelemetry (optional), LangSmith (optional) |
| **Frontend** | Vanilla HTML/CSS/JavaScript (3 hash-routed views) |
| **Infrastructure** | Docker, Docker Compose, GitHub Actions CI |
| **Deployment** | Render (app), Neon (PostgreSQL), Upstash (Redis) |

## 📊 RAG Quality Gates

The table below is the historical prototype-v1 PostgreSQL baseline, not a fresh measurement of punjab-v1. Run `python scripts/run_rag_evaluation.py --enforce` locally.

| Metric | Result | Gate |
|---|---|---|
| Answer accuracy | 92.06% | ≥ 85% |
| Retrieval recall@5 | 98.31% | ≥ 90% |
| Citation precision | 100% | ≥ 95% |
| Unsupported-question abstention | 100% | = 100% |
| Evaluation cases | 63 deterministic + 12 live-agent | — |

## 🚀 Quick Start

**Requirements:** Python 3.11+, Docker Desktop, and optionally a Groq API key.

```powershell
# Clone and set up
git clone https://github.com/HassanSardar525/GPIS.git
cd GPIS
python -m venv .venv
.\.venv\Scripts\pip install -e ".[dev]"
Copy-Item .env.example .env   # Then add your GROQ_API_KEY

# Start services and seed data
docker compose up -d database redis
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\python -m app.cli bootstrap

# Optional document-native RAG ingestion (run once per registered source edition)
.\.venv\Scripts\pip install -e ".[ingestion]"
.\.venv\Scripts\python -m app.cli ingest-documents --source all

# Run the app
.\.venv\Scripts\python -m app.server
```

Open http://127.0.0.1:8000. The first bootstrap downloads the local MiniLM model (~90 MB).

Document ingestion reads the registered raw files during the command, validates every extracted value against the reviewed PostgreSQL observations, and stores retrieval chunks with exact workbook cells or PDF pages. Chat requests use the stored chunks; they do not reparse the source files. Use `--dry-run` to validate files without PostgreSQL or `--no-embed` to defer embeddings.

### Run tests

```powershell
$env:GPIS_TEST_DATABASE_URL="postgresql+psycopg://gpis:gpis@localhost:5432/gpis_test"  # Dedicated disposable test database
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python scripts/run_rag_evaluation.py --enforce
```

### Full Docker startup

```powershell
docker compose up --build
```

## 📁 Project Structure

```text
app/
  agent.py        LangGraph agent, three tools, bounded calls and session memory
  services.py     District, cached retrieval and chat orchestration
  scoring.py      Deterministic score formulas
  cache.py        Failure-safe Redis cache-aside and corpus-version keys
  routing.py      Question classification and controlled query expansion
  llm.py          Groq provider and citation validation
  embeddings.py   Local MiniLM embeddings
  comparisons.py  Deterministic pairwise comparisons
  session_store.py PostgreSQL session lifecycle
  observability.py Optional Phoenix/OpenTelemetry spans
  main.py         FastAPI app and /api/v1 routes
  database/       SQLAlchemy models, repository, seed, migrations
  static/         Browser UI (3 hash-routed views)
alembic/          Database migrations
data/curated/     36-district scoring contract + retained pilot baseline and source snapshots
docs/             Architecture, methodology, RAG design, decisions, status
scripts/          Evaluation, documentation checks, session cleanup
tests/            Regression tests: API, scoring, RAG, agent, cache, sessions
```

## 📖 Documentation

| Document | Description |
|---|---|
| [Architecture](docs/architecture.md) | System diagram, modules, and API surface |
| [Punjab Scoring](docs/PUNJAB_SCORING.md) | Active 36-district formulas, periods and source conflicts |
| [Data & Scoring](docs/DATA_AND_SCORING.md) | Scoring methodology, formulas, and evidence contract |
| [RAG Design](docs/RAG_DESIGN.md) | Retrieval pipeline, guardrails, and evaluation |
| [Source Coverage](docs/SOURCE_COVERAGE.md) | Official sources, verified periods, and candidate decisions |
| [Project Scope](docs/PROJECT_SCOPE.md) | Problem statement, users, and non-goals |
| [Decisions](docs/DECISIONS.md) | Architecture decision records |
| [Status](docs/STATUS.md) | Current milestone and completed work |
| [Backlog](docs/BACKLOG.md) | Prioritized future work |
| [Changelog](CHANGELOG.md) | Release history |

## ⚠️ Current Scope & Limitations

- All 36 Census 2023 districts have punjab-v1 scores. The original ten-district prototype-v1 remains reproducible. Source conflicts are flagged; see [Punjab methodology](docs/PUNJAB_SCORING.md).
- Education uses literacy and gender parity — not teaching quality or annual improvement.
- Health is relative facility availability — not care quality or outcomes.
- Accountability is budget utilization — not proof of honesty or corruption.
- District results do not prove that an individual politician caused an outcome.
- Groq is optional; the extractive fallback keeps the app functional without it.

See the full [scope document](docs/PROJECT_SCOPE.md) and [data methodology](docs/DATA_AND_SCORING.md).

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow, evidence requirements, and scoring rules.

## 📄 License

MIT. See [LICENSE](LICENSE).
