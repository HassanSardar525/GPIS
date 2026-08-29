# Data and scoring methodology

## Evidence contract

Each district record contains raw metrics, evidence passages, and source metadata. A usable factual observation must include:

- district and category;
- metric definition and value;
- reporting period;
- publisher and document title;
- official URL;
- table, row, or PDF-page locator.

Missing values must remain missing. They must never be converted to zero.

## Evidence-quality metadata

Reviewed observations can now record a definition version, geography level, population basis, comparability group, and quality flags. Score results can record a reporting period, coverage, confidence, missing components, and warnings.

These fields are additive for `prototype-v1`: its numeric scores and golden fixtures remain unchanged. Current `prototype-v1` coverage is 1.0 because every component required by that version is present, but this does not mean the proxy is comprehensive.

Coverage is eligible present component weight divided by expected component weight. Missing observations do not become zero. Confidence is evidence quality, not model probability: source authority receives 30%, recency 25%, measurement directness 25%, and cross-district comparability 20%. Reviewed inputs use ratings of 1.0, 0.75, or 0.5; evidence below 0.5 is excluded. Aggregate confidence is weighted over present components while coverage separately reports absence.

The reviewed Punjab Health Statistics Table 3 contract is stored in `data/curated/health_capacity_periods.json`. Original observations and per-100,000 derivatives retain source, locator, observation period, and the explicit Census 2023 population denominator. Printed dashes remain null.

## Education score

Current components:

- total literacy percentage;
- female literacy percentage;
- gender-parity component: `100 - abs(male literacy - female literacy)`.

```text
education = mean(total literacy, female literacy, gender parity)
```

This score measures literacy level and gender inclusion. It does not measure teaching quality or year-over-year improvement.

## Health-access score

The prototype totals listed DHA facilities and converts the result to facilities per 100,000 Census 2023 residents. It then applies min-max normalization within the ten-district cohort:

```text
rate = listed facilities / population * 100,000
health = (rate - cohort minimum) / (cohort maximum - cohort minimum) * 100
```

This is a relative availability proxy. Facility counts do not capture staffing, medicines, beds, utilization, accessibility, or quality.

## Accountability score

Current components:

- overall budget utilization: `100 - overall lapse percentage`;
- development budget utilization: `100 - development lapse percentage`.

```text
accountability = mean(overall utilization, development utilization)
```

This is better described as a public financial-management proxy. Budget utilization alone does not establish value for money, integrity, or impact.

## Overall score

```text
overall = mean(education, health, accountability)
```

All three categories currently receive equal weight. Version `prototype-v1` applies only to the ten selected districts.

## Staged `evidence-v2` methodology

`evidence-v2` is registered but inactive. It keeps the current education and accountability components unless a qualified source replaces them. Its health formula reserves 50% for capacity, 25% for activity, and 25% for outcomes. Scores below 75% component coverage are unranked, and missing weights are never redistributed.

Activation is blocked because no comparable second education period, annual district activity series, general district outcome series, or exact audit-finding expenditure denominator has passed review. The machine-readable decisions are in `data/curated/evidence_qualification.json`. Callers therefore receive `prototype-v1` explicitly; selecting `evidence-v2` fails rather than silently falling back.

## Rules for future changes

1. Never change a formula without changing the score version.
2. Keep raw observations separate from derived scores.
3. Add golden tests for manually calculated examples.
4. Show coverage and missing-data behavior in the UI.
5. Do not compare periods unless definitions and geography match.
