# GPIS Official Document Survey

**Survey date:** 2026-08-20

**Purpose:** Select trustworthy, district-level documents that are practical for a one-week MVP.

## Evaluation criteria

Each source was assessed for:

- **Authority:** Is it published by the legally responsible government institution?
- **District coverage:** Does it provide comparable district-level records?
- **Usability:** Is it downloadable and reasonably machine-readable?
- **Meaning:** Does it measure an outcome, service capacity, spending, accountability, or only an announcement?
- **Comparability:** Can the same definition be compared across districts or periods?

Scores use 1 (poor) to 5 (excellent).

## Survey results

| Document/source | Authority | District coverage | Ease | What it can support | MVP decision |
|---|---:|---:|---:|---|---|
| PBS Population Census 2023 district Excel tables | 5 | 5 | 5 | Population denominators, literacy, enrolment, out-of-school population, housing/basic facilities | **Core** |
| Punjab Health Statistics 2024 and 2023 | 5 | 5 | 3 | Facilities, beds, patients, medical and paramedical personnel at district/tehsil level | **Core if files can be downloaded manually** |
| AGP Punjab South District Health Authorities audit report 2024–25 | 5 | 5 for 17 South Punjab districts | 4 | Audit findings, categories, amounts, recommendations, paragraph/page citations | **Core** |
| PBS PSLM district survey 2019–20 and earlier rounds | 5 | 5 | 4 | Literacy, enrolment, immunization, water, sanitation and other household outcomes | **Optional historical/outcome evidence** |
| Punjab Education Statistics 2022–23 and earlier annual editions | 5 | 5 | 3 | Schools, teachers, enrolment and education service statistics | **Optional annual comparison** |
| Punjab District Profiles 2023–24 | 5 | 5 | 3 | Convenient compilation of population, education, health, infrastructure, agriculture and economic activity | **Cross-check/backup** |
| MICS Punjab 2024 | 5 | Likely district-level; verify each table's sampling level | 3 | Recent outcomes for children, women, health, education and household welfare | **Optional after table-level verification** |
| Accountant General Punjab appropriation accounts | 5 | District Health and Education Authorities | 2 | Budget versus actual expenditure | **Phase 2 enhancement** |
| Punjab Annual Development Programme books | 5 | Mixed; many schemes include districts | 3 | Allocations and approved development schemes | **Context only** |
| ECP delimitation records and Punjab Assembly member directory | 5 | Constituency/district mapping | 4 | Constituencies, representatives, party and tenure | **Context only** |

## Recommended minimum document set

Use only these four groups for the initial MVP.

### 1. PBS Census 2023 district Excel tables

Use:

- Table 1 for population and growth/urbanization context.
- Table 12 for district literacy, enrolment and out-of-school population.
- Other district tables only when needed for denominators or basic-service context.

Why:

- Official national source.
- Excel is easier and safer to parse than PDF tables.
- Recent and consistent across Punjab districts.

Limit:

- Census indicators provide a snapshot, not an annual government-performance series.

Official index: https://www.pbs.gov.pk/result-excel/

### 2. Punjab Health Statistics 2024, with 2023 for comparison

Candidate metrics:

- Hospital/health institutions per 100,000 population.
- Beds per 100,000 population.
- Doctors or medical personnel per 100,000 population.
- Outpatient or inpatient load per facility/bed where definitions match.

Why:

- Published by the Bureau of Statistics Punjab.
- Specifically includes tehsil, district and division-level health capacity and activity.
- Annual editions allow a defensible year-over-year comparison for unchanged definitions.

Limit:

- The website may require a data-user form/CAPTCHA; acquire the file manually once and archive its checksum.
- Beds and doctors measure service capacity, not health outcomes or quality by themselves.

Official index: https://bos.punjab.gov.pk/health_statistics

### 3. AGP District Health Authorities audit report 2024–25

Extract:

- District.
- Audit paragraph number and page.
- Finding category.
- Amount involved.
- Recommendation.
- Whether the observation concerns procurement, HR, contract management, recordkeeping or another category.

Why:

- Official constitutional audit institution.
- One report covers the proposed South Punjab pilot districts under a common audit framework.
- Text-based PDF supports RAG citations.

Limits:

- An audit observation is not proof of corruption or guilt.
- Raw questioned amounts should not determine rank without normalization by audited expenditure/scope.
- Audit sampling and coverage may differ by district; expose these limitations.

Official PDF: https://www.agp.gov.pk/SiteImage/Policy/AR%20on%20the%20accounts%20of%2017%20%20district%20hrealt%20authorities%20of%20punjab%20south%202024-25.pdf

### 4. ECP and Punjab Assembly records

Use only for:

- Mapping districts to relevant constituencies.
- Displaying elected representatives and party affiliation.
- Displaying the responsible provincial-government period.

Do not use these records to calculate district performance.

Official indexes:

- https://ecp.gov.pk/delimitation-2023
- https://papnew.pap.gov.pk/members/

## Recommended pilot districts

Use five districts covered by the same Punjab South health audit report:

1. Multan
2. Bahawalpur
3. Rahim Yar Khan
4. Muzaffargarh
5. Dera Ghazi Khan

This keeps audit methodology and source coverage more consistent while Census and Punjab health statistics provide matching district records.

## Proposed factual matrix

### Education

| Metric | Source | Interpretation |
|---|---|---|
| Literacy rate | PBS Census 2023, Table 12 | Outcome/status indicator |
| Enrolment rate | PBS Census 2023, Table 12 | Participation indicator |
| Out-of-school population/rate | PBS Census 2023, Table 12 | Lower is better |

Do not call this annual improvement unless a directly comparable earlier table with the same definition is used.

### Health

| Metric | Source | Interpretation |
|---|---|---|
| Beds per 100,000 | Punjab Health Statistics + Census population | Capacity indicator |
| Medical personnel per 100,000 | Punjab Health Statistics + Census population | Capacity indicator |
| Patient load per bed/facility | Punjab Health Statistics | Pressure/utilization indicator; direction requires care |
| Fully immunized children | PSLM 2019–20, optional | Outcome/coverage indicator, not annual |

### Accountability

| Metric | Source | Interpretation |
|---|---|---|
| Audit findings by category | AGP report | Control/compliance risk signal |
| Questioned amount relative to audited expenditure | AGP report plus expenditure denominator if available | Financial exposure indicator |
| Severe categories present | AGP report | Risk flag, not proof of wrongdoing |
| Source coverage/sampling note | AGP report | Required confidence context |

The MVP should initially display accountability components separately. A composite accountability score should be added only after comparable audit denominators are confirmed.

## Comparison rules

- Compare districts only within the same document edition and metric definition.
- Compare years only when unit, population basis, geography and definition are unchanged.
- Say **“change since the previous comparable period”**, not “last year,” for periodic surveys.
- Recalculate count-based health metrics per 100,000 population.
- Show source year beside every value.
- Keep capacity, outcome and accountability scores separate.
- Do not merge data from MICS and PSLM into a trend unless methodology compatibility is demonstrated.
- Do not interpret budget allocation as delivered development or actual expenditure.

## Documents to avoid as scoring evidence

- Political speeches, manifestos and campaign promises.
- Press releases announcing project approval or launch.
- News articles that do not link to the primary dataset.
- Social-media posts and crowdsourced accusations.
- Dashboards without downloadable definitions and source metadata.
- Estimated district GDP unless an official reproducible methodology and series is available.
- LLM-extracted numbers that have not been validated against the source table.

These may be searchable context only if clearly labelled; they must not affect scores.

## Final recommendation

Start with **Census 2023 Excel + Punjab Health Statistics 2024/2023 + one AGP health audit PDF + ECP/Assembly context**. This is the strongest balance of trust, district coverage and implementation speed.

Use PSLM and MICS later to enrich health and education outcomes. Use appropriation accounts only after the core dashboard and RAG pipeline work, because accessing and normalizing expenditure data will consume more time.
