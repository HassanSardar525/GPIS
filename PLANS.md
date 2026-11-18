# GPIS first release

Let a visitor find a district, compare a same-period metric, inspect historical representation and ask a cited follow-up.

- [x] Set up contributor workflow and consolidate the dated handoff.
- [x] Deliver district-first navigation, comparable source-backed values and dated representation. Review desktop and mobile screenshots.
- [x] Prepare the release candidate database and enforce document and live generation checks.
- [ ] Exercise the deployed candidate in desktop and mobile browsers. Record the candidate revision and results before merge.
- [ ] Publish from merged main and repeat the deployed acceptance journey.
- [x] Add repeatable component, pipeline and application checks plus a curated LangSmith dataset and experiment.

## Decisions

Use the 36-district punjab-v1 contract, existing API, Render and PostgreSQL/pgvector. Preserve the prototype score version. Use LangSmith for curated experiments only. Human-reviewed exact facts remain authoritative. Calibrate judge scores before considering them for release gates.

## Verification record

A release requires a successful live explanation, document retrieval, unsupported answer and provider failure check, plus the Multan to Lahore browser journey. Record actual results here. Existing historical results are in [project status](docs/STATUS.md).

Local UI review used 390px and 1280px screenshots. Nine UI and browser checks passed. The comparison table wraps its cells on narrow screens.

The local PostgreSQL candidate passed the 59-case baseline, including all four document cases. Both originals reproduced 78 chunks (72 district rows and six parents). Hosted deployment is deferred by the owner.

The six-case curated LangSmith experiment uses a content-versioned dataset. Judge scores remain advisory pending independent human calibration.

Hosted experiment gpis-curated-f454244e passed six factual checks. Four judge calls were rate limited. The evaluator now honors bounded Retry-After delays and accepts an independently selected judge model.

Generation configuration regression: the historical hard-coded Gemini choices ignored the configured model. The model list and generation now use GEMINI_MODEL. The local release uses the Render Groq model openai/gpt-oss-20b.

Clean-runner CI reproduced two missing-workbook failures. CI now retrieves checksum-verified originals before database and document tests. The local release gate passed on PostgreSQL with live Groq, extractive lookup, abstention and all five application/outage tests.


## Deferred work

Hosted pre-merge acceptance and the production deployment await the owner's Render setup. Human calibration of the advisory judge is pending. Future research and product ideas include a comparable earlier education period, expanded health and financial indicators, Urdu labels, operational alerting and a portfolio demonstration.

Generation regression from the hosted experiment: Lahore’s correct 718,199 count cited a calculated education score. The district tool now returns census evidence for census facts even when the district has scores, and the agent validates the source before displaying the generated answer.

Tenure citation regression: the chief-minister history preview named the officeholders but omitted their recorded handover dates. Verified the official history, retained the separately qualified Elahi oath date, and added inline sources to the overlap statements.

Evaluator regression: the judge treated an earlier Multan question as an additional requirement of the Lahore follow-up. The evaluator now labels the current request, district selection and earlier context separately.

The GitHub runner reached PBS but timed out connecting to the official health PDF host. CI now extracts PHS2024 from the previously verified public multi-edition mirror and checks the original SHA-256. Production provenance continues to point to the Bureau of Statistics.
