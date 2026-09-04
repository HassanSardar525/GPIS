"""Repository contracts and the reviewed-JSON development adapter."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from app.cache import retrieval_corpus_version
from app.errors import DistrictNotFound, InvalidCategory, TrendUnavailable
from app.evidence_quality import EXPECTED_FACILITY_KINDS, health_capacity_change, load_health_capacity
from app.facts import format_fact, requested_metrics
from app.retrieval import EvidenceRetriever
from app.schemas import Citation, RetrievedEvidence
from app.scoring import rankings as calculate_rankings
from app.scoring import score_districts
from app.score_explanations import format_score_explanation, requested_score_category
from app.score_quality import PROTOTYPE_VERSION, load_qualification_registry
from app.temporal import development_budget_trend


RANKING_CATEGORIES = {"overall", "education", "health", "accountability"}


class GPISRepository(Protocol):
    name: str

    def healthcheck(self) -> bool: ...
    def cache_version(self) -> str: ...
    def metadata(self) -> dict: ...
    def list_districts(self) -> list[dict]: ...
    def get_district(self, slug: str) -> dict: ...
    def rankings(self, category: str) -> list[dict]: ...
    def fact_search(self, query: str, district_slugs: list[str], limit: int) -> list[RetrievedEvidence]: ...
    def keyword_search(
        self,
        query: str,
        district_slugs: list[str],
        category: str | None,
        period: str | None,
        limit: int,
    ) -> list[RetrievedEvidence]: ...
    def vector_search(
        self,
        embedding: list[float],
        district_slugs: list[str],
        category: str | None,
        period: str | None,
        limit: int,
    ) -> list[RetrievedEvidence]: ...
    def development_trend(self, slug: str) -> dict: ...
    def health_capacity_trend(self, slug: str, facility: str) -> dict: ...
    def trend_search(self, query: str, district_slugs: list[str], limit: int) -> list[RetrievedEvidence]: ...
    def score_search(
        self, query: str, district_slugs: list[str], category: str | None, limit: int
    ) -> list[RetrievedEvidence]: ...
    def record_trace(self, trace: dict) -> None: ...


class JsonRepository:
    """Read-only adapter used for tests and a no-database fallback."""

    name = "json"

    def __init__(self, path: Path, score_version: str = PROTOTYPE_VERSION):
        if score_version != PROTOTYPE_VERSION:
            raise ValueError(
                f"Score version '{score_version}' is not active; evidence-v2 remains staged"
            )
        self.path = path
        self.data = json.loads(path.read_text(encoding="utf-8"))
        self.score_version = score_version
        self._cache_version = retrieval_corpus_version(path, score_version)
        self.districts = score_districts(
            self.data["districts"], self.data["metadata"]["generated_on"]
        )
        self.by_slug = {district["slug"]: district for district in self.districts}
        self.retriever = EvidenceRetriever(
            self.districts, self.data["sources"], self.data.get("project_evidence", [])
        )
        health_path = path.with_name("health_capacity_periods.json")
        self.health_capacity = load_health_capacity(health_path) if health_path.is_file() else None
        qualification_path = path.with_name("evidence_qualification.json")
        self.qualification = load_qualification_registry(qualification_path)

    def cache_version(self) -> str:
        return self._cache_version

    def _methodology_citation(self, evidence_id: str, locator: str) -> dict:
        source = self.data["sources"]["gpis_methodology_v1"]
        return {
            "evidence_id": evidence_id,
            "source_id": "gpis_methodology_v1",
            "publisher": source["publisher"],
            "title": source["title"],
            "period": source["period"],
            "url": source["url"],
            "locator": locator,
        }

    def healthcheck(self) -> bool:
        return self.path.is_file()

    def metadata(self) -> dict:
        return {
            **self.data["metadata"],
            "active_score_version": self.score_version,
            "evidence_v2_gate": self.qualification,
        }

    def list_districts(self) -> list[dict]:
        return [
            {
                "slug": district["slug"],
                "name": district["name"],
                "scores": district["derived"]["scores"],
                "score_details": district["derived"]["score_details"],
            }
            for district in sorted(self.districts, key=lambda item: item["name"])
        ]

    def get_district(self, slug: str) -> dict:
        district = self.by_slug.get(slug)
        if not district:
            raise DistrictNotFound(f"District '{slug}' was not found")
        return {
            **district,
            "score_details": district["derived"]["score_details"],
            "rankings": {
                category: next(
                    item for item in self.rankings(category) if item["slug"] == district["slug"]
                )
                for category in RANKING_CATEGORIES
            },
            "sources": self.data["sources"],
            "metadata": self.metadata(),
        }

    def rankings(self, category: str) -> list[dict]:
        if category not in RANKING_CATEGORIES:
            raise InvalidCategory(f"Unknown ranking category: {category}")
        return calculate_rankings(self.districts, category)

    def development_trend(self, slug: str) -> dict:
        district = self.by_slug.get(slug)
        if not district:
            raise DistrictNotFound(f"District '{slug}' was not found")
        if "accountability_periods" not in district:
            raise TrendUnavailable(f"Comparable development-budget periods are unavailable for {district['name']}")
        trend = development_budget_trend(district["accountability_periods"])
        evidence = next(item for item in district["evidence"] if item["id"].endswith("-development-trend"))
        source = self.data["sources"][evidence["source_id"]]
        return {
            "district_slug": slug,
            "district_name": district["name"],
            **trend,
            "citation": {
                "evidence_id": evidence["id"],
                "source_id": evidence["source_id"],
                "publisher": source["publisher"],
                "title": source["title"],
                "period": source["period"],
                "url": source["url"],
                "locator": evidence["locator"],
                "passage": evidence["text"],
            },
        }

    def health_capacity_trend(self, slug: str, facility: str) -> dict:
        if facility not in EXPECTED_FACILITY_KINDS:
            raise InvalidCategory(f"Unknown health facility category: {facility}")
        if not self.health_capacity:
            raise TrendUnavailable("Reviewed health-capacity periods are unavailable")
        try:
            change = health_capacity_change(self.health_capacity, slug, facility)
        except KeyError as error:
            raise DistrictNotFound(f"District '{slug}' was not found") from error
        periods = []
        for key in ("previous", "current"):
            item = change[key]
            source = self.health_capacity.sources[item["source_id"]]
            periods.append(
                {
                    "snapshot_date": item["snapshot_date"],
                    "count": item["count"],
                    "beds": item["beds"],
                    "citation": {
                        "evidence_id": f"{slug}-health-capacity-{item['snapshot_date']}",
                        "source_id": item["source_id"],
                        "publisher": source.publisher,
                        "title": source.title,
                        "period": source.period_label,
                        "url": source.official_url,
                        "locator": item["locator"],
                    },
                }
            )
        return {
            "district_slug": change["district_slug"],
            "district_name": change["district_name"],
            "facility": facility,
            "comparability_group": change["comparability_group"],
            "periods": periods,
            "count_change": change["count_change"],
            "bed_change": change["bed_change"],
            "warnings": change["warnings"],
            "limitations": self.health_capacity.comparability.limitations,
        }

    def trend_search(self, query: str, district_slugs: list[str], limit: int) -> list[RetrievedEvidence]:
        selected = district_slugs or list(self.by_slug)
        trends = [self.development_trend(slug) for slug in selected]
        reverse = not any(word in query.casefold() for word in ("decline", "decrease", "least", "worst"))
        trends.sort(key=lambda item: item["change_percentage_points"], reverse=reverse)
        results = []
        for rank, trend in enumerate(trends[:limit], start=1):
            previous, current = trend["periods"]
            citation = Citation(**trend["citation"])
            results.append(
                RetrievedEvidence(
                    id=citation.evidence_id,
                    district_slug=trend["district_slug"],
                    district_name=trend["district_name"],
                    category="accountability",
                    text=(
                        f"{trend['district_name']} development-budget utilization was {previous['utilization_pct']:.2f}% "
                        f"in {previous['period']} and {current['utilization_pct']:.2f}% in {current['period']}; "
                        f"it {trend['direction']} by {abs(trend['change_percentage_points']):.2f} percentage points."
                    ),
                    source_id=citation.source_id,
                    locator=citation.locator,
                    period=citation.period,
                    keyword_rank=rank,
                    citation=citation,
                )
            )
        return results

    def score_search(
        self, query: str, district_slugs: list[str], category: str | None, limit: int
    ) -> list[RetrievedEvidence]:
        selected = district_slugs or list(self.by_slug)
        score_category = requested_score_category(query, category)
        if not district_slugs and any(
            word in query.casefold() for word in ("best", "highest", "lowest", "rank", "worst")
        ):
            reverse = not any(word in query.casefold() for word in ("lowest", "worst"))
            selected.sort(
                key=lambda slug: self.by_slug[slug]["derived"]["scores"][score_category],
                reverse=reverse,
            )
        rates = [district["derived"]["facilities_per_100k"] for district in self.districts]
        results = []
        for slug in selected[:limit]:
            district = self.by_slug.get(slug)
            if not district:
                continue
            scores = district["derived"]["scores"]
            education = district["education"]
            accountability = district["accountability"]
            components = {
                "education": {
                    "literacy_total_pct": education["literacy_total_pct"],
                    "literacy_female_pct": education["literacy_female_pct"],
                    "gender_parity": 100 - abs(education["literacy_male_pct"] - education["literacy_female_pct"]),
                },
                "health": {
                    "facility_count": district["derived"]["facility_count"],
                    "facilities_per_100k": district["derived"]["facilities_per_100k"],
                    "cohort_min": min(rates),
                    "cohort_max": max(rates),
                },
                "accountability": {
                    "overall_budget_utilization_pct": 100 - accountability["overall_budget_lapse_pct"],
                    "development_budget_utilization_pct": 100 - accountability["development_budget_lapse_pct"],
                },
                "overall": {name: scores[name] for name in ("education", "health", "accountability")},
            }[score_category]
            detail = district["derived"]["score_details"][score_category]
            evidence_id = f"score-{slug}-{score_category}-prototype-v1"
            citation = self._methodology_citation(evidence_id, f"{score_category.title()} formula and stored components")
            results.append(
                RetrievedEvidence(
                    id=evidence_id,
                    district_slug=slug,
                    district_name=district["name"],
                    category=score_category,
                    text=format_score_explanation(
                        district["name"], score_category, scores[score_category], components, detail
                    ),
                    source_id=citation["source_id"],
                    locator=citation["locator"],
                    period=citation["period"],
                    keyword_rank=len(results) + 1,
                    citation=citation,
                )
            )
        return results

    def fact_search(self, query: str, district_slugs: list[str], limit: int) -> list[RetrievedEvidence]:
        metrics = requested_metrics(query)
        if not metrics:
            return []
        selected = district_slugs or list(self.by_slug)
        results = []
        for slug in selected:
            district = self.by_slug.get(slug)
            if not district:
                continue
            evidence_by_category = {}
            for item in district["evidence"]:
                evidence_by_category.setdefault(item["category"], item)
            for metric in metrics:
                if metric == "population_2023":
                    value, category, source_id, locator, unit = district[metric], "context", "pbs_table_1", f"{district['name']} District row", "count"
                else:
                    category = next((name for name in ("education", "health", "accountability") if metric in district[name]), None)
                    if not category:
                        continue
                    value = district[category][metric]
                    source_id = evidence_by_category[category]["source_id"]
                    locator = evidence_by_category[category]["locator"]
                    unit = "percent" if metric.endswith("_pct") else "count"
                source = self.data["sources"][source_id]
                evidence_id = f"fact-{slug}-{metric}"
                results.append(
                    RetrievedEvidence(
                        id=evidence_id,
                        district_slug=slug,
                        district_name=district["name"],
                        category=category,
                        text=format_fact(district["name"], metric, float(value), unit),
                        source_id=source_id,
                        locator=locator,
                        period=source["period"],
                        keyword_rank=len(results) + 1,
                        citation={
                            "evidence_id": evidence_id,
                            "source_id": source_id,
                            "publisher": source["publisher"],
                            "title": source["title"],
                            "period": source["period"],
                            "url": source["url"],
                            "locator": locator,
                        },
                    )
                )
        return results[:limit]

    def keyword_search(
        self,
        query: str,
        district_slugs: list[str],
        category: str | None,
        period: str | None,
        limit: int,
    ) -> list[RetrievedEvidence]:
        results = self.retriever.search(
            query,
            district_slugs=district_slugs,
            category=category,
            period=period,
            limit=limit,
        )
        return [RetrievedEvidence.model_validate(result) for result in results]

    def vector_search(
        self,
        embedding: list[float],
        district_slugs: list[str],
        category: str | None,
        period: str | None,
        limit: int,
    ) -> list[RetrievedEvidence]:
        return []

    def record_trace(self, trace: dict) -> None:
        return None
