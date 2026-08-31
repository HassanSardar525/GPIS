import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import func, select, update

from app.database.models import EvidenceChunk, Observation, RetrievalTrace, ScoreDefinition, ScoreResult
from app.database.repository import PostgresRepository
from app.database.seed import embed_missing, seed_database
from app.database.session import session_factory
from app.comparisons import build_comparison
from app.embeddings import DeterministicTestEmbedder
from app.repositories import JsonRepository


ROOT = Path(__file__).resolve().parents[1]
DATABASE_URL = os.getenv("GPIS_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="GPIS_TEST_DATABASE_URL is not configured")


def test_migration_and_seed_are_idempotent():
    environment = {**os.environ, "GPIS_DATABASE_URL": DATABASE_URL}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=environment, check=True)
    first = seed_database(DATABASE_URL, ROOT / "data/curated/districts.json", "prototype-v1")
    second = seed_database(DATABASE_URL, ROOT / "data/curated/districts.json", "prototype-v1")
    assert first == second
    assert second == {"districts": 10, "observations": 556, "evidence_chunks": 67, "score_results": 40}


def test_provenance_is_complete_after_seed():
    sessions = session_factory(DATABASE_URL)
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Observation).where(Observation.source_id.is_(None))) == 0
        assert session.scalar(select(func.count()).select_from(EvidenceChunk).where(EvidenceChunk.locator == "")) == 0
        assert session.scalar(select(func.count()).select_from(ScoreResult).where(ScoreResult.coverage < 1)) == 0
        assert session.scalar(
            select(func.count()).select_from(Observation).where(Observation.definition_version == "")
        ) == 0
        assert session.scalar(
            select(func.count()).select_from(Observation).where(Observation.geography_level != "district")
        ) == 0
        assert session.scalar(
            select(func.count()).select_from(ScoreResult).where(ScoreResult.reporting_period == "")
        ) == 0
        health_score = session.scalar(
            select(ScoreResult).where(
                ScoreResult.version == "prototype-v1",
                ScoreResult.category == "health",
            )
        )
        assert float(health_score.confidence) == 0.8125
        assert float(health_score.confidence_factors["directness"]) == 0.5
        assert health_score.missing_components == []
        assert "relative facility-count capacity proxy" in health_score.warnings[0]
        assert session.scalar(
            select(func.count())
            .select_from(Observation)
            .where(Observation.comparability_group == "phs-table-3-public-capacity-v1")
        ) == 366
        assert session.scalar(
            select(func.count())
            .select_from(EvidenceChunk)
            .where(EvidenceChunk.id.like("%-health-capacity-%"))
        ) == 20
        anomaly = session.scalar(
            select(Observation).where(
                Observation.metric_key == "phs_mch_centers_beds",
                Observation.period == "2023-12-31",
                Observation.quality_flags != [],
            )
        )
        assert anomaly.value == 4
        assert "count is not inferred" in anomaly.quality_flags[0]
        normalized = session.scalar(
            select(Observation).where(
                Observation.metric_key == "phs_hospitals_count_per_100k",
                Observation.period == "2023-01-01",
            )
        )
        assert normalized.unit == "per_100k"
        assert "Census 2023 district population" in normalized.population_basis
        staged = session.scalar(
            select(ScoreDefinition).where(
                ScoreDefinition.version == "evidence-v2",
                ScoreDefinition.category == "health",
            )
        )
        assert staged.active is False
        assert staged.formula["components"] == {
            "capacity": 0.5,
            "activity": 0.25,
            "outcomes": 0.25,
        }


def test_pgvector_round_trip_and_embedding_seed_are_idempotent():
    embedder = DeterministicTestEmbedder()
    sessions = session_factory(DATABASE_URL)
    with sessions() as session:
        chunk = session.get(EvidenceChunk, "multan-education")
        chunk_id = chunk.id
        original_embedding = chunk.embedding
        chunk.embedding = None
        session.commit()
    with sessions() as session:
        expected_missing = session.scalar(
            select(func.count()).select_from(EvidenceChunk).where(EvidenceChunk.embedding.is_(None))
        )
    assert embed_missing(DATABASE_URL, embedder) == expected_missing
    assert embed_missing(DATABASE_URL, embedder) == 0
    data = __import__("json").loads((ROOT / "data/curated/districts.json").read_text(encoding="utf-8"))
    evidence = data["districts"][0]["evidence"][0]
    source = data["sources"][evidence["source_id"]]
    text = f"{evidence['category']}. {source['title']}. {evidence['text']}"
    repository = PostgresRepository(DATABASE_URL, "prototype-v1")
    results = repository.vector_search(embedder.embed([text])[0], ["multan"], "education", None, 3)
    assert results
    with sessions.begin() as session:
        chunk = session.get(EvidenceChunk, chunk_id)
        chunk.embedding = original_embedding


def test_postgres_development_trend_uses_canonical_evidence():
    repository = PostgresRepository(DATABASE_URL, "prototype-v1")
    trend = repository.development_trend("rahim-yar-khan")
    assert trend["change_percentage_points"] == 54.23
    assert trend["citation"]["evidence_id"] == "ryk-development-trend"


def test_postgres_health_capacity_trend_matches_json_contract():
    postgres = PostgresRepository(DATABASE_URL, "prototype-v1")
    json_repository = JsonRepository(ROOT / "data/curated/districts.json")

    assert postgres.health_capacity_trend("multan", "hospitals") == json_repository.health_capacity_trend(
        "multan", "hospitals"
    )
    assert postgres.health_capacity_trend("rajanpur", "mch_centers") == json_repository.health_capacity_trend(
        "rajanpur", "mch_centers"
    )


def test_postgres_score_reasoning_and_global_project_evidence():
    repository = PostgresRepository(DATABASE_URL, "prototype-v1")
    score_evidence = repository.score_search(
        "Why did Vehari receive its accountability score?", ["vehari"], None, 6
    )
    assert score_evidence[0].id == "score-vehari-accountability-prototype-v1"
    assert "98.5" in score_evidence[0].text
    project_evidence = repository.keyword_search("RAG architecture", ["vehari"], None, None, 6)
    assert any(item.id == "gpis-rag-architecture" for item in project_evidence)


def test_postgres_comparison_matches_json_contract():
    postgres = PostgresRepository(DATABASE_URL, "prototype-v1")
    json_repository = JsonRepository(ROOT / "data/curated/districts.json")

    actual = build_comparison(postgres, ["multan", "bahawalpur"], "accountability")
    expected = build_comparison(json_repository, ["multan", "bahawalpur"], "accountability")

    assert actual.districts == expected.districts
    assert actual.score_delta == expected.score_delta
    assert actual.rank_delta == expected.rank_delta
    assert actual.components == expected.components
    assert [item.change_percentage_points for item in actual.trends] == [
        item.change_percentage_points for item in expected.trends
    ]
    assert {item.evidence_id for item in actual.citations} == {
        item.evidence_id for item in expected.citations
    }
    assert {
        item.evidence_id: item.passage for item in actual.citations
    } == {
        item.evidence_id: item.passage for item in expected.citations
    }


def test_postgres_score_quality_contract_matches_json_backend():
    postgres = PostgresRepository(DATABASE_URL, "prototype-v1")
    json_repository = JsonRepository(ROOT / "data/curated/districts.json")

    assert postgres.list_districts() == json_repository.list_districts()
    assert postgres.rankings("health") == json_repository.rankings("health")
    postgres_detail = postgres.get_district("multan")
    json_detail = json_repository.get_district("multan")
    assert postgres_detail["score_details"] == json_detail["score_details"]
    assert postgres_detail["metadata"]["active_score_version"] == "prototype-v1"
    assert postgres_detail["metadata"]["evidence_v2_gate"]["activation_ready"] is False


def test_postgres_trace_persists_retrieval_details():
    repository = PostgresRepository(DATABASE_URL, "prototype-v1")
    trace_id = str(uuid.uuid4())
    repository.record_trace(
        {
            "id": trace_id,
            "question": "trace test",
            "filters": {"districts": ["multan"]},
            "route": "exact_fact",
            "retrieved_ids": ["fact-multan-literacy_total_pct"],
            "mode": "extractive",
            "latency_ms": 1.25,
            "details": {"retrieval": [{"id": "fact-multan-literacy_total_pct", "keyword_rank": 1}]},
        }
    )
    sessions = session_factory(DATABASE_URL)
    with sessions() as session:
        stored = session.get(RetrievalTrace, trace_id)
        assert stored.details["retrieval"][0]["keyword_rank"] == 1
    with sessions.begin() as session:
        stored = session.get(RetrievalTrace, trace_id)
        session.delete(stored)
