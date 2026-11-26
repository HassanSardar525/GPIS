# Historical changes, officeholders and exact evidence

Implemented 28 October 2026. The Punjab scoring baseline is commit `9de2379`.
This feature is additive: neither score formulas nor the two score contracts change.

## Published coverage

| Evidence | Coverage and limits |
|---|---|
| Health capacity | Four institution-count categories for all 36 census districts, at 1 January and 31 December 2023. Original Table 3 pages and component tehsil lists reviewed. Counts are not quality, access or outcomes. |
| Development spending | Final grant, expenditure and calculated utilization for the 17 South DHA authorities in the report's explicit FY 2022–23/FY 2023–24 comparison. Nominal Rs million. |
| North DHA history | The North report compares the same 19 DHAs across FY 2022–23 and FY 2023–24. Its development final grants match both district chapters for 16 authorities, expenditure for 16, and both inputs for 14. Total-budget and total-expenditure changes remain unverified. |
| Education | Census 2023 literacy for 36 districts. Five districts also have a verified 2017–2023 comparison. See the literacy source review below. |
| Chief ministers | Seven named entries spanning the research period. Four have usable reviewed date intervals; early oath dates and Hamza Shahbaz's handover remain qualified. |
| Ministers | Three caretaker portfolio records reported in January 2023. Exact portfolio start/end notifications remain unverified. |
| MPAs | 290 constituency/name/party records from the Assembly's **2021 publication for the 2018 assembly**, spanning all 36 districts. These are archived representation records, not current MPAs or verified full terms. |
| Previews | 57 original PDF page images, plus original workbook cells and headings. Reviewed highlights cover health rows, the comparative development table and workbook cells; other anchors offer a registered page or official source. |

The release contains 655 observations, 300 officeholder records and 964 anchors.
Research starts at 2017; this does **not** mean annual data exists from 2017 onward.
Missing records never imply zero or an office vacancy. MPA membership changes,
by-elections, vacancies, ministerial changes and full date notifications remain
explicit coverage gaps. The schema and matching code support these records when verified.

## Important source qualifications

- The PHS 2023 scanned pages were manually read. The four district count sums
  independently match the printed province totals: 339 hospitals, 1,185
  dispensaries, 374 RHCs and 2,533 BHUs. Original district/tehsil groupings remain
  consistent in the two editions, including areas subsequently split administratively.
- The health snapshots cover two dates within 2023, not a 2023–2024 annual trend.
  Changes can reflect reporting revisions. Lahore's large changes are preserved,
  without interpreting them as improved or worsened treatment.
- Multan's comparative development table prints **1,013.030 million** final grant
  for FY 2023–24. The existing score input is **1,013.029 million**. The history
  follows its cited comparative table, flags the conflict and leaves scores unchanged.
- Parvez Elahi's oath is dated 27 July 2022 by the Presidency, although the CM
  summary lists 26 July. Mohsin Naqvi's oath occurred Sunday night, 22 January
  2023; the report was published the following day. Publication is not office start.
- A politician's party belongs to the archived period, not a claim about current
  affiliation. Caretaker is represented separately from party.

### North DHA development review, 26 November 2026

The two-year tables identify the authority, fiscal years and units. Final grants are on PDF pages 22–23 (printed 4–5), and expenditure is on pages 23–24 (printed 5–6). The 19 rows sum to the printed final grants of 2,057.747 and 1,059.489 million rupees and expenditure of 801.684 and 557.664 million rupees. The final-grant table’s source footer mentions 2021–22, although its columns specify 2022–23 and 2023–24. Each published change therefore also requires agreement with both fiscal-year chapter figures. [Official North audit report](https://agp.gov.pk/SiteImage/Policy/AR%20on%20account%20of%2019%20DHand%20Education%20Authorities%20AY%202024-25.pdf#page=22)

The following FY 2023–24 figures differ (chapter / comparison table, Rs million). The history panel preserves the chapter reading, links both sources and withholds the affected change and utilization comparison.

| Authority | Final grant | Expenditure |
|---|---|---|
| Gujranwala | | 3.850 / 3.853 |
| Mandi Bahauddin | 380.562 / 30.562 | |
| Nankana Sahib | 4.030 / 4.031 | 4.030 / 4.031 |
| Okara | | 29.677 / 29.679 |
| Sheikhupura | 67.389 / 67.390 | |

### Literacy baseline review

Figure 3.18 explicitly compares both censuses for Rawalpindi, Gujrat, Jhelum, Lahore and Sialkot. The paragraph above it gives the 2017 rates to two decimal places. Each 2023 rate agrees with the reviewed Table 12 workbook when rounded to the figure’s precision. For example, Lahore rose from 77.08% to 79.62%, a change of 2.54 percentage points. The remaining 31 districts require separate verification. [PBS provincial census report, printed page 84](https://www.pbs.gov.pk/wp-content/uploads/2020/07/Provincial-Census-Report-2023-Punjab.pdf#page=108)

PBS publishes the 2017 ages-10-and-over district literacy figures in *Social Indicators of Punjab*, Table 4.01. Use the all-area, all-sexes literate row. Before publishing a district change, verify its 2017 and 2023 reporting boundaries, literacy definition and denominator, then register both table locations. [PBS district figures](https://www.pbs.gov.pk/wp-content/uploads/2020/07/Social_Indicators_of_Punjab_v2.pdf) · [PBS census archive](https://www.pbs.gov.pk/censusarchive/)

## API and deterministic matching

`GET /api/v1/districts/{slug}/officeholders` returns records and coverage notes.

`GET /api/v1/districts/{slug}/history?metric=phs_hospitals_count&tenure=naqvi-2023`
returns observations, units, evidence anchors, coverage and a Python-calculated
comparison. The optional tenure restricts the comparison to observations whose
**whole measurement intervals** fit inside a verified term. Context observations
remain in the response with `within_selected_tenure` flags for the chart.

Measurements must match metric, definition, population group, unit, geography and
reviewed comparability group. Null values and overlapping measurement intervals
cannot produce a change. Percentage changes in percentage-valued metrics are
reported as percentage points. Fiscal years are inclusive July–June intervals;
all recorded overlapping administrations are shown, with uncertain dates qualified.
No spending is apportioned at a handover. Unknown service dates are not inferred.

`GET /api/v1/evidence/{anchor_id}` returns registered locations and preview URLs.
`GET /api/v1/evidence-assets/{filename}` serves only registered files from the
packaged evidence directory, with resolved-path confinement. Neither endpoint
accepts arbitrary source URLs or raw filesystem paths. User requests never render
PDFs, invoke OCR, download reports or open raw spreadsheets.

Citation contracts add optional `anchor_ids`. Existing fields remain intact.
Calculated score anchors explain the method and link to their input evidence.

## Storage and rebuilding

- `data/curated/officeholder_register.json`: reviewed provincial records and source register.
- `data/curated/health_history_review.json`: manual scan transcription and row rectangles.
- `data/curated/history.json`: complete versioned publication, including workbook excerpts.
- `data/evidence/*.png`: original full-page previews, pinned by source and asset checksums.
- Migration `0007_historical_evidence`: additive `historical_releases` JSONB table.
  A complete validated release is upserted atomically during ordinary seeding.
  This avoids publishing half-updated terms and evidence. Scores are untouched.

With the checksum-pinned raw files available:

```powershell
python scripts/curate_officeholders.py
python scripts/curate_health_history.py
python scripts/build_history.py
python -m app.history
alembic upgrade head
python -m app.cli seed
```

The Assembly biography is registered at its official PDF URL in the release.
The other raw URLs/hashes come from the current source contracts. The builder
checks existing hashes; adding a source requires deliberate review. Rectangles
use top-left normalized coordinates `[left, top, right, bottom]` against original
page dimensions. PDF page numbers are one-based and separate from printed labels.
Spreadsheet excerpts retain source cell addresses, district headings and sex
column headings. Web records are explicitly reviewed summaries, not verbatim quotes.

Restart the application after reseeding. JSON and PostgreSQL load an atomic release
into memory; they do not poll for curator edits. The Dockerfile copies all previews
and runs `python -m app.history` to reject missing/corrupt assets at build time.
Runtime parsing libraries and the developer's `data/raw` directory are unnecessary.
On Windows, use `python -m app.server`; its Selector event loop is required by
the asynchronous PostgreSQL checkpoint pool.

## Ask GPIS and interface

The District Profile contains category controls, dated observations and an
officeholder timeline alongside Ask GPIS. Selecting a tenure highlights the dates
and eligible observations. The evidence dialog supports keyboard activation,
Escape, zoom, full-page context, registered-page navigation, source text and official links.
Links such as `#/district/multan?evidence=ev-...` are bookmarkable. Opening a citation
does not clear the district, chat answer or unsent question.

Named-person/tenure questions use a deterministic historical-record route before
either model provider. The language model does not calculate changes or match
dates. Source-backed names are allowed; causal blame and personal allegations are
not inferred from district statistics. Queries without sufficient observations
state the gap. Original district retrieval and score evaluation remain available.

## Verification

Tests cover caretaker and mid-year overlaps, unknown dates, vacancies, units,
boundary changes, missing values, nominal spending, percentage points, source
conflicts, exact page labels, scanned highlights, workbook cells, registered-asset
access, backend parity, named-person chat and preserved score fixtures.
Chrome checks cover chat/chart citations, deep links, mobile overflow, keyboard
access, draft/session preservation and escaped chat content.

The 55-case Punjab deterministic RAG benchmark still passes every acceptance
metric. These results do not claim complete officeholder research or full yearly
coverage. Next curation priorities are official oath/end-date notifications,
the remaining 31 literacy baselines, earlier health editions, the five North DHA source conflicts and comparability of total budgets.

General semantic RAG still lazily loads MiniLM. The local first score-question smoke
test exceeded 45 seconds during that cold start; the model worked from its offline
cache and the same live PostgreSQL question then returned in 0.64 seconds, including
its calculated-score evidence anchor. Historical-record answers do not load MiniLM.
