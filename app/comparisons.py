"""Deterministic pairwise score, component, rank, and trend comparisons."""

from __future__ import annotations

import re
from typing import Any

from app.errors import InvalidComparison, TrendUnavailable
from app.llm import CITATION_MARKER
from app.schemas import (
    Citation,
    ComparisonComponent,
    ComparisonDistrict,
    ComparisonResult,
    ComparisonTrend,
    RankingCategory,
)


NUMBER = re.compile(r"(?<![A-Za-z0-9_])-?\d+(?:,\d{3})*(?:\.\d+)?")
INFERENCE_WORDS = {"could", "may", "might", "possible", "possibly", "suggests"}


def requested_comparison_category(question: str, explicit: str | None = None) -> RankingCategory:
    if explicit:
        return explicit  # type: ignore[return-value]
    lowered = question.casefold()
    if any(word in lowered for word in ("literacy", "education", "school")):
        return "education"
    if any(word in lowered for word in ("health", "facility", "facilities", "bhu", "rhc", "hospital")):
        return "health"
    if any(word in lowered for word in ("accountability", "audit", "budget", "utilization")):
        return "accountability"
    return "overall"


def _component_specs(record: dict[str, Any], category: RankingCategory) -> list[tuple[str, str, str, float]]:
    scores = record["derived"]["scores"]
    if category == "education":
        education = record["education"]
        return [
            ("literacy_total_pct", "Total literacy", "%", float(education["literacy_total_pct"])),
            ("literacy_female_pct", "Female literacy", "%", float(education["literacy_female_pct"])),
            (
                "gender_parity",
                "Gender parity component",
                "points",
                100 - abs(float(education["literacy_male_pct"]) - float(education["literacy_female_pct"])),
            ),
        ]
    if category == "health":
        return [
            ("facility_count", "Listed public facilities", "count", float(record["derived"]["facility_count"])),
            (
                "facilities_per_100k",
                "Facilities per 100,000 residents",
                "per 100,000",
                float(record["derived"]["facilities_per_100k"]),
            ),
        ]
    if category == "accountability":
        accountability = record["accountability"]
        return [
            (
                "overall_budget_utilization_pct",
                "Overall budget utilization",
                "%",
                100 - float(accountability["overall_budget_lapse_pct"]),
            ),
            (
                "development_budget_utilization_pct",
                "Development-budget utilization",
                "%",
                100 - float(accountability["development_budget_lapse_pct"]),
            ),
        ]
    return [
        ("education", "Education score", "points", float(scores["education"])),
        ("health", "Health score", "points", float(scores["health"])),
        ("accountability", "Accountability score", "points", float(scores["accountability"])),
    ]


def build_comparison(repository, district_slugs: list[str], category: RankingCategory) -> ComparisonResult:
    selected = list(dict.fromkeys(district_slugs))
    if len(selected) != 2:
        raise InvalidComparison("A structured comparison requires exactly two different districts.")

    records = [repository.get_district(slug) for slug in selected]
    if any(category not in record["score_details"] for record in records):
        raise InvalidComparison("Reviewed scores are unavailable for one or more selected districts; compare census facts instead.")
    districts = [
        ComparisonDistrict(
            slug=record["slug"],
            name=record["name"],
            score=float(record["derived"]["scores"][category]),
            rank=int(record["rankings"][category]["rank"]),
            score_detail=record["score_details"][category],
        )
        for record in records
    ]
    left_components = {item[0]: item for item in _component_specs(records[0], category)}
    right_components = {item[0]: item for item in _component_specs(records[1], category)}
    components = []
    for key, (_key, label, unit, left_value) in left_components.items():
        right_value = right_components[key][3]
        components.append(
            ComparisonComponent(
                key=key,
                label=label,
                unit=unit,
                values={selected[0]: round(left_value, 2), selected[1]: round(right_value, 2)},
                delta=round(right_value - left_value, 2),
            )
        )

    score_evidence = repository.score_search(
        f"compare {category} score components", selected, category, 2
    )
    citations = [
        item.citation.model_copy(update={"passage": item.text}) for item in score_evidence
    ]
    trends = []
    limitations = [
        "The comparison describes available district indicators and does not establish causation by any person."
    ]
    for district in districts:
        limitations.extend(district.score_detail.warnings)
    if category == "accountability":
        for slug in selected:
            try:
                trend = ComparisonTrend.model_validate(repository.development_trend(slug))
                trends.append(trend)
                citations.append(trend.citation)
            except TrendUnavailable as error:
                limitations.append(str(error))
        limitations.append(
            "Yearly change covers development-budget utilization only, not the overall accountability score."
        )
    else:
        limitations.append(
            "Comparable yearly changes are currently available only for development-budget utilization."
        )

    unique_citations: dict[str, Citation] = {}
    for citation in citations:
        existing = unique_citations.get(citation.evidence_id)
        if existing is None or (existing.passage is None and citation.passage is not None):
            unique_citations[citation.evidence_id] = citation
    return ComparisonResult(
        category=category,
        districts=districts,
        score_delta=round(districts[1].score - districts[0].score, 1),
        rank_delta=districts[1].rank - districts[0].rank,
        components=components,
        trends=trends,
        citations=list(unique_citations.values()),
        limitations=list(dict.fromkeys(limitations)),
    )


def format_comparison_summary(comparison: ComparisonResult) -> str:
    left, right = comparison.districts
    gap = abs(comparison.score_delta)
    if comparison.score_delta > 0:
        score_statement = f"{right.name} leads {left.name} by {gap:.1f} points"
    elif comparison.score_delta < 0:
        score_statement = f"{left.name} leads {right.name} by {gap:.1f} points"
    else:
        score_statement = f"{left.name} and {right.name} are tied"
    score_markers = " ".join(f"[{item.evidence_id}]" for item in comparison.citations[:2])
    answer = (
        f"For {comparison.category}, {left.name} scores {left.score:.1f} at rank {left.rank}, while "
        f"{right.name} scores {right.score:.1f} at rank {right.rank}; {score_statement}. {score_markers}"
    ).strip()
    answer += (
        f" Both results use {left.score_detail.version}; {left.name} covers "
        f"{left.score_detail.coverage:.0%} of expected components and {right.name} covers "
        f"{right.score_detail.coverage:.0%}."
    )
    if comparison.trends:
        trend_parts = []
        for trend in comparison.trends:
            trend_parts.append(
                f"{trend.district_name}'s development-budget utilization {trend.direction} by "
                f"{abs(trend.change_percentage_points):.2f} percentage points "
                f"[{trend.citation.evidence_id}]."
            )
        answer = f"{answer} {' '.join(trend_parts)}"
    return answer


def comparison_numbers_are_grounded(answer: str, comparison: ComparisonResult) -> bool:
    """Reject numeric comparison claims that are absent from the deterministic payload."""
    clean = CITATION_MARKER.sub("", answer)
    claimed = [float(item.replace(",", "")) for item in NUMBER.findall(clean)]
    if not claimed:
        return True
    payload = comparison.model_dump(mode="json")
    allowed: list[float] = [2.0]

    def collect(value: Any) -> None:
        if isinstance(value, bool) or value is None:
            return
        if isinstance(value, (int, float)):
            allowed.append(float(value))
            return
        if isinstance(value, str):
            allowed.extend(float(item.replace(",", "")) for item in NUMBER.findall(value))
            return
        if isinstance(value, dict):
            for item in value.values():
                collect(item)
            return
        if isinstance(value, list):
            for item in value:
                collect(item)

    collect(payload)
    if not all(any(abs(number - candidate) < 0.011 for candidate in allowed) for number in claimed):
        return False

    def associated_value(name: str, label: str) -> float | None:
        pattern = re.compile(
            rf"{re.escape(name)}[^.!?]{{0,80}}?{re.escape(label)}[^0-9-]{{0,16}}({NUMBER.pattern})",
            re.IGNORECASE,
        )
        match = pattern.search(clean)
        return float(match.group(1).replace(",", "")) if match else None

    for district in comparison.districts:
        score = associated_value(district.name, "score")
        if score is not None and abs(score - district.score) >= 0.011:
            return False
        rank = associated_value(district.name, "rank")
        if rank is not None and abs(rank - district.rank) >= 0.011:
            return False
        for component in comparison.components:
            value = associated_value(district.name, component.label)
            expected = component.values[district.slug]
            if value is not None and abs(value - expected) >= 0.011:
                return False
        trend = next((item for item in comparison.trends if item.district_slug == district.slug), None)
        if trend:
            for label in ("increased by", "decreased by", "change of", "changed by"):
                value = associated_value(district.name, label)
                if value is not None and abs(abs(value) - abs(trend.change_percentage_points)) >= 0.011:
                    return False
    return True


def comparison_language_is_safe(answer: str) -> bool:
    """Reject definitive causal/attribution language in comparison explanations."""
    lowered = answer.casefold()
    unsafe_phrases = (
        "caused the outcome",
        "caused this result",
        "politician caused",
        "representative caused",
        "proves corruption",
        "proof of corruption",
    )
    if any(phrase in lowered for phrase in unsafe_phrases):
        return False
    for sentence in re.split(r"(?<=[.!?])\s+", lowered):
        if any(term in sentence for term in ("contributing factor", "contributing factors")):
            words = set(re.findall(r"[a-z]+", sentence))
            if not words & INFERENCE_WORDS:
                return False
    return True
