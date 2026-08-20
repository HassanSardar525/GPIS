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
    P --> T["District-data tool"]
    R --> V2["Evidence-search tool"]
    C --> K["Project-knowledge tool"]
    T --> L["Single bounded LangGraph agent"]
    V2 --> L
    K --> L
    L --> G["Groq tool calling and grounded response"]
    L --> F["Extractive fallback or abstention"]
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
| `app/agent.py` | Run the bounded LangGraph agent, three controlled tools, and in-memory chat sessions |
| `app/services.py` | Route questions, fuse retrieval results, validate generation, and fall back safely |
| `app/database/` | SQLAlchemy schema, repositories, idempotent seed, and embeddings |
| `app/llm.py` | Replaceable Groq provider and citation validator |
| `app/main.py` | FastAPI application, API contracts, errors, request IDs, and static UI |
| `app/static/` | District dashboard, ten-district rankings, two-period trends, score explanations, comparisons, and evidence chat |
| `data/curated/` | Versioned reviewed data contract |
| `tests/` | Score range, ranking, retrieval-scope, and abstention checks |

## API surface

- `GET /api/v1/health`
- `GET /api/v1/districts`
- `GET /api/v1/districts/{slug}`
- `GET /api/v1/districts/{slug}/trends/development-budget`
- `GET /api/v1/rankings?category={category}`
- `POST /api/v1/chat` accepts an optional `session_id` and returns `session_id` plus `tools_used`

Dependency injection selects a PostgreSQL repository in normal operation and the curated JSON adapter for lightweight tests. The scoring engine has no FastAPI, database, embedding, or LLM dependency. Rankings query stored results rather than recalculating in handlers.
