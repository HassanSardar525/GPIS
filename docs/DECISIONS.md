# Decision log

## ADR-001: District is the scoring geography

**Status:** Accepted

**Decision:** Score districts because official outcome datasets use district boundaries. Constituencies and representatives may be shown only as context.

**Reason:** Electoral and administrative boundaries do not align reliably enough for constituency attribution.

## ADR-002: Scores are deterministic

**Status:** Accepted

**Decision:** Calculate all scores in ordinary code from structured metrics.

**Reason:** Reproducibility, auditability, and protection against prompt-dependent scoring.

## ADR-003: RAG explains but does not score

**Status:** Accepted

**Decision:** Retrieval and generation may summarize evidence and methodology but cannot calculate or modify a score.

**Reason:** A language model is unsuitable as the source of record for a public performance index.

## ADR-004: Manual evidence contract before ingestion automation

**Status:** Accepted

**Decision:** Use a small manually reviewed JSON contract for the first vertical slice.

**Reason:** It delivers a trustworthy demo quickly and exposes the schema needed for a later ingestion pipeline.

## ADR-005: Dependency-free first server

**Status:** Accepted

**Decision:** Use Python's standard-library HTTP server for v0.1.

**Reason:** A clean checkout can run immediately. Module boundaries preserve a straightforward FastAPI migration path.

## ADR-006: Raw official documents are not committed

**Status:** Accepted

**Decision:** Keep raw PDF/XLSX files local and version the reviewed evidence plus download instructions.

**Reason:** Smaller repository, clearer provenance workflow, and less duplication of third-party publications.
