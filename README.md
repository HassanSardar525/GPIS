# Government Performance Intelligence System (GPIS)

GPIS is a citation-first dashboard and RAG assistant for comparing education, health access, and public-financial-management indicators across ten South Punjab districts.

## Architecture

```mermaid
flowchart LR
    S["Official PDF/XLSX sources"] --> J["Reviewed curated JSON"]
    J --> I["Idempotent seed + MiniLM embeddings"]
    I --> P["PostgreSQL + pgvector"]
    P --> Q["SQL facts, full-text search, vector search"]
    Q --> R["Filtered reciprocal-rank fusion"]
    R --> G["Groq grounded generation"]
    R --> F["Extractive fallback / abstention"]
    G --> A["FastAPI /api/v1"]
    F --> A
    P --> D["Deterministic scoring"]
    D --> A
    A --> U["HTML/CSS/JavaScript UI"]
```

Scores are calculated by versioned Python rules and stored in PostgreSQL. RAG and Groq may explain scores but cannot calculate or change them.

## Project structure

```text
app/
  database/       SQLAlchemy models, PostgreSQL repository, seed and sessions
  static/         Browser UI
  main.py         FastAPI app and /api/v1 routes
  services.py     District, retrieval and chat orchestration
  scoring.py      Deterministic score formulas
  routing.py      Question classification and controlled query expansion
  llm.py          Groq provider and citation validation
  embeddings.py   Local MiniLM embeddings
alembic/          Database migrations
data/curated/     Reviewed ten-district seed dataset
data/raw/         Local official source documents
docs/             Scope, architecture, RAG, methodology and backlog
scripts/          Evaluation and documentation checks
tests/            API, scoring, RAG and PostgreSQL integration tests
compose.yml       Local PostgreSQL/pgvector and API services
```

## Setup

Requirements: Python 3.11+, Docker Desktop, and optionally a Groq API key. Local development uses Docker PostgreSQL; managed PostgreSQL can be added during deployment.

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -e ".[dev]"
Copy-Item .env.example .env   # Skip if .env already exists
```

Add the optional key to `.env`; never commit this file:

```env
GROQ_API_KEY=gsk_your_key
GROQ_MODEL=openai/gpt-oss-20b
```

## Start locally

Recommended development workflow:

```powershell
docker compose up -d database
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\python -m app.cli bootstrap
.\.venv\Scripts\python -m app.server
```

Open <http://127.0.0.1:8000>. The first bootstrap downloads the local MiniLM model.

Full Docker startup:

```powershell
docker compose up --build
```

## Stop locally

- Stop the Python API with `Ctrl+C`.
- Stop services while preserving database data: `docker compose stop`.
- Remove containers while preserving the named database volume: `docker compose down`.
- Delete containers and local database data only when intentionally resetting: `docker compose down -v`.

## Verify

```powershell
$env:GPIS_TEST_DATABASE_URL="postgresql+psycopg://gpis:gpis@localhost:5432/gpis_test"
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python scripts\run_rag_evaluation.py --enforce
.\.venv\Scripts\python scripts\check_markdown_links.py
```

## Current scope and limits

- Ten districts, one current score period, and a two-period development-budget comparison.
- Education uses literacy and gender parity.
- Health is relative facility availability, not care quality or outcomes.
- Accountability is budget utilization, not proof of honesty or corruption.
- District results do not prove that an individual politician caused an outcome.
- Automatic ingestion, additional periods, constituencies, Urdu, public deployment, and managed PostgreSQL are deferred.

See [project status](docs/STATUS.md), [architecture](docs/ARCHITECTURE.md), [data and scoring](docs/DATA_AND_SCORING.md), and [RAG design](docs/RAG_DESIGN.md).

## License

MIT. See [LICENSE](LICENSE).
