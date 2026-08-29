"""Idempotently load the reviewed JSON contract and calculated scores."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import joinedload

from app.database.models import DatasetMetadata, District, EvidenceChunk, Observation, ScoreDefinition, ScoreResult, Source
from app.database.session import session_factory
from app.embeddings import Embedder
from app.evidence_quality import format_health_capacity_period, health_capacity_rates, load_health_capacity
from app.score_quality import EVIDENCE_V2_FORMULAS, load_qualification_registry
from app.scoring import score_districts


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
    health_path = data_path.with_name("health_capacity_periods.json")
    health_capacity = load_health_capacity(health_path) if health_path.is_file() else None
    qualification = load_qualification_registry(data_path.with_name("evidence_qualification.json"))
    scored = score_districts(data["districts"], data["metadata"]["generated_on"])
    sessions = session_factory(database_url)
    with sessions.begin() as session:
        for source_id, source in data["sources"].items():
            _upsert(session, Source, {"id": source_id, **source, "sha256": source.get("sha256")}, ["id"])
        if health_capacity:
            for source_id, source in health_capacity.sources.items():
                _upsert(
                    session,
                    Source,
                    {
                        "id": source_id,
                        "publisher": source.publisher,
                        "title": source.title,
                        "period": source.period_label,
                        "url": source.official_url,
                        "local_file": source.local_file,
                        "sha256": source.sha256,
                    },
                    ["id"],
                )
        for key, value in data["metadata"].items():
            _upsert(session, DatasetMetadata, {"key": key, "value": value}, ["key"])
        _upsert(
            session,
            DatasetMetadata,
            {"key": "active_score_version", "value": score_version},
            ["key"],
        )
        _upsert(
            session,
            DatasetMetadata,
            {"key": "evidence_v2_gate", "value": qualification},
            ["key"],
        )

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
                        "definition_version": "prototype-v1",
                        "geography_level": "district",
                        "population_basis": (
                            "Census 2023 district population"
                            if category in {"context", "health"}
                            else None
                        ),
                        "comparability_group": None,
                        "quality_flags": [],
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
                            "definition_version": "agp-development-utilization-v1",
                            "geography_level": "district",
                            "population_basis": None,
                            "comparability_group": "agp-development-utilization-fy-v1",
                            "quality_flags": [],
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

        if health_capacity:
            session.execute(
                delete(Observation).where(
                    Observation.comparability_group == health_capacity.comparability.group
                )
            )
            _upsert(
                session,
                DatasetMetadata,
                {"key": "health_capacity_contract_version", "value": health_capacity.version},
                ["key"],
            )
            _upsert(
                session,
                DatasetMetadata,
                {
                    "key": "health_capacity_comparability",
                    "value": health_capacity.comparability.model_dump(mode="json"),
                },
                ["key"],
            )
            for district in health_capacity.districts:
                district_id = district_ids.get(district.slug)
                if district_id is None:
                    raise ValueError(f"Health capacity references unknown district: {district.slug}")
                for period in district.periods:
                    flags_by_metric = {
                        anomaly.metric: anomaly.note
                        for anomaly in health_capacity.anomalies
                        if anomaly.district_slug == district.slug
                        and anomaly.snapshot_date == period.snapshot_date
                    }
                    for facility, observation in period.facilities.items():
                        for measure in ("count", "beds"):
                            value = getattr(observation, measure)
                            if value is None:
                                continue
                            metric = f"phs_{facility}_{measure}"
                            quality_flags = [
                                note
                                for anomaly_metric, note in flags_by_metric.items()
                                if anomaly_metric == f"{facility}.{measure}"
                            ]
                            _upsert(
                                session,
                                Observation,
                                {
                                    "district_id": district_id,
                                    "metric_key": metric,
                                    "category": "health",
                                    "value": value,
                                    "unit": "count",
                                    "period": period.snapshot_date.isoformat(),
                                    "source_id": period.source_id,
                                    "locator": period.locator,
                                    "definition_version": health_capacity.version,
                                    "geography_level": health_capacity.comparability.geography_level,
                                    "population_basis": None,
                                    "comparability_group": health_capacity.comparability.group,
                                    "quality_flags": quality_flags,
                                },
                                ["district_id", "metric_key", "period"],
                            )
                    _upsert(
                        session,
                        EvidenceChunk,
                        {
                            "id": f"{district.slug}-health-capacity-{period.snapshot_date.isoformat()}",
                            "district_id": district_id,
                            "source_id": period.source_id,
                            "category": "health",
                            "period": period.snapshot_date.isoformat(),
                            "text": format_health_capacity_period(district.name, period),
                            "locator": period.locator,
                        },
                        ["id"],
                    )

            populations = {district["slug"]: district["population_2023"] for district in scored}
            for rate in health_capacity_rates(health_capacity, populations):
                if rate["value_per_100k"] is None:
                    continue
                _upsert(
                    session,
                    Observation,
                    {
                        "district_id": district_ids[rate["district_slug"]],
                        "metric_key": f"phs_{rate['facility']}_{rate['measure']}_per_100k",
                        "category": "health",
                        "value": rate["value_per_100k"],
                        "unit": "per_100k",
                        "period": rate["period"],
                        "source_id": rate["source_id"],
                        "locator": rate["locator"],
                        "definition_version": health_capacity.version,
                        "geography_level": "district",
                        "population_basis": (
                            f"{rate['population_period']} district population: "
                            f"{rate['population_denominator']}"
                        ),
                        "comparability_group": rate["comparability_group"],
                        "quality_flags": [],
                    },
                    ["district_id", "metric_key", "period"],
                )

        for category, formula in FORMULAS.items():
            _upsert(
                session,
                ScoreDefinition,
                {"version": score_version, "category": category, "formula": formula, "active": True},
                ["version", "category"],
            )
        for category, formula in EVIDENCE_V2_FORMULAS.items():
            _upsert(
                session,
                ScoreDefinition,
                {"version": "evidence-v2", "category": category, "formula": formula, "active": False},
                ["version", "category"],
            )

        now = datetime.fromisoformat(data["metadata"]["generated_on"]).replace(tzinfo=timezone.utc)
        for district in scored:
            for category, score in district["derived"]["scores"].items():
                detail = district["derived"]["score_details"][category]
                _upsert(
                    session,
                    ScoreResult,
                    {
                        "district_id": district_ids[district["slug"]],
                        "version": score_version,
                        "category": category,
                        "score": score,
                        "components": detail["components"],
                        "coverage": detail["coverage"],
                        "reporting_period": detail["reporting_period"],
                        "confidence": detail["confidence"],
                        "confidence_factors": detail["confidence_factors"],
                        "missing_components": detail["missing_components"],
                        "warnings": detail["warnings"],
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
