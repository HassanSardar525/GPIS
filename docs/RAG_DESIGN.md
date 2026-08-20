# RAG design

## Purpose

The evidence assistant helps a user understand official district data without asking them to read large spreadsheets or audit reports. Retrieval-augmented generation is used for explanation, not scoring.

## Current implementation

1. The user submits a question and selected district.
2. A deterministic router selects exact fact, comparison, methodology, evidence, or unsupported handling.
3. SQL supplies exact observations, scores, and rankings.
4. PostgreSQL full-text search and 384-dimensional MiniLM cosine search retrieve filtered passages.
5. Reciprocal-rank fusion returns at most six deduplicated chunks; semantic-only hits below `0.35` are discarded.
6. Groq may write the answer at temperature `0.1`; every factual sentence must cite a retrieved evidence ID.
7. Unknown citations, provider errors, timeouts, and malformed output trigger the extractive fallback.
8. Unsupported or evidence-free questions abstain.

The application remains fully usable without a Groq key. Retrieved documents are treated as untrusted data and cannot supply instructions or modify scores.

## Required guardrails

- Never invent a missing value or citation.
- Never attribute district outcomes to one politician without causal evidence.
- State when geography or reporting periods do not match.
- Distinguish audit observations from proven fraud or corruption.
- Distinguish service capacity from service quality.
- Refuse unsupported candidate recommendations.

## Evaluation set

Maintain questions covering direct fact lookup, district comparison, score explanation, source and period questions, unsupported questions requiring abstention, and adversarial requests to blame a person or override a score.

The fixed 30-question fixture currently passes route accuracy `100%`, retrieval recall@5 `100%`, citation precision `100%`, and unsupported abstention `100%`. Run `python scripts/run_rag_evaluation.py --enforce` against PostgreSQL before changing routing, chunks, embeddings, or thresholds.
