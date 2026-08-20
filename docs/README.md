# GPIS documentation

This directory is the source of truth for product, technical, and evidence decisions.

| Document | Use it for |
|---|---|
| [PROJECT_SCOPE.md](PROJECT_SCOPE.md) | Goals, users, boundaries, and success criteria |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Components, request flow, and replacement points |
| [DATA_AND_SCORING.md](DATA_AND_SCORING.md) | Metrics, formulas, provenance, and limitations |
| [RAG_DESIGN.md](RAG_DESIGN.md) | Retrieval, answer generation, citations, and evaluation |
| [STATUS.md](STATUS.md) | Current working state and immediate next milestone |
| [BACKLOG.md](BACKLOG.md) | Prioritized work items |
| [DECISIONS.md](DECISIONS.md) | Short architecture decision log |
| [DOCUMENT_SURVEY.md](DOCUMENT_SURVEY.md) | Assessment of trustworthy official sources |
| [SOURCE_COVERAGE.md](SOURCE_COVERAGE.md) | Ten-district and two-period evidence coverage |
| [RAG_ROADMAP.md](RAG_ROADMAP.md) | Phased RAG-first expansion and acceptance gates |
| [KNOWLEDGE_BASE.md](KNOWLEDGE_BASE.md) | Versioned project and formula passages cited by RAG |

Update `STATUS.md` after meaningful work, `DECISIONS.md` when a choice changes architecture or methodology, and `CHANGELOG.md` when a user-visible release is made. Run `python scripts/check_markdown_links.py` after moving or renaming documentation.
