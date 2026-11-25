from dataclasses import replace
from decimal import Decimal
import json
import os

import pytest

from app.document_ingestion import (
    CONFIG_PATH,
    IngestionReport,
    ROOT,
    load_chunks,
    parse_pbs_table_12,
    parse_sources,
)

PBS_FILE = ROOT / "data" / "raw" / "pbs_census_2023_table_12_punjab.xlsx"
PHS_FILE = ROOT / "data" / "raw" / "punjab_health_statistics_2024.pdf"


@pytest.mark.skipif(not PBS_FILE.is_file(), reason="Registered PBS workbook is not available")
def test_real_pbs_table_12_chunks_are_structured_and_provenanced():
    chunks, report = parse_sources("pbs_table_12")
    assert report.parsed_chunks == 37
    assert report.parent_chunks == 1
    assert report.child_chunks == 36
    assert len(report.districts_covered) == 36

    parent = chunks[0]
    multan = next(chunk for chunk in chunks if chunk.id == "doc-pbs-table-12-multan-v1")
    assert parent.chunk_type == "table_parent"
    assert multan.parent_id == parent.id
    assert multan.metrics == {
        "literacy_total_pct": Decimal("61.410495"),
        "literacy_male_pct": Decimal("67.280602"),
        "literacy_female_pct": Decimal("55.268645"),
        "out_of_school_children_5_16": Decimal("475376"),
    }
    assert "percent" in multan.text
    assert "population count" in multan.text
    assert "punjab!A1610:D1624" in multan.locator
    assert multan.source_checksum
    repeated = next(chunk for chunk in parse_sources("pbs_table_12")[0] if chunk.id == multan.id)
    assert len(multan.content_hash) == 64
    assert multan.content_hash == repeated.content_hash


@pytest.mark.skipif(not PHS_FILE.is_file(), reason="Registered PHS PDF is not available")
def test_real_phs_table_3_chunks_preserve_missing_cells():
    pytest.importorskip("pdfplumber")
    chunks, report = parse_sources("phs_2024_table_3")
    assert report.parsed_chunks == 41
    assert report.parent_chunks == 5
    assert report.child_chunks == 36
    multan = next(chunk for chunk in chunks if chunk.id == "doc-phs-2024-table-3-multan-v1")
    assert multan.page_number == 22
    assert multan.metrics["phs_dispensaries_count"] == Decimal("47")
    assert multan.metrics["phs_dispensaries_beds"] is None
    assert "beds not reported" in multan.text
    assert "not-reported cells are not zero" in multan.text
    assert multan.extraction_metadata["method"] == "pdfplumber-fixed-columns"


def test_changed_document_checksum_is_rejected(tmp_path):
    config = json.loads(CONFIG_PATH.read_text())["pbs_table_12"]
    changed = tmp_path / "changed.xlsx"
    changed.write_bytes(b"not the registered workbook")
    config = {**config, "local_file": str(changed)}
    with pytest.raises(ValueError, match="checksum"):
        parse_pbs_table_12(config)


def test_unexpected_spreadsheet_headers_are_rejected(tmp_path, monkeypatch):
    from hashlib import sha256
    from openpyxl import Workbook
    import app.document_ingestion as ingestion

    config = json.loads(CONFIG_PATH.read_text())["pbs_table_12"]
    malformed = tmp_path / "malformed.xlsx"
    workbook = Workbook()
    workbook.active.title = config["sheet"]
    workbook.active["A1"] = "Not PBS Table 12"
    workbook.save(malformed)
    config = {
        **config,
        "local_file": str(malformed),
        "sha256": sha256(malformed.read_bytes()).hexdigest(),
    }
    metric_config = json.loads(ingestion.TABLE_12_CONFIG_PATH.read_text())
    metric_config["sha256"] = config["sha256"]
    test_contract = tmp_path / "pbs_table_12.json"
    test_contract.write_text(json.dumps(metric_config))
    monkeypatch.setattr(ingestion, "TABLE_12_CONFIG_PATH", test_contract)
    with pytest.raises(ValueError, match="header layout"):
        parse_pbs_table_12(config)


def test_unknown_source_is_rejected():
    with pytest.raises(ValueError, match="Unsupported document source"):
        parse_sources("arbitrary_pdf")


def test_parent_context_is_attached_without_changing_locator():
    from types import SimpleNamespace
    from app.database.repository import PostgresRepository

    child = SimpleNamespace(id="child", text="District row", parent_id="parent")
    parent = SimpleNamespace(text="Table headers and units")
    session = SimpleNamespace(get=lambda model, identity: parent if identity == "parent" else None)
    assert PostgresRepository._context_text(session, child) == (
        "District row\n\nTable context: Table headers and units"
    )


@pytest.mark.skipif(
    not os.getenv("GPIS_PUNJAB_TEST_DATABASE_URL") or not PBS_FILE.is_file() or not PHS_FILE.is_file(),
    reason="Dedicated Punjab test database or registered source documents are not available",
)
def test_postgres_document_ingestion_is_idempotent_and_matches_observations():
    from sqlalchemy import select
    from app.database.models import DatasetMetadata, EvidenceChunk
    from app.database.seed import seed_database
    from app.database.session import session_factory

    url = os.environ["GPIS_PUNJAB_TEST_DATABASE_URL"]
    data_path = ROOT / "data" / "curated" / "districts.json"
    seed_database(url, data_path, "punjab-v1")
    chunks, _ = parse_sources("all")
    first = IngestionReport()
    load_chunks(url, chunks, first, data_path, "punjab-v1")
    second = IngestionReport()
    load_chunks(url, chunks, second, data_path, "punjab-v1")
    assert first.inserted + first.updated + first.unchanged == 78
    assert second.unchanged == 78
    assert second.inserted == second.updated == 0
    multan = next(chunk for chunk in chunks if chunk.id == "doc-pbs-table-12-multan-v1")
    conflicting_metrics = dict(multan.metrics)
    conflicting_metrics["literacy_total_pct"] += Decimal("1")
    conflicting = [
        replace(chunk, metrics=conflicting_metrics) if chunk.id == multan.id else chunk
        for chunk in chunks
    ]
    with pytest.raises(ValueError, match="disagrees with reviewed observation"):
        load_chunks(url, conflicting, IngestionReport(), data_path, "punjab-v1")
    with session_factory(url)() as session:
        corpus_before_seed = session.get(DatasetMetadata, "retrieval_corpus_version").value
    seed_database(url, data_path, "punjab-v1")
    with session_factory(url)() as session:
        assert session.get(DatasetMetadata, "retrieval_corpus_version").value == corpus_before_seed
        row = session.scalar(select(EvidenceChunk).where(EvidenceChunk.id == "doc-phs-2024-table-3-multan-v1"))
        assert row.parent_id == "doc-phs-2024-table-3-page-22-parent-v1"
        assert row.content_hash
        assert row.source_checksum
        assert row.extraction_metadata["method"] == "pdfplumber-fixed-columns"
