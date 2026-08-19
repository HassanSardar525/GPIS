# RAG design

## Purpose

The evidence assistant helps a user understand official district data without asking them to read large spreadsheets or audit reports. Retrieval-augmented generation is used for explanation, not scoring.

## Current implementation

1. The user submits a question and selected district.
2. Retrieval is restricted to evidence for that district.
3. A lexical relevance score ranks reviewed evidence passages.
4. The generator builds a concise answer only from retrieved passages.
5. Publisher, document, period, URL, and locator are returned as citations.
6. If nothing relevant is found, the system abstains.

The current generator is extractive and deterministic, so the demo works without an API key.

## Planned hybrid RAG

The next architecture will combine:

- structured retrieval from PostgreSQL for exact metrics and ranks;
- vector and keyword retrieval for report passages;
- metadata filters for district, category, source, and period;
- an LLM used only after retrieval;
- citation validation before returning an answer.

## Required guardrails

- Never invent a missing value or citation.
- Never attribute district outcomes to one politician without causal evidence.
- State when geography or reporting periods do not match.
- Distinguish audit observations from proven fraud or corruption.
- Distinguish service capacity from service quality.
- Refuse unsupported candidate recommendations.

## Evaluation set

Maintain questions covering direct fact lookup, district comparison, score explanation, source and period questions, unsupported questions requiring abstention, and adversarial requests to blame a person or override a score.

Track retrieval hit rate, citation correctness, factual consistency, abstention quality, and response latency.
