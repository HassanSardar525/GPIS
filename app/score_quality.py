"""Shared score-quality rules and the staged evidence-v2 activation gate."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping


PROTOTYPE_VERSION = "prototype-v1"
CANDIDATE_VERSION = "evidence-v2"
MINIMUM_COVERAGE = 0.75

CONFIDENCE_WEIGHTS = {
    "source_authority": 0.30,
    "recency": 0.25,
    "directness": 0.25,
    "cross_district_comparability": 0.20,
}

PROTOTYPE_PERIODS = {
    "education": "Census 2023",
    "health": "Census 2023 population and Audit Year 2024-25 facility listing",
    "accountability": "FY 2023-24",
    "overall": "Mixed: Census 2023, FY 2023-24, and Audit Year 2024-25",
}

PROTOTYPE_FACTORS = {
    "education": {
        "source_authority": 1.0,
        "recency": 1.0,
        "directness": 1.0,
        "cross_district_comparability": 1.0,
    },
    "health": {
        "source_authority": 1.0,
        "recency": 0.75,
        "directness": 0.5,
        "cross_district_comparability": 1.0,
    },
    "accountability": {
        "source_authority": 1.0,
        "recency": 0.75,
        "directness": 0.5,
        "cross_district_comparability": 1.0,
    },
}

PROTOTYPE_WARNINGS = {
    "education": [],
    "health": [
        "prototype-v1 health is a relative facility-count capacity proxy, not an activity, quality, or outcome score"
    ],
    "accountability": [
        "prototype-v1 accountability measures budget utilization, not audit risk, integrity, or impact"
    ],
    "overall": [
        "prototype-v1 combines indicators with different reporting periods and provisional proxies"
    ],
}

PROTOTYPE_COMPONENT_WEIGHTS = {
    "education": {
        "literacy_total_pct": 1 / 3,
        "literacy_female_pct": 1 / 3,
        "gender_parity": 1 / 3,
    },
    "health": {"facilities_per_100k": 1.0},
    "accountability": {
        "overall_budget_utilization_pct": 0.5,
        "development_budget_utilization_pct": 0.5,
    },
    "overall": {"education": 1 / 3, "health": 1 / 3, "accountability": 1 / 3},
}

EVIDENCE_V2_FORMULAS = {
    "education": {
        "status": "staged",
        "direction": "higher_is_better",
        "components": PROTOTYPE_COMPONENT_WEIGHTS["education"],
        "normalization": "bounded percentages within the fixed ten-district cohort",
        "minimum_coverage": MINIMUM_COVERAGE,
        "trend_component": "blocked until a definitionally comparable second period is qualified",
    },
    "health": {
        "status": "staged",
        "direction": "higher_is_better",
        "components": {"capacity": 0.5, "activity": 0.25, "outcomes": 0.25},
        "normalization": "min-max within the fixed ten-district cohort after denominator validation",
        "minimum_coverage": MINIMUM_COVERAGE,
    },
    "accountability": {
        "status": "staged",
        "direction": "higher_is_better",
        "components": PROTOTYPE_COMPONENT_WEIGHTS["accountability"],
        "normalization": "bounded utilization percentages",
        "minimum_coverage": MINIMUM_COVERAGE,
        "audit_component": "blocked until finding scope has an exact expenditure denominator",
    },
    "overall": {
        "status": "staged",
        "direction": "higher_is_better",
        "components": PROTOTYPE_COMPONENT_WEIGHTS["overall"],
        "normalization": "weighted sum of category scores",
        "minimum_coverage": MINIMUM_COVERAGE,
    },
}


def weighted_coverage(values: Mapping[str, float | None], weights: Mapping[str, float]) -> float:
    """Return eligible present weight / expected weight without zero-filling."""
    expected = sum(weights.values())
    if expected <= 0:
        raise ValueError("Expected component weight must be positive")
    unknown = set(values) - set(weights)
    if unknown:
        raise ValueError(f"Unknown score components: {', '.join(sorted(unknown))}")
    available = sum(weight for key, weight in weights.items() if values.get(key) is not None)
    return round(available / expected, 4)


def evidence_confidence(factors: Mapping[str, float]) -> float:
    """Calculate deterministic evidence confidence from the four reviewed properties."""
    if set(factors) != set(CONFIDENCE_WEIGHTS):
        raise ValueError("Confidence factors must include exactly the four documented properties")
    accepted = {0.5, 0.75, 1.0}
    invalid = {name: value for name, value in factors.items() if value not in accepted}
    if invalid:
        raise ValueError(f"Confidence ratings must be 0.5, 0.75, or 1.0: {invalid}")
    return round(sum(factors[name] * weight for name, weight in CONFIDENCE_WEIGHTS.items()), 4)


def aggregate_confidence(
    component_confidence: Mapping[str, float | None], weights: Mapping[str, float]
) -> float | None:
    """Aggregate confidence over present components; coverage separately reports absence."""
    present = {key: value for key, value in component_confidence.items() if value is not None}
    if not present:
        return None
    denominator = sum(weights[key] for key in present)
    return round(sum(present[key] * weights[key] for key in present) / denominator, 4)


def prototype_score_details(
    scores: Mapping[str, float], components: Mapping[str, Mapping[str, float]], calculated_at: str
) -> dict[str, dict]:
    """Build canonical public metadata for reproducible prototype-v1 scores."""
    confidence = {
        category: evidence_confidence(factors)
        for category, factors in PROTOTYPE_FACTORS.items()
    }
    overall_factors = {
        name: round(sum(PROTOTYPE_FACTORS[category][name] for category in PROTOTYPE_FACTORS) / 3, 4)
        for name in CONFIDENCE_WEIGHTS
    }
    confidence["overall"] = round(
        sum(overall_factors[name] * weight for name, weight in CONFIDENCE_WEIGHTS.items()), 4
    )
    factors = {**PROTOTYPE_FACTORS, "overall": overall_factors}
    details = {}
    for category, weights in PROTOTYPE_COMPONENT_WEIGHTS.items():
        eligible = {key: components[category].get(key) for key in weights}
        coverage = weighted_coverage(eligible, weights)
        missing = [key for key, value in eligible.items() if value is None]
        warnings = list(PROTOTYPE_WARNINGS[category])
        if coverage < 1:
            warnings.append("Score coverage is incomplete; missing inputs were not converted to zero")
        if confidence[category] < 0.75:
            warnings.append("Evidence confidence is below the 0.75 review threshold")
        details[category] = {
            "category": category,
            "score": float(scores[category]),
            "version": PROTOTYPE_VERSION,
            "components": dict(components[category]),
            "coverage": coverage,
            "reporting_period": PROTOTYPE_PERIODS[category],
            "confidence": confidence[category],
            "confidence_factors": factors[category],
            "missing_components": missing,
            "warnings": warnings,
            "calculated_at": calculated_at,
        }
    return details


def staged_health_result(values: Mapping[str, float | None]) -> dict:
    """Calculate staged v2 health coverage without fabricating missing observations."""
    weights = EVIDENCE_V2_FORMULAS["health"]["components"]
    coverage = weighted_coverage(values, weights)
    missing = [key for key in weights if values.get(key) is None]
    score = round(sum(values[key] * weight for key, weight in weights.items() if values.get(key) is not None), 1)
    warnings = []
    if missing:
        warnings.append("Partial evidence-v2 score; missing component weights are not redistributed")
    return {
        "score": score if coverage >= MINIMUM_COVERAGE else None,
        "coverage": coverage,
        "missing_components": missing,
        "ranked": coverage >= MINIMUM_COVERAGE,
        "warnings": warnings,
    }


def staged_rankings(results: list[dict]) -> list[dict]:
    """Rank sufficiently covered candidate results and append explicit unranked rows."""
    ranked = sorted(
        (item for item in results if item.get("ranked") and item.get("score") is not None),
        key=lambda item: (-item["score"], item["name"]),
    )
    unranked = sorted(
        (item for item in results if not item.get("ranked") or item.get("score") is None),
        key=lambda item: item["name"],
    )
    return [
        {**item, "rank": index}
        for index, item in enumerate(ranked, start=1)
    ] + [{**item, "rank": None} for item in unranked]


def load_qualification_registry(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    decisions = payload.get("decisions", [])
    ids = [item.get("id") for item in decisions]
    if len(ids) != len(set(ids)):
        raise ValueError("Evidence qualification decision ids must be unique")
    allowed = {"qualified", "qualified_with_limitations", "not_qualified"}
    if any(item.get("status") not in allowed for item in decisions):
        raise ValueError("Unknown evidence qualification status")
    payload["activation_ready"] = all(
        item["status"] in {"qualified", "qualified_with_limitations"}
        for item in decisions
        if item.get("required_for_activation")
    )
    return payload


def deterministic_calculated_at(generated_on: str) -> str:
    return datetime.fromisoformat(generated_on).replace(tzinfo=timezone.utc).isoformat()
