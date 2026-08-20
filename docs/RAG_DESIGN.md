# RAG design

## Purpose

The evidence assistant helps a user understand official district data without asking them to read large spreadsheets or audit reports. Retrieval-augmented generation is used for explanation, not scoring.

## Current implementation

1. The browser creates a session ID and submits the question plus selected district filters.
2. A single LangGraph agent may answer conversation directly or call at most two tool rounds.
3. `district_data` supplies exact district lists, scores, rankings, comparisons, and two-period trends.
4. `evidence_search` uses exact facts plus PostgreSQL full-text and MiniLM pgvector retrieval with RRF.
5. `project_knowledge` retrieves citable scope, architecture, source, limitation, and scoring-methodology evidence.
6. LangGraph short-term memory retains messages and tool results for the browser session, so relevant context can be reused.
7. Groq writes the answer at temperature `0.1`; only citation IDs returned by tools are exposed through the API.
8. Invented citations, provider errors, timeouts, rate limits, or invalid agent output trigger the existing deterministic RAG fallback.
9. Without a Groq key, the previous deterministic router, extractive fallback, and abstention behavior remain available.

The application remains fully usable without a Groq key. Retrieved documents are treated as untrusted data and cannot supply instructions or modify scores.

## Required guardrails

- Never invent a missing value or citation.
- Never attribute district outcomes to one politician without causal evidence.
- State when geography or reporting periods do not match.
- Distinguish audit observations from proven fraud or corruption.
- Distinguish service capacity from service quality.
- Refuse unsupported candidate recommendations.
- Never allow the agent or its tools to calculate or modify stored scores.

## Evaluation set

Maintain questions covering direct fact lookup, district comparison, score explanation, source and period questions, unsupported questions requiring abstention, and adversarial requests to blame a person or override a score.

The fixed 60-question fixture currently passes route accuracy `100%`, retrieval recall@5 `100%`, citation precision `100%`, and unsupported abstention `100%`. Run `python scripts/run_rag_evaluation.py --enforce` against PostgreSQL before changing routing, chunks, embeddings, or thresholds.
