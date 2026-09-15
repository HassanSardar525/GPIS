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
  <img src="https://img.shields.io/badge/tests-144_passing-brightgreen.svg" alt="144 Tests Passing">
  <img src="https://img.shields.io/badge/districts-36_census_%7C_10_scored-orange.svg" alt="Districts">
</p>

---

## What is GPIS?

Election debate often focuses on promises and personalities. Official district data exists — literacy rates, health facilities, budget audits — but it is scattered across government spreadsheets and PDF reports that ordinary citizens rarely read.

**GPIS** gives citizens, journalists, and civic researchers a simple, evidence-backed view of how districts are actually performing, with enough source detail to verify every claim. Every displayed number traces to an official Pakistani government publication with exact page and table locators.

## ✨ Key Features

- 📊 **Deterministic scoring** — Education, health-access, and budget-accountability scores calculated by versioned Python rules, never by the LLM
- 🤖 **Tool-using RAG agent** — LangGraph agent with three controlled tools: district-data, evidence-search, and project-knowledge
- 📎 **Citation-first design** — Every factual sentence cites a retrieved evidence passage with publisher, period, and page locator
- 🔍 **Hybrid retrieval** — PostgreSQL full-text search + pgvector MiniLM embeddings combined through Reciprocal Rank Fusion
- ⚡ **Redis caching** — Failure-safe cache-aside for query embeddings and ranked evidence with corpus-version invalidation
- 💬 **Conversational memory** — PostgreSQL-backed LangGraph session checkpoints that survive API restarts
- 🛡️ **Guardrails** — Deterministic refusal for prompt injection, politician attribution, score manipulation, and unsupported claims
- 📈 **36 districts** — Census data for all Punjab districts; 10 scored with education, health, and accountability indicators
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
    S["Official PDF/XLSX sources"] --> J["Reviewed curated JSON"]
    J --> I["Idempotent seed + MiniLM embeddings"]
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
| **RAG Agent** | LangGraph, LangChain, Groq (openai/gpt-oss-20b) |
| **Embeddings** | sentence-transformers/all-MiniLM-L6-v2 (local, 384D) |
| **Caching** | Redis 7 with failure-safe cache-aside |
| **Observability** | Phoenix/OpenTelemetry (optional), LangSmith (optional) |
| **Frontend** | Vanilla HTML/CSS/JavaScript (3 hash-routed views) |
| **Infrastructure** | Docker, Docker Compose, GitHub Actions CI |
| **Deployment** | Render (app), Neon (PostgreSQL), Upstash (Redis) |

## 📊 RAG Quality Gates

Enforced by CI on every push. Run `python scripts/run_rag_evaluation.py --enforce` locally.

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

# Run the app
.\.venv\Scripts\python -m app.server
```

Open http://127.0.0.1:8000. The first bootstrap downloads the local MiniLM model (~90 MB).

### Run tests

```powershell
$env:GPIS_TEST_DATABASE_URL="postgresql+psycopg://gpis:gpis@localhost:5432/gpis"
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
data/curated/     Reviewed ten-district seed dataset + 36-district census
docs/             Architecture, methodology, RAG design, decisions, status
scripts/          Evaluation, documentation checks, session cleanup
tests/            19 test modules (144 tests): API, scoring, RAG, agent, cache, sessions
```

## 📖 Documentation

| Document | Description |
|---|---|
| [Architecture](docs/ARCHITECTURE.md) | System diagram, modules, and API surface |
| [Data & Scoring](docs/DATA_AND_SCORING.md) | Scoring methodology, formulas, and evidence contract |
| [RAG Design](docs/RAG_DESIGN.md) | Retrieval pipeline, guardrails, and evaluation |
| [Source Coverage](docs/SOURCE_COVERAGE.md) | Official sources, verified periods, and candidate decisions |
| [Project Scope](docs/PROJECT_SCOPE.md) | Problem statement, users, and non-goals |
| [Decisions](docs/DECISIONS.md) | Architecture decision records |
| [Status](docs/STATUS.md) | Current milestone and completed work |
| [Backlog](docs/BACKLOG.md) | Prioritized future work |
| [Changelog](CHANGELOG.md) | Release history |

## ⚠️ Current Scope & Limitations

- Ten districts are scored; 26 additional census districts have population and literacy facts only.
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
