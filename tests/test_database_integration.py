import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import func, select, update

from app.database.models import EvidenceChunk, Observation, ScoreResult
from app.database.repository import PostgresRepository
from app.database.seed import embed_missing, seed_database
from app.database.session import session_factory
from app.embeddings import DeterministicTestEmbedder


ROOT = Path(__file__).resolve().parents[1]
DATABASE_URL = os.getenv("GPIS_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="GPIS_TEST_DATABASE_URL is not configured")


def test_migration_and_seed_are_idempotent():
    environment = {**os.environ, "GPIS_DATABASE_URL": DATABASE_URL}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=environment, check=True)
    first = seed_database(DATABASE_URL, ROOT / "data/curated/districts.json", "prototype-v1")
    second = seed_database(DATABASE_URL, ROOT / "data/curated/districts.json", "prototype-v1")
    assert first == second
    assert second == {"districts": 10, "observations": 190, "evidence_chunks": 40, "score_results": 40}


def test_provenance_is_complete_after_seed():
    sessions = session_factory(DATABASE_URL)
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Observation).where(Observation.source_id.is_(None))) == 0
        assert session.scalar(select(func.count()).select_from(EvidenceChunk).where(EvidenceChunk.locator == "")) == 0
        assert session.scalar(select(func.count()).select_from(ScoreResult).where(ScoreResult.coverage < 1)) == 0


def test_pgvector_round_trip_and_embedding_seed_are_idempotent():
    embedder = DeterministicTestEmbedder()
    sessions = session_factory(DATABASE_URL)
    with sessions.begin() as session:
        session.execute(update(EvidenceChunk).values(embedding=None))
    assert embed_missing(DATABASE_URL, embedder) == 40
    assert embed_missing(DATABASE_URL, embedder) == 0
    data = __import__("json").loads((ROOT / "data/curated/districts.json").read_text(encoding="utf-8"))
    evidence = data["districts"][0]["evidence"][0]
    source = data["sources"][evidence["source_id"]]
    text = f"{evidence['category']}. {source['title']}. {evidence['text']}"
    repository = PostgresRepository(DATABASE_URL, "prototype-v1")
    results = repository.vector_search(embedder.embed([text])[0], ["multan"], "education", None, 3)
    assert results[0].id == "multan-education"
