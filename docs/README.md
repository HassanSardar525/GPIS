# GPIS documentation

This directory is the source of truth for product, technical, and evidence decisions.

| Document | Use it for |
|---|---|
| [PROJECT_SCOPE.md](PROJECT_SCOPE.md) | Goals, users, boundaries, and success criteria |
| [architecture.md](architecture.md) | Components, request flow, and replacement points |
| [DATA_AND_SCORING.md](DATA_AND_SCORING.md) | Metrics, formulas, provenance, and limitations |
| [RAG_DESIGN.md](RAG_DESIGN.md) | Retrieval, answer generation, citations, and evaluation |
| [Release plan](../PLANS.md) | Current release and deployment status |
| [Testing](testing.md) | Commands, release gates and experiment procedure |
| [Conventions](conventions.md) | Implementation and evidence requirements |
| [Status snapshot](STATUS.md) | Historical verification through 3 November 2026 |
| [DECISIONS.md](DECISIONS.md) | Short architecture decision log |
| [DOCUMENT_SURVEY.md](DOCUMENT_SURVEY.md) | Assessment of trustworthy official sources |
| [SOURCE_COVERAGE.md](SOURCE_COVERAGE.md) | Ten-district and two-period evidence coverage |
| [PUNJAB_SCORING.md](PUNJAB_SCORING.md) | Active 36-district methodology, sources and limitations |
| [HISTORICAL_EVIDENCE.md](HISTORICAL_EVIDENCE.md) | Tenure comparisons, source viewer, verified coverage and remaining gaps |
| [KNOWLEDGE_BASE.md](KNOWLEDGE_BASE.md) | Versioned project and formula passages cited by RAG |

Update `PLANS.md` after each phase, `DECISIONS.md` when a choice changes architecture or methodology, and `CHANGELOG.md` when a user-visible release is made. Run `python scripts/check_markdown_links.py` after moving or renaming documentation.
