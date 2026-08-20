"""Deterministic score-category selection and human-readable component explanations."""

from __future__ import annotations


CATEGORIES = ("education", "health", "accountability", "overall")


def requested_score_category(question: str, explicit: str | None = None) -> str:
    if explicit:
        return explicit
    lowered = question.casefold()
    return next((category for category in CATEGORIES if category in lowered), "overall")


def format_score_explanation(
    district_name: str, category: str, score: float, components: dict[str, float]
) -> str:
    if category == "education":
        return (
            f"{district_name}'s education score is {score:.1f}. Its deterministic components are "
            f"total literacy {components['literacy_total_pct']:.2f}%, female literacy "
            f"{components['literacy_female_pct']:.2f}%, and gender parity {components['gender_parity']:.2f}; "
            "the score is their arithmetic mean."
        )
    if category == "health":
        return (
            f"{district_name}'s health score is {score:.1f}. It has {int(components['facility_count'])} listed "
            f"public facilities, or {components['facilities_per_100k']:.2f} per 100,000 residents. That rate is "
            f"min-max normalized against the ten-district range {components['cohort_min']:.2f} to "
            f"{components['cohort_max']:.2f} facilities per 100,000."
        )
    if category == "accountability":
        return (
            f"{district_name}'s accountability score is {score:.1f}. Overall budget utilization is "
            f"{components['overall_budget_utilization_pct']:.2f}% and development-budget utilization is "
            f"{components['development_budget_utilization_pct']:.2f}%; the score is their arithmetic mean."
        )
    return (
        f"{district_name}'s overall score is {score:.1f}. It is the equal-weight mean of education "
        f"{components['education']:.1f}, health {components['health']:.1f}, and accountability "
        f"{components['accountability']:.1f}."
    )
