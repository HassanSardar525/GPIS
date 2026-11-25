# GPIS first release

Let a visitor find a district, compare a same-period metric, inspect historical representation and ask a cited follow-up.

- [x] Set up contributor workflow and consolidate the dated handoff.
- [x] Deliver district-first navigation, comparable source-backed values and dated representation. Review desktop and mobile screenshots.
- [x] Prepare the release candidate database and enforce document and live generation checks.
- [ ] Exercise the deployed candidate in desktop and mobile browsers. Record the candidate revision and results before merge.
- [ ] Publish from merged main and repeat the deployed acceptance journey.
- [x] Add repeatable component, pipeline and application checks plus a curated LangSmith dataset and experiment.
- [x] Update the README with the implemented district journey, evidence coverage, RAG evaluation results, setup commands, and pending Render acceptance.
- [x] Add opt-in development chat traces. Verified two turns from the rebuilt local Compose API in the same `gpis-local` LangSmith thread, with each hosted run matching the API trace ID.

## Decisions

Use the 36-district punjab-v1 contract, existing API, Render and PostgreSQL/pgvector. Preserve the prototype score version. Use curated data for LangSmith experiments. Developers can also enable local session tracing. Human-reviewed exact facts remain authoritative. Calibrate judge scores before considering them for release gates.

## Verification record

Application candidate `0a6a5fe` ran locally at `http://127.0.0.1:8177` against PostgreSQL/pgvector and Redis with the Render Groq model, `openai/gpt-oss-20b`. Revision `a108d33` corrects evaluation of age ranges and leaves the application code identical.

| Check | Result |
| --- | --- |
| Full regression suite | All 204 tests passed on `a108d33` with fresh legacy/Punjab test databases and both browser widths. One upstream Starlette TestClient deprecation warning. [GitHub PR CI](https://github.com/HassanSardar525/GPIS/actions/runs/44370418263) also passed. |
| Migration, seed, embeddings and document ingestion | 36 districts, 1,373 observations and 184 score results. Re-ingestion verified all 78 document chunks against the original sources. |
| Deterministic RAG | 59 cases ran, including all four required document cases. Routing, measured answer accuracy, recall at five, citation precision and unsupported abstention each scored 1.00. |
| Live API and failure paths | Verified a generated Groq explanation, extractive document lookup, unsupported abstention and cited fallback during an injected outage. |
| Desktop and mobile | The 1,280px and 390px journeys verified Multan 61.41% and Lahore 79.62%, opened their workbook cells B1614 and B1284, inspected archived representation and asked a district-scoped follow-up. |
| Packaged evidence | All 53 original-page previews validated. |
| Hosted curated evaluation | LangSmith experiment `gpis-curated-0496c07d` on `a108d33` passed all six factual checks. The advisory judge scored grounding and relevance positively on all six. Only curated inputs were used. |

The hosted evaluation reproduced a correct Lahore count attached to an education-score citation, a tenure passage missing the handover dates, and evaluator mistakes with reversed district/value phrasing, age ranges and a changed district in a follow-up. Each correction has its own commit. CI uses the verified public archive for the health source because the official host timed out from a GitHub runner. See [testing](docs/testing.md) for reproduction commands.

## Remaining work

- The owner plans to set up Render later. Keep [the release PR](https://github.com/HassanSardar525/GPIS/pull/1) in draft until hosted acceptance passes. Deploy production from merged main.
- Have a human reviewer label held-out examples before adopting the judge as a release gate.
- Longer-term work includes a comparable earlier education period, richer health and financial indicators, Urdu labels, operational alerting and a portfolio demonstration.

## Frontend refresh

- [x] Phase 1. Shared theme tokens and System, Light and Dark control. Verified switching on all three existing routes in Chrome.
- [x] Phase 2. District-first navigation and layouts.
- [x] Phase 3. Section feedback and retry controls, source links, keyboard and theme regressions. Browser journeys passed at 390 and 1280 px.
- [ ] Release acceptance. Hosted Render verification is pending. The local default Gemini live explanation returned the extractive fallback.
- [x] Mobile follow-up. Reproduced overlapping map controls at 390 px, separated them, and verified their bounds and screenshots in both themes. Body, muted and link text meet 4.5:1 against the page and panel surfaces.
