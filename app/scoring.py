"""Transparent, deterministic prototype scoring rules."""

from __future__ import annotations

from app.errors import MissingScoreInputs


HEALTH_FIELDS = (
    "government_dispensaries",
    "bhus",
    "rhcs",
    "thq_hospitals",
    "dhq_hospitals",
    "dhdc",
)

EDUCATION_FIELDS = ("literacy_total_pct", "literacy_male_pct", "literacy_female_pct")
ACCOUNTABILITY_FIELDS = ("overall_budget_lapse_pct", "development_budget_lapse_pct")


def _round(value: float) -> float:
    return round(value, 1)


def validate_score_inputs(district: dict) -> None:
    missing = []
    for section, fields in (
        ("education", EDUCATION_FIELDS),
        ("health", HEALTH_FIELDS),
        ("accountability", ACCOUNTABILITY_FIELDS),
    ):
        values = district.get(section, {})
        missing.extend(f"{section}.{field}" for field in fields if values.get(field) is None)
    if district.get("population_2023") in (None, 0):
        missing.append("population_2023")
    if missing:
        identity = district.get("slug") or district.get("name") or "unknown district"
        raise MissingScoreInputs(f"Cannot score {identity}; missing: {', '.join(missing)}")


def education_score(district: dict) -> float:
    """Average literacy, female literacy, and gender-parity components."""
    metrics = district["education"]
    gender_gap = abs(metrics["literacy_male_pct"] - metrics["literacy_female_pct"])
    return _round(
        (
            metrics["literacy_total_pct"]
            + metrics["literacy_female_pct"]
            + (100 - gender_gap)
        )
        / 3
    )


def facility_count(district: dict) -> int:
    return sum(district["health"][field] for field in HEALTH_FIELDS)


def facilities_per_100k(district: dict) -> float:
    return facility_count(district) / district["population_2023"] * 100_000


def accountability_score(district: dict) -> float:
    """Average overall and development budget utilization percentages."""
    metrics = district["accountability"]
    overall_utilization = 100 - metrics["overall_budget_lapse_pct"]
    development_utilization = 100 - metrics["development_budget_lapse_pct"]
    return _round((overall_utilization + development_utilization) / 2)


def score_districts(districts: list[dict]) -> list[dict]:
    """Return enriched districts; health is min-max relative to this cohort."""
    if not districts:
        return []
    for district in districts:
        validate_score_inputs(district)
    health_rates = [facilities_per_100k(district) for district in districts]
    low, high = min(health_rates), max(health_rates)
    spread = high - low

    enriched = []
    for district, rate in zip(districts, health_rates, strict=True):
        health_score = 50.0 if spread == 0 else (rate - low) / spread * 100
        scores = {
            "education": education_score(district),
            "health": _round(health_score),
            "accountability": accountability_score(district),
        }
        scores["overall"] = _round(sum(scores.values()) / len(scores))
        enriched.append(
            {
                **district,
                "derived": {
                    "facility_count": facility_count(district),
                    "facilities_per_100k": round(rate, 2),
                    "scores": scores,
                },
            }
        )
    return enriched


def rankings(districts: list[dict], category: str) -> list[dict]:
    allowed = {"overall", "education", "health", "accountability"}
    if category not in allowed:
        raise ValueError(f"Unknown category: {category}")
    ordered = sorted(
        districts,
        key=lambda district: (-district["derived"]["scores"][category], district["name"]),
    )
    return [
        {
            "rank": rank,
            "slug": district["slug"],
            "name": district["name"],
            "score": district["derived"]["scores"][category],
        }
        for rank, district in enumerate(ordered, start=1)
    ]
