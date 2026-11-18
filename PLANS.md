# GPIS first release

Let a visitor find a district, compare a same-period metric, inspect historical representation and ask a cited follow-up.

- [x] Set up contributor workflow and consolidate the dated handoff.
- [ ] Deliver district-first navigation, comparable source-backed values and dated representation. Review desktop and mobile screenshots.
- [ ] Prepare the release candidate database and enforce document and live generation checks.
- [ ] Exercise the deployed candidate in desktop and mobile browsers. Record the candidate revision and results before merge.
- [ ] Publish from merged main and repeat the deployed acceptance journey.
- [ ] Add repeatable component, pipeline and application checks plus a curated LangSmith dataset and experiment.

## Decisions

Use the 36-district punjab-v1 contract, existing API, Render and PostgreSQL/pgvector. Preserve the prototype score version. Use LangSmith for curated experiments only. Human-reviewed exact facts remain authoritative. Calibrate judge scores before considering them for release gates.

## Remaining work

A release requires a successful live explanation, document retrieval, unsupported answer and provider failure check, plus the Multan to Lahore browser journey. Record actual results here. Existing historical results are in [project status](docs/STATUS.md).
