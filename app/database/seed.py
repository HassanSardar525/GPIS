"""Idempotently load the reviewed JSON contract and calculated scores."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import joinedload

from app.database.models import DatasetMetadata, District, EvidenceChunk, Observation, ScoreDefinition, ScoreResult, Source
from app.database.session import session_factory
from app.embeddings import Embedder
from app.scoring import HEALTH_FIELDS, score_districts


FORMULAS = {
    "education": {
        "components": ["literacy_total_pct", "literacy_female_pct", "100 - literacy_gender_gap"],
        "aggregation": "arithmetic_mean",
    },
    "health": {
        "components": ["listed_public_facilities_per_100k"],
        "normalization": "min_max_within_fixed_ten_district_cohort",
    },
    "accountability": {
        "components": ["overall_budget_utilization_pct", "development_budget_utilization_pct"],
        "aggregation": "arithmetic_mean",
    },
    "overall": {
        "components": ["education", "health", "accountability"],
        "aggregation": "equal_weight_arithmetic_mean",
    },
}


def _upsert(session, model, values: dict, keys: list[str]) -> None:
    statement = insert(model).values(**values)
    updates = {key: getattr(statement.excluded, key) for key in values if key not in keys}
    session.execute(statement.on_conflict_do_update(index_elements=keys, set_=updates))


def _unit(metric: str) -> str:
    if metric.endswith("_pct"):
        return "percent"
    if metric.endswith("_million_pkr"):
        return "million_pkr"
    return "count"


def seed_database(database_url: str, data_path: Path, score_version: str) -> dict[str, int]:
    data = json.loads(data_path.read_text(encoding="utf-8"))
    scored = score_districts(data["districts"])
    sessions = session_factory(database_url)
    with sessions.begin() as session:
        for source_id, source in data["sources"].items():
            _upsert(session, Source, {"id": source_id, **source, "sha256": source.get("sha256")}, ["id"])
        for key, value in data["metadata"].items():
            _upsert(session, DatasetMetadata, {"key": key, "value": value}, ["key"])

        for district in scored:
            _upsert(
                session,
                District,
                {"slug": district["slug"], "name": district["name"], "population_2023": district["population_2023"]},
                ["slug"],
            )
        district_ids = dict(session.execute(select(District.slug, District.id)).all())

        for district in scored:
            district_id = district_ids[district["slug"]]
            evidence_by_category = {}
            for item in district["evidence"]:
                evidence_by_category.setdefault(item["category"], item)
            population_evidence = {"source_id": "pbs_table_1", "locator": f"{district['name']} District row"}
            observations = [("context", "population_2023", district["population_2023"], population_evidence)]
            for category in ("education", "health", "accountability"):
                evidence = evidence_by_category[category]
                observations.extend((category, metric, value, evidence) for metric, value in district[category].items())
            for category, metric, value, evidence in observations:
                source_id = evidence["source_id"]
                period = data["sources"][source_id]["period"]
                _upsert(
                    session,
                    Observation,
                    {
                        "district_id": district_id,
                        "metric_key": metric,
                        "category": category,
                        "value": value,
                        "unit": _unit(metric),
                        "period": period,
                        "source_id": source_id,
                        "locator": evidence["locator"],
                    },
                    ["district_id", "metric_key", "period"],
                )
            temporal_evidence = next(
                item for item in district["evidence"] if item["id"].endswith("-development-trend")
            )
            for period, period_values in district["accountability_periods"].items():
                for metric, value in period_values.items():
                    _upsert(
                        session,
                        Observation,
                        {
                            "district_id": district_id,
                            "metric_key": metric,
                            "category": "accountability",
                            "value": value,
                            "unit": _unit(metric),
                            "period": period,
                            "source_id": temporal_evidence["source_id"],
                            "locator": temporal_evidence["locator"],
                        },
                        ["district_id", "metric_key", "period"],
                    )
            for evidence in district["evidence"]:
                source = data["sources"][evidence["source_id"]]
                _upsert(
                    session,
                    EvidenceChunk,
                    {
                        "id": evidence["id"],
                        "district_id": district_id,
                        "source_id": evidence["source_id"],
                        "category": evidence["category"],
                        "period": source["period"],
                        "text": evidence["text"],
                        "locator": evidence["locator"],
                    },
                    ["id"],
                )

        for evidence in data.get("project_evidence", []):
            source = data["sources"][evidence["source_id"]]
            _upsert(
                session,
                EvidenceChunk,
                {
                    "id": evidence["id"],
                    "district_id": None,
                    "source_id": evidence["source_id"],
                    "category": evidence["category"],
                    "period": source["period"],
                    "text": evidence["text"],
                    "locator": evidence["locator"],
                },
                ["id"],
            )

        for category, formula in FORMULAS.items():
            _upsert(
                session,
                ScoreDefinition,
                {"version": score_version, "category": category, "formula": formula, "active": True},
                ["version", "category"],
            )

        now = datetime.now(timezone.utc)
        rates = {district["slug"]: district["derived"]["facilities_per_100k"] for district in scored}
        for district in scored:
            metrics = district["education"]
            gender_parity = 100 - abs(metrics["literacy_male_pct"] - metrics["literacy_female_pct"])
            accountability = district["accountability"]
            components = {
                "education": {
                    "literacy_total_pct": metrics["literacy_total_pct"],
                    "literacy_female_pct": metrics["literacy_female_pct"],
                    "gender_parity": gender_parity,
                },
                "health": {
                    "facility_count": sum(district["health"][field] for field in HEALTH_FIELDS),
                    "facilities_per_100k": rates[district["slug"]],
                    "cohort_min": min(rates.values()),
                    "cohort_max": max(rates.values()),
                },
                "accountability": {
                    "overall_budget_utilization_pct": 100 - accountability["overall_budget_lapse_pct"],
                    "development_budget_utilization_pct": 100 - accountability["development_budget_lapse_pct"],
                },
                "overall": {
                    key: district["derived"]["scores"][key]
                    for key in ("education", "health", "accountability")
                },
            }
            for category, score in district["derived"]["scores"].items():
                _upsert(
                    session,
                    ScoreResult,
                    {
                        "district_id": district_ids[district["slug"]],
                        "version": score_version,
                        "category": category,
                        "score": score,
                        "components": components[category],
                        "coverage": 1,
                        "calculated_at": now,
                    },
                    ["district_id", "version", "category"],
                )

        return {
            "districts": session.scalar(select(func.count()).select_from(District)),
            "observations": session.scalar(select(func.count()).select_from(Observation)),
            "evidence_chunks": session.scalar(select(func.count()).select_from(EvidenceChunk)),
            "score_results": session.scalar(select(func.count()).select_from(ScoreResult)),
        }


def embed_missing(database_url: str, embedder: Embedder) -> int:
    sessions = session_factory(database_url)
    with sessions.begin() as session:
        chunks = session.scalars(
            select(EvidenceChunk)
            .options(joinedload(EvidenceChunk.source))
            .where(EvidenceChunk.embedding.is_(None))
            .order_by(EvidenceChunk.id)
        ).all()
        if not chunks:
            return 0
        vectors = embedder.embed(
            [f"{chunk.category}. {chunk.source.title}. {chunk.text}" for chunk in chunks]
        )
        for chunk, vector in zip(chunks, vectors, strict=True):
            chunk.embedding = vector
        return len(chunks)
