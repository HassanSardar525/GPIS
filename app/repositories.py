"""Repository contracts and the reviewed-JSON development adapter."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from app.errors import DistrictNotFound, InvalidCategory
from app.facts import format_fact, requested_metrics
from app.retrieval import EvidenceRetriever
from app.schemas import RetrievedEvidence
from app.scoring import rankings as calculate_rankings
from app.scoring import score_districts


RANKING_CATEGORIES = {"overall", "education", "health", "accountability"}


class GPISRepository(Protocol):
    name: str

    def healthcheck(self) -> bool: ...
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
    def record_trace(self, trace: dict) -> None: ...


class JsonRepository:
    """Read-only adapter used for tests and a no-database fallback."""

    name = "json"

    def __init__(self, path: Path):
        self.path = path
        self.data = json.loads(path.read_text(encoding="utf-8"))
        self.districts = score_districts(self.data["districts"])
        self.by_slug = {district["slug"]: district for district in self.districts}
        self.retriever = EvidenceRetriever(self.districts, self.data["sources"])

    def healthcheck(self) -> bool:
        return self.path.is_file()

    def metadata(self) -> dict:
        return self.data["metadata"]

    def list_districts(self) -> list[dict]:
        return [
            {
                "slug": district["slug"],
                "name": district["name"],
                "scores": district["derived"]["scores"],
            }
            for district in self.districts
        ]

    def get_district(self, slug: str) -> dict:
        district = self.by_slug.get(slug)
        if not district:
            raise DistrictNotFound(f"District '{slug}' was not found")
        return {
            **district,
            "rankings": {
                category: next(
                    item for item in self.rankings(category) if item["slug"] == district["slug"]
                )
                for category in RANKING_CATEGORIES
            },
            "sources": self.data["sources"],
            "metadata": self.data["metadata"],
        }

    def rankings(self, category: str) -> list[dict]:
        if category not in RANKING_CATEGORIES:
            raise InvalidCategory(f"Unknown ranking category: {category}")
        return calculate_rankings(self.districts, category)

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
