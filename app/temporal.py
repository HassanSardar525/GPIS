"""Deterministic period comparisons; the LLM never performs this arithmetic."""

from __future__ import annotations


PERIOD_ORDER = ("FY 2022-23", "FY 2023-24")


def development_budget_trend(periods: dict[str, dict[str, float]]) -> dict:
    records = []
    warnings = []
    for period in PERIOD_ORDER:
        values = periods.get(period)
        if not values:
            raise ValueError(f"Missing comparable development-budget data for {period}")
        grant = float(values["development_final_grant_million_pkr"])
        expenditure = float(values["development_expenditure_million_pkr"])
        if grant <= 0:
            raise ValueError(f"Final development grant must be positive for {period}")
        utilization = expenditure / grant * 100
        if utilization > 100:
            warnings.append(f"{period} expenditure exceeds the final development grant; utilization is above 100%.")
        records.append(
            {
                "period": period,
                "final_grant_million_pkr": round(grant, 3),
                "expenditure_million_pkr": round(expenditure, 3),
                "utilization_pct": round(utilization, 2),
            }
        )
    change = round(records[1]["utilization_pct"] - records[0]["utilization_pct"], 2)
    direction = "increased" if change > 0 else "decreased" if change < 0 else "unchanged"
    return {
        "metric": "development_budget_utilization_pct",
        "periods": records,
        "change_percentage_points": change,
        "direction": direction,
        "warnings": warnings,
    }
