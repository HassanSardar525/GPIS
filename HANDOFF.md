# GPIS handoff — 28 October 2026

## Punjab expansion baseline

The default `punjab-v1` contract scores all 36 Census 2023 Punjab districts.
`data/curated/punjab_districts.json` combines PBS Tables 1/12, PHS 2024
Table 3 (31 December 2023), and North/South DHA FY 2023–24 accounts.
The original `prototype-v1` contract and its ten-district fixtures remain available.
Do not append incompatible inputs to the legacy contract.

Rebuild with `python scripts/build_punjab_scores.py` after acquiring registered raw files.
Source hashes and locators are in the curated contract. North audit chapter tables
 take precedence over summaries; Mandi Bahauddin's conflicting development grant
is explicitly flagged. Health scores measure institution capacity, not care quality.
DHA utilization is not an integrity rating or a politician score.

The map, rankings, search/list selector and profiles use the active API cohort.
JSON and PostgreSQL support both score versions. New seeding preserves the 40
legacy score records and adds 144 new records. LF snapshot reproduction and
fresh-migration duplicate columns are fixed.

The 55-case Punjab deterministic RAG evaluation passes all acceptance metrics.
Database tests use separate disposable databases: `GPIS_TEST_DATABASE_URL`
for legacy tests and `GPIS_PUNJAB_TEST_DATABASE_URL` for Punjab parity/repeat-seed.
Browser checks use `GPIS_BROWSER_TEST_URL`.

## Implemented historical evidence feature

The Punjab baseline is committed as `9de2379`. The separate feature adds:

- `app/history.py`: deterministic observation/tenure comparisons, validation,
  JSON/PostgreSQL historical release and registered evidence assets.
- `app/history_chat.py`: named-person answers from records before model generation.
- `app/static/history.js`: profile charts, officeholder timeline, evidence dialog,
  highlighted scans/workbook cells, zoom, keyboard/mobile support and bookmarks.
- APIs `/api/v1/districts/{slug}/history`, `/officeholders`, and `/api/v1/evidence/{anchor_id}`.
- Additive migration `0007_historical_evidence`; ordinary seeding persists the release.
- 612 observations: health pairs for 36 districts, development spending pairs for
  17 South DHAs. Other historical measurements retain explicit review gaps.
- 300 officeholder entries: seven CMs, three caretaker portfolio records and
  290 archived MPA records from a **2021 biography**, not current MPAs. Most
  exact service/portfolio dates still need notifications. Do not invent them.
- 921 evidence anchors and 53 packaged original PDF images; no request-time parsing.

Read [historical evidence](docs/HISTORICAL_EVIDENCE.md) for rebuild commands,
source qualifications, API behavior and remaining curation work. `python -m app.history`
checks all packaged preview hashes without raw documents. Docker copies the assets
and runs that check. Restart after migration/seeding to load the atomic release.
Historical answers bypass model arithmetic.

Remaining research: 2017 education definitions/boundaries, older health editions,
North DHA cross-year geography, oath/end-date notifications, minister changes,
by-elections and vacancies. Existing scores and prototype fixtures stay unchanged.
Multan's comparative-table 1,013.030m grant differs from the 1,013.029m score input:
history discloses this and follows its own source, without changing scores.

Baseline verification: 159 tests passed, one browser test skipped in the full run.
The expired-session test initially counted old test sessions; it now cleans that
baseline first and is rerun separately. Live Chrome navigation/chart test passed.

Feature tests are in `tests/test_history.py` and `tests/test_history_browser.py`.
The 55-case Punjab RAG evaluation still passes all metrics. Original score fixtures
are retained; no political scoring was added.

Final checks: 183 passed in the full suite, two opt-in browser tests skipped there;
both Chrome tests passed separately against the live PostgreSQL-backed app.
All 53 packaged previews pass checksum validation. Local Alembic migration/seeding
is applied. Start on Windows with `python -m app.server` (Selector event loop).

General semantic RAG has an existing slow first MiniLM load. An initial live score
question exceeded 45 seconds, then passed in 0.64 seconds after the local model
loaded; offline-cache embedding returned 384 dimensions. Historical questions and
the evidence viewer do not need that model. Production Docker prepackages it.
