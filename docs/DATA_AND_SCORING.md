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

These fields are additive for `prototype-v1`: its numeric scores and golden fixtures remain unchanged. Current `prototype-v1` coverage is 1.0 because every component required by that version is present, but this does not mean the proxy is comprehensive or high-confidence. Confidence remains null until a documented evidence-quality rule is approved; the application must not invent a probability.

The reviewed Punjab Health Statistics Table 3 contract is stored separately in `data/curated/health_capacity_periods.json` until its observations, coverage behavior, and new score version pass JSON/PostgreSQL parity tests.

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

## Rules for future changes

1. Never change a formula without changing the score version.
2. Keep raw observations separate from derived scores.
3. Add golden tests for manually calculated examples.
4. Show coverage and missing-data behavior in the UI.
5. Do not compare periods unless definitions and geography match.
