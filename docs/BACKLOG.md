# Backlog

Items are ordered by current priority. Move an item into `STATUS.md` when active.

## P0 - Make the RAG demo stronger

- [ ] Add optional LLM generation behind a provider interface.
- [ ] Preserve the current deterministic fallback when no API key is configured.
- [ ] Build a 20-question RAG evaluation fixture.
- [ ] Validate that every generated factual sentence maps to a returned citation.
- [ ] Add structured comparison answers using score components from the API.

## P1 - Improve evidence and scoring

- [ ] Acquire Punjab Health Statistics for staffing, beds, and activity indicators.
- [ ] Add a second comparable period where definitions match.
- [ ] Replace the health proxy with a multi-component capacity/outcome score.
- [ ] Expand accountability beyond utilization using carefully normalized audit indicators.
- [ ] Add coverage and confidence fields to every score.

## P1 - Production-shaped architecture

- [ ] Migrate HTTP routes to FastAPI.
- [ ] Store facts and provenance in PostgreSQL.
- [ ] Store evidence embeddings in pgvector.
- [ ] Add a repeatable validation/import command.
- [ ] Add Docker Compose for local development.

## P2 - User experience

- [ ] Add Urdu labels and plain-language score explanations.
- [ ] Add district-to-district comparison view.
- [ ] Add score component charts and source previews.
- [ ] Improve keyboard and screen-reader accessibility.
- [ ] Add representative/constituency context without causal attribution.

## P2 - Delivery

- [ ] Add continuous integration for tests.
- [ ] Add production deployment configuration.
- [ ] Add observability and privacy-safe usage analytics.
- [ ] Record a short portfolio demonstration video.
