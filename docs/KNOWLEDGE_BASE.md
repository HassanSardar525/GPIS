# GPIS citable project knowledge

**Version:** `prototype-v1`  
**Scope:** Ten selected South Punjab districts

## Project scope and limitations

GPIS compares selected district indicators in education, listed public-health-facility availability, and budget-utilization accountability, plus an equal-weight overall score. It helps users inspect evidence and limitations. It does not establish that an individual politician caused a district result.

## RAG architecture

Exact observations, rankings, persisted scores, score components, and two-period changes come from deterministic application or SQL functions. Explanatory questions use PostgreSQL full-text search and local MiniLM vector retrieval, combined through reciprocal-rank fusion. Groq may phrase the response, but every factual sentence must cite an ID from the retrieved set; otherwise GPIS uses its extractive fallback. The LLM never calculates or changes scores.

## Education formula

The education score is the arithmetic mean of total literacy percentage, female literacy percentage, and gender parity. Gender parity is `100 - abs(male literacy - female literacy)`. The result is rounded to one decimal.

## Health formula

The health score totals the listed public facilities, divides by population to produce facilities per 100,000 residents, then min-max normalizes that rate from 0 to 100 within the fixed ten-district cohort. It measures relative listed facility availability, not quality or health outcomes.

## Accountability formula

Overall budget utilization is `100 - overall budget lapse percentage`. Development-budget utilization is `100 - development budget lapse percentage`. The accountability score is their arithmetic mean. It is a financial-utilization proxy, not proof of honesty, corruption, service quality, or impact.

## Overall formula

The overall score is the equal-weight arithmetic mean of education, health, and accountability, rounded to one decimal. It summarizes only the selected indicators and their current definitions.

## Temporal comparison formula

The only supported year-over-year metric is development-budget utilization: `expenditure / final grant * 100`. GPIS calculates it for FY 2022-23 and FY 2023-24, then subtracts the previous utilization from the current utilization to report a percentage-point change. This is not a change in the full accountability or overall score.
