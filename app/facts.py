"""Map plain-language fact questions to structured metric keys."""

from __future__ import annotations


METRIC_LABELS = {
    "population_2023": "Population (2023)",
    "literacy_total_pct": "Total literacy",
    "literacy_male_pct": "Male literacy",
    "literacy_female_pct": "Female literacy",
    "out_of_school_children_5_16": "Out-of-school children aged 5-16",
    "government_dispensaries": "Government dispensaries",
    "bhus": "Basic Health Units (BHUs)",
    "rhcs": "Rural Health Centres (RHCs)",
    "thq_hospitals": "THQ hospitals",
    "dhq_hospitals": "DHQ hospitals",
    "overall_budget_lapse_pct": "Overall budget lapse",
    "development_budget_lapse_pct": "Development budget lapse",
}


def requested_metrics(question: str) -> list[str]:
    query = question.casefold()
    metrics: list[str] = []
    if "population" in query:
        metrics.append("population_2023")
    if "literacy" in query:
        if "female" in query:
            metrics.append("literacy_female_pct")
        elif "male" in query:
            metrics.append("literacy_male_pct")
        else:
            metrics.append("literacy_total_pct")
    if "out of school" in query or "out-of-school" in query:
        metrics.append("out_of_school_children_5_16")
    if "dispensar" in query:
        metrics.append("government_dispensaries")
    if "bhu" in query or "basic health unit" in query:
        metrics.append("bhus")
    if "rhc" in query or "rural health centre" in query or "rural health center" in query:
        metrics.append("rhcs")
    if "thq" in query:
        metrics.append("thq_hospitals")
    if "dhq" in query:
        metrics.append("dhq_hospitals")
    if "budget" in query and "lapse" in query:
        metrics.append("development_budget_lapse_pct" if "development" in query else "overall_budget_lapse_pct")
    return list(dict.fromkeys(metrics))


def format_fact(name: str, metric: str, value: float, unit: str) -> str:
    label = METRIC_LABELS.get(metric, metric.replace("_", " ").title())
    if unit == "percent":
        rendered = f"{value:.2f}%"
    elif float(value).is_integer():
        rendered = f"{int(value):,}"
    else:
        rendered = f"{value:,.2f}"
    return f"{label} for {name} is {rendered}."
