# Project scope

## Problem

Election discussion often emphasizes promises, visibility, and individual personalities. District performance data exists, but it is fragmented across official spreadsheets and audit documents and is difficult for ordinary citizens to interpret.

## Product goal

Give a citizen a simple, evidence-backed view of district conditions and administrative performance, with enough source detail to verify every important claim.

## Prototype users

- Citizens with limited statistical or technical knowledge.
- Journalists and civic researchers who need a fast evidence overview.
- Portfolio reviewers evaluating data engineering, scoring, and RAG design.

## MVP capabilities

1. Select one of five South Punjab districts.
2. View education, health access, and financial-management scorecards.
3. Compare the district with the other prototype districts.
4. Inspect source-backed component metrics.
5. Ask questions and receive evidence-grounded answers with citations.

## Non-goals for the current prototype

- Proving that an individual politician caused an outcome.
- Constituency-level scoring where the evidence is district-level.
- A Punjab-wide or Pakistan-wide ranking.
- Real-time data or automatic ingestion.
- Detecting corruption from audit text.
- Predicting election results or recommending a candidate.

## Success criteria

- A clean checkout starts without installing third-party packages.
- Every displayed factual metric has an official source and locator.
- Scores are deterministic and reproducible.
- The evidence assistant cites retrieved material and abstains when evidence is missing.
- Limitations are visible in the interface rather than hidden in documentation.
