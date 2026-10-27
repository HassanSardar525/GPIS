# Punjab-wide scoring implementation

Started 2026-10-22. Scope: the 36 district boundaries represented by Census 2023,
not a claim to cover every subsequently created administrative district.

## Plan

1. Acquire the official North Punjab Health and Education Authorities audit,
   Audit Year 2024-25; extract only DHA FY 2023-24 budget tables.
2. Produce a reproducible, source-linked curated contract for all 36 districts.
   Combine Census 2023 education/population, PHS 2024 Table 3 capacity as at
   2023-12-31, and FY 2023-24 DHA final grants/expenditure.
3. Implement `punjab-v1` separately from the immutable ten-district
   `prototype-v1`. Education retains the literacy formula. Health uses the same
   four reported institution types in all districts: hospitals, dispensaries,
   RHCs and BHUs, per 100,000 Census residents, min-max across all 36 districts.
   Accountability averages total and development utilization, bounding each
   score contribution to 0–100 while retaining uncapped figures and warnings.
   Overall gives the three categories equal weight. These remain proxies,
   not service quality, integrity or causal politician performance measures.
4. Wire both repositories, seeding, citations, profiles, rankings and map to
   the selected version. Never substitute an old financial year or infer zeros.
5. Consolidate current status documentation and remove redundant prototype
   artifacts only after checking references. Preserve source provenance,
   methodology, decision records, tests and raw document download instructions.
6. Verify source coverage, formulas, legacy reproducibility, database migrations,
   backend parity and browser behavior. Record results and commit.

## Acceptance

- Exactly 36 unique source districts with complete, finite scoring inputs.
- Every input has a source, exact locator, unit and reporting period.
- All budget score inputs use FY 2023-24 and DHA scope.
- Missing cells remain missing; overspending and source discrepancies remain visible.
- Old golden scores remain reproducible; new map values come from application data.
- Deployment never silently serves old scores under the new version label.
