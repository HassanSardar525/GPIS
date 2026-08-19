# Project status

**Last updated:** 2026-08-20

**Current milestone:** Prototype v0.1

**State:** Working locally

## Completed

- [x] Selected five South Punjab pilot districts.
- [x] Downloaded and inspected PBS Census and Auditor-General sources.
- [x] Created a reviewed evidence contract with source/page metadata.
- [x] Implemented deterministic education, health, accountability, and overall scores.
- [x] Implemented district APIs and ranking APIs.
- [x] Built a responsive browser dashboard.
- [x] Built citation-grounded lexical retrieval and abstention.
- [x] Added automated tests; all four currently pass.
- [x] Added architecture, methodology, RAG, status, backlog, and decision documentation.

## In progress

- [ ] Publish the initial Git repository to GitHub.

## Next milestone

Add an optional LLM generation layer while retaining the deterministic fallback and citations. Then replace the lexical-only retriever with hybrid structured plus vector retrieval.

## Known limitations

- Only five districts and one main period are covered.
- Health and accountability are provisional proxies.
- Raw source acquisition is manual.
- The chat endpoint does not yet call an LLM.
- No authentication, deployment pipeline, or monitoring exists.
