# Punjab-wide scoring: punjab-v1

This version covers the 36 district boundaries represented in Census 2023.
It is a source-based, provisional comparison of selected indicators, not a
comprehensive assessment of governance or an individual politician.

## Sources and periods

The complete input contract is `data/curated/punjab_districts.json`. Each district
contains population, education, four health-capacity counts, financial-utilization
inputs, raw observations, source warnings and citable evidence. The original
`districts.json` is retained as the immutable ten-district `prototype-v1` baseline.

- PBS Census 2023 Tables 1 and 12: population, literacy and out-of-school children.
- Punjab Health Statistics 2024 Table 3: public institutions and beds as at
  31 December 2023, PDF pages 19–23. Only four fully reported institution types
  enter the score. Other capacity observations remain available as facts.
- South Punjab DHA audit, Audit Year 2024-25: FY 2023-24 final grants and
  expenditure, Annexure D, PDF pages 302–304, for 17 districts.
- [North Punjab Health and Education Authorities audit, Audit Year 2024-25](https://agp.gov.pk/SiteImage/Policy/AR%20on%20account%20of%2019%20DHand%20Education%20Authorities%20AY%202024-25.pdf):
  FY 2023-24 DHA district variance tables for the other 19. Education-authority
  and Daanish-school figures from this combined report are excluded.

The acquisition/parser entry point is `python -m scripts.build_punjab_scores`.
Install `.[ingestion]` and download the registered raw sources first. The North
PDF is pinned to SHA-256
`e0e567d66ba77c993c1ad6ece3cf704c978790eb1b69efeff4e58e4a992cf713`.
The parser checks headers, column counts, district coverage, units and fiscal
year; its output retains exact PDF/XLSX locators and North table row text.

## Education formula

Mean of total literacy, female literacy and `100 - abs(male - female literacy)`.
Round to one decimal. This is literacy and gender inclusion, not school quality.

## Health formula

Count hospitals + dispensaries + RHCs + BHUs from the same PHS table. Divide by
Census 2023 district population and multiply by 100,000. Min-max normalize across
the fixed 36-district cohort and round to one decimal. If all rates are equal,
assign 50 to all. A score of zero means the lowest rate in this cohort; it does
not mean there are no facilities. Different facility types are counted equally;
size, staffing, quality, referral demand and outcomes are not measured.

Do not map PHS hospitals into invented DHQ/THQ categories or turn printed dashes
into zero. This definition differs from the old DHA facility listing, so it has
a new version and must not be interpreted as improvement over prototype-v1.

## Accountability formula

For total and development spending separately:
`raw utilization = expenditure / final grant * 100`.
Bound each contribution to 0–100, average them and round to one decimal.
The raw values, including overspending, remain visible. This measures utilization
of District Health Authority budgets only, not all district expenditure, value
for money, honesty or corruption. Zero or missing final grants block scoring.

## Overall formula

Equal-weight mean of the three rounded category scores, rounded to one decimal.
Ranking uses score descending and district name as the tie breaker, matching
the existing API. These snapshots span Census 2023 and FY 2023-24; no annual
trend in overall score is inferred. Two-period development trends remain limited
to the original ten reviewed series.

## Source conflicts and limitations

North inputs consistently use each district's detailed variance table, not the
nearby comparative narrative or provincial summary. Differences in printed
precision and internal arithmetic are preserved, not silently corrected.

Mandi Bahauddin is a material case: PDF 57 (printed 39) gives development final
grant **380.562 million**, while PDF 22 (printed 4) gives **30.562 million**.
The detailed table is used, with a warning beside its accountability and overall
scores. Its rank is sensitive to this source conflict; the source does not allow
us to establish which number is correct. Lahore's detailed final total is
5472.330 million versus 5472.331 in the adjacent narrative. Other small rounding
differences also exist. These are provisional scores based on the named tables.

Coverage of 100% means all formula inputs are present, not that the evidence is
perfect. Numerical confidence is deliberately unassessed, rather than copying
ratings from the old methodology. Warnings are included in API score details.

## Operation and compatibility

Use `GPIS_SCORE_VERSION=punjab-v1` and `python -m app.cli bootstrap` with PostgreSQL.
The application default and deployment examples select this version. Seeding
retains 40 original score records and adds 144 Punjab score records. Select
`prototype-v1` explicitly to reproduce the old ten-district scores. `evidence-v2`
remains inactive: it requires outcome/activity evidence not available here.
