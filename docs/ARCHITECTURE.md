# Architecture

## Implemented architecture

```mermaid
flowchart LR
    S["Official XLSX and PDF sources"] --> C["Manually reviewed evidence contract"]
    C --> D["Idempotent seed command"]
    D --> P["PostgreSQL facts, sources, and persisted scores"]
    D --> V["pgvector MiniLM evidence embeddings"]
    P --> E["Pure deterministic scoring rules"]
    P --> H["SQL facts plus PostgreSQL full-text search"]
    V --> H
    H --> R["Filtered RRF retrieval, maximum six chunks"]
    R --> G["Groq provider with citation validation"]
    R --> F["Extractive fallback or abstention"]
    E --> A["FastAPI /api/v1"]
    G --> A
    F --> A
    A --> U["Existing browser dashboard and chat"]
```

The application has no runtime dependency on the raw documents. Reviewed values and evidence passages live in `data/curated/districts.json` with publisher, period, URL, and page/table locators.

## Modules

| Module | Responsibility |
|---|---|
| `app/scoring.py` | Calculate transparent category and overall scores |
| `app/services.py` | Route questions, fuse retrieval results, validate generation, and fall back safely |
| `app/database/` | SQLAlchemy schema, repositories, idempotent seed, and embeddings |
| `app/llm.py` | Replaceable Groq provider and citation validator |
| `app/main.py` | FastAPI application, API contracts, errors, request IDs, and static UI |
| `app/static/` | District dashboard, rankings, evidence chat, and methodology UI |
| `data/curated/` | Versioned reviewed data contract |
| `tests/` | Score range, ranking, retrieval-scope, and abstention checks |

## API surface

- `GET /api/v1/health`
- `GET /api/v1/districts`
- `GET /api/v1/districts/{slug}`
- `GET /api/v1/rankings?category={category}`
- `POST /api/v1/chat`

Dependency injection selects a PostgreSQL repository in normal operation and the curated JSON adapter for lightweight tests. The scoring engine has no FastAPI, database, embedding, or LLM dependency. Rankings query stored results rather than recalculating in handlers.
