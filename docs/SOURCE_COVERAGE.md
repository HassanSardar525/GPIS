# Source coverage for the RAG-first expansion

## Verified current-period coverage

The PBS Census 2023 district workbooks contain population and literacy blocks for all Punjab districts. The Auditor-General report covers seventeen District Health Authorities and contains current health-facility, audited-formation, and FY 2023-24 budget tables.

The five added districts are Khanewal, Layyah, Lodhran, Rajanpur, and Vehari. Each appears in:

- PBS Census 2023 Table 1 for population;
- PBS Census 2023 Table 12 for literacy and out-of-school population;
- Audit report Annexure-B for health facilities (PDF page 300 / printed page 289);
- Annexure-C for audited formations (PDF page 301 / printed page 290);
- Annexure-D for FY 2023-24 budget and expenditure (PDF pages 302-304 / printed pages 291-293).

## Verified two-period coverage

Audit report PDF page 26 (printed page 15) provides final development grant and expenditure for FY 2022-23 and FY 2023-24 for all ten selected districts. This supports a comparable temporal metric:

```text
development utilization = development expenditure / final development grant * 100
percentage-point change = current utilization - previous utilization
```

This first trend is narrower than the accountability composite. It must be labelled **development-budget utilization**, not overall development, impact, corruption, or politician performance.

Punjab Health Statistics 2023 Table 3 (snapshot 01-01-2023) and Punjab Health Statistics 2024 Table 3 (snapshot 31-12-2023) use the same district/tehsil layout, eight facility categories, institution/bed columns, and six contributing agencies. The reviewed contract in `data/curated/health_capacity_periods.json` records both snapshots for all ten pilot districts.

This series supports changes in reported public health-facility and bed capacity only. Printed dashes remain null because the publication defines them as "nil or insignificant." Source anomalies are preserved with warnings rather than corrected or inferred.

The editions do not provide comparable district staffing or general health-outcome series suitable for scoring. District patient-activity tables remain pending because the earlier edition does not state a sufficiently clear annual interval for a temporal comparison.

All ten pilot district rows on registered Table 3 pages 4, 6, and 7 were checked against both official editions. Facility and bed values, printed dashes, and the retained Rajanpur MCH anomaly match the curated contract.

## Candidate evidence decisions

No earlier education source is accepted as a trend because the current repository contains only Census 2023 district literacy and no acquired edition has verified equivalent indicators, geography, units, and methodology.

The audit report supports budget-utilization and audited-formation facts. Finding counts and questioned amounts remain outside scoring because their scope does not have one exact, comparable district expenditure denominator. These and the health activity/outcome exclusions are recorded in `data/curated/evidence_qualification.json`; consequently `evidence-v2` remains inactive.

## Unsupported temporal claims

The current source set does not contain comparable two-period inputs for literacy, district staffing, general health outcomes, the full accountability composite, or the overall GPIS score. Those changes remain unavailable until equivalent official sources are added. The reviewed health-capacity series is evidence and normalized capacity data, but it is not part of the active score version.
