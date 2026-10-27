# GPIS handoff — 27 October 2026

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

## Next accepted feature

Historical observations alongside provincial officeholders from 2017, plus an
exact-page/cell evidence panel. Keep scores unchanged. Publish verified comparisons
and explicit gaps. Distinguish election, appointment and oath dates. Pre-render
assets; user requests must never download or parse raw reports.
See `docs/PUNJAB_SCORING.md` and `docs/SOURCE_COVERAGE.md` for baseline limitations.

Baseline verification: 159 tests passed, one browser test skipped in the full run.
The expired-session test initially counted old test sessions; it now cleans that
baseline first and is rerun separately. Live Chrome navigation/chart test passed.
