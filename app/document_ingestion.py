"""Checksum-pinned, source-specific document chunks for GPIS retrieval."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Iterable

from openpyxl import load_workbook
from sqlalchemy import select

from app.cache import retrieval_corpus_version
from app.database.models import DatasetMetadata, District, EvidenceChunk, Observation, Source
from app.database.seed import embed_missing
from app.database.session import session_factory
from app.embeddings import Embedder
from app.ingest_official_data import parse_count, resolve_district
from app.punjab_data import parse_percent


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "data" / "curated" / "document_sources.json"
DISTRICT_CONFIG_PATH = ROOT / "data" / "curated" / "pbs_table_1.json"
TABLE_12_CONFIG_PATH = ROOT / "data" / "curated" / "pbs_table_12.json"
FACILITIES = (
    "hospitals",
    "dispensaries",
    "rhcs",
    "bhus",
    "tb_clinics",
    "sh_centers",
    "mch_centers",
    "trauma_centers",
)


@dataclass(frozen=True)
class ParsedChunk:
    id: str
    source_id: str
    category: str
    period: str
    text: str
    locator: str
    chunk_type: str
    source_checksum: str
    parser_version: str
    table_reference: str
    district_slug: str | None = None
    parent_id: str | None = None
    page_number: int | None = None
    metrics: dict[str, Decimal | None] = field(default_factory=dict)
    extraction_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        payload = {
            "source_id": self.source_id,
            "period": self.period,
            "text": self.text,
            "locator": self.locator,
            "chunk_type": self.chunk_type,
            "parent_id": self.parent_id,
            "page_number": self.page_number,
            "table_reference": self.table_reference,
            "source_checksum": self.source_checksum,
            "parser_version": self.parser_version,
            "metadata": self.extraction_metadata,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class IngestionReport:
    sources: list[str] = field(default_factory=list)
    parsed_chunks: int = 0
    parent_chunks: int = 0
    child_chunks: int = 0
    districts_covered: list[str] = field(default_factory=list)
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    embedded: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _verify_file(config: dict) -> Path:
    path = ROOT / config["local_file"]
    if not path.is_file():
        raise ValueError(f"Registered source file is missing: {config['local_file']}")
    if _digest(path) != config["sha256"]:
        raise ValueError(f"Source checksum differs from the registered edition: {config['source_id']}")
    return path


def _decimal(value: int | float | Decimal) -> Decimal:
    return Decimal(str(value))


def parse_pbs_table_12(config: dict) -> list[ParsedChunk]:
    path = _verify_file(config)
    district_config = _load_json(DISTRICT_CONFIG_PATH)
    metric_config = _load_json(TABLE_12_CONFIG_PATH)
    if metric_config["sha256"] != config["sha256"] or metric_config["sheet"] != config["sheet"]:
        raise ValueError("PBS Table 12 document and observation contracts disagree")

    parent_id = "doc-pbs-table-12-parent-v1"
    parent = ParsedChunk(
        id=parent_id,
        source_id=config["source_id"],
        category=config["category"],
        period=config["period"],
        text=(
            "Pakistan Bureau of Statistics (PBS) Census 2023 Table 12 reports district literacy rates by sex and out-of-school "
            "population aged 5–16. Percentages use percent units; out-of-school population uses counts. "
            "Each child chunk represents one district block and repeats these headers and units."
        ),
        locator="Table 12; table title and column headers; punjab!A1:D4",
        chunk_type="table_parent",
        source_checksum=config["sha256"],
        parser_version=config["parser_version"],
        table_reference=config["table_reference"],
        extraction_metadata={"method": "openpyxl", "sheet": config["sheet"], "header_range": "A1:D4"},
    )

    workbook = load_workbook(path, read_only=True, data_only=False)
    chunks: list[ParsedChunk] = [parent]
    seen: set[str] = set()
    try:
        sheet = workbook[config["sheet"]]
        if (
            "TABLE 12" not in str(sheet["A1"].value)
            or "CENSUS-2023" not in str(sheet["A1"].value)
            or [sheet[f"{column}3"].value for column in "ABCD"] != ["INDICATORS", "TOTAL", "MALE", "FEMALE"]
            or sheet["B2"].value != "TOTAL"
        ):
            raise ValueError("Unexpected PBS Table 12 header layout")
        active_slug: str | None = None
        active_row: int | None = None
        values: dict[str, Decimal] = {}
        cells: dict[str, str] = {}

        def finish(end_row: int) -> None:
            nonlocal active_slug, active_row, values, cells
            if active_slug is None:
                return
            expected = {metric for mapping in metric_config["rows"].values() for metric in mapping.values()}
            if set(values) != expected:
                raise ValueError(f"Incomplete Table 12 metrics for {active_slug}: {sorted(expected - set(values))}")
            if active_slug in seen:
                raise ValueError(f"Duplicate PBS Table 12 district block: {active_slug}")
            seen.add(active_slug)
            name = district_config["districts"][active_slug]
            text = (
                f"Pakistan Bureau of Statistics (PBS) Census 2023, Table 12 reports for District: {name}. "
                f"Total literacy rate: {values['literacy_total_pct']} percent; "
                f"male literacy rate: {values['literacy_male_pct']} percent; "
                f"female literacy rate: {values['literacy_female_pct']} percent; "
                f"out-of-school children age 5–16: {values['out_of_school_children_5_16']} count. "
                "The literacy values are percentages and the out-of-school value is a population count."
            )
            chunks.append(
                ParsedChunk(
                    id=f"doc-pbs-table-12-{active_slug}-v1",
                    source_id=config["source_id"],
                    category=config["category"],
                    period=config["period"],
                    text=text,
                    locator=f"Table 12; {config['sheet']}!A{active_row}:D{end_row}; {name} District block",
                    chunk_type="table_row",
                    district_slug=active_slug,
                    parent_id=parent_id,
                    source_checksum=config["sha256"],
                    parser_version=config["parser_version"],
                    table_reference=config["table_reference"],
                    metrics=dict(values),
                    extraction_metadata={"method": "openpyxl", "sheet": config["sheet"], "cells": dict(cells)},
                )
            )
            active_slug, active_row, values, cells = None, None, {}, {}

        last_row = 4
        for row_number, row in enumerate(sheet.iter_rows(min_row=5, values_only=True), 5):
            last_row = row_number
            label = str(row[0] or "").strip()
            if label and all(value is None for value in row[1:]):
                finish(row_number - 1)
                active_slug = resolve_district(label, district_config) if label.endswith(" DISTRICT") else None
                active_row = row_number if active_slug else None
                continue
            if active_slug is None or label not in metric_config["rows"]:
                continue
            for column, metric in metric_config["rows"][label].items():
                original = row[ord(column) - ord("A")]
                parsed = parse_percent(original) if metric.endswith("_pct") else parse_count(original)
                if parsed is None:
                    raise ValueError(f"Missing {metric} for {active_slug}")
                values[metric] = _decimal(parsed)
                cells[metric] = f"{column}{row_number}"
        finish(last_row)
    finally:
        workbook.close()

    expected_districts = set(district_config["districts"])
    if seen != expected_districts:
        raise ValueError(f"Incomplete PBS Table 12 district coverage: {sorted(expected_districts - seen)}")
    return chunks


def _health_number(value: str) -> Decimal | None:
    normalized = value.replace(",", "").replace(" ", "")
    if normalized == "-":
        return None
    if not re.fullmatch(r"\d+(?:\.\d+)?", normalized):
        raise ValueError(f"Invalid health table value: {value!r}")
    return Decimal(normalized)


def parse_phs_2024_table_3(config: dict) -> list[ParsedChunk]:
    try:
        import pdfplumber
    except ImportError as exc:  # pragma: no cover - environment-specific dependency message
        raise ValueError('PDF ingestion requires: pip install -e ".[ingestion]"') from exc

    path = _verify_file(config)
    district_config = _load_json(DISTRICT_CONFIG_PATH)
    aliases = dict(config["district_aliases"])
    expected_districts = set(district_config["districts"])
    chunks: list[ParsedChunk] = []
    seen: set[str] = set()
    bounds = config["column_bounds"]

    with pdfplumber.open(path) as pdf:
        for page_number in config["pdf_pages"]:
            page = pdf.pages[page_number - 1]
            text = page.extract_text() or ""
            if "Table 3" not in text or "Health Institutions" not in text:
                raise ValueError(f"Unexpected PHS Table 3 layout on PDF page {page_number}")
            parent_id = f"doc-phs-2024-table-3-page-{page_number}-parent-v1"
            printed_page = page_number - config["printed_page_offset"]
            chunks.append(
                ParsedChunk(
                    id=parent_id,
                    source_id=config["source_id"],
                    category=config["category"],
                    period=config["period"],
                    text=(
                        "Punjab Health Statistics 2024 Table 3: Health Institutions by Division, District & Tehsil. "
                        "For hospitals, dispensaries, rural health centres, basic health units, TB clinics, social "
                        "health centres, MCH centres, and trauma centres, each category has institution and bed counts. "
                        "A printed dash means nil or insignificant and is preserved as not reported, never numeric zero."
                    ),
                    locator=f"Table 3; PDF page {page_number}; printed page {printed_page}; table headers",
                    chunk_type="table_parent",
                    page_number=page_number,
                    source_checksum=config["sha256"],
                    parser_version=config["parser_version"],
                    table_reference=config["table_reference"],
                    extraction_metadata={"method": "pdfplumber-fixed-columns", "printed_page": printed_page},
                )
            )
            for word in page.extract_words():
                if word["text"] != "District" or word["x0"] >= bounds[0] or word["top"] < 145:
                    continue
                chars = [character for character in page.chars if abs(character["top"] - word["top"]) < 1]
                source_name = "".join(
                    character["text"]
                    for character in sorted(chars, key=lambda character: character["x0"])
                    if character["x0"] < bounds[0]
                ).replace(" District", "").strip()
                slug = aliases.get(source_name)
                if slug is None:
                    slug = resolve_district(f"{source_name} DISTRICT", district_config)
                if slug in seen:
                    raise ValueError(f"Duplicate PHS Table 3 district row: {slug}")
                seen.add(slug)
                raw_values = [
                    "".join(
                        character["text"]
                        for character in sorted(chars, key=lambda character: character["x0"])
                        if left <= (character["x0"] + character["x1"]) / 2 < right
                    )
                    for left, right in zip(bounds, bounds[1:])
                ]
                parsed_values = [_health_number(value) for value in raw_values]
                metrics: dict[str, Decimal | None] = {}
                descriptions = []
                for facility, (count, beds) in zip(FACILITIES, zip(parsed_values[::2], parsed_values[1::2]), strict=True):
                    metrics[f"phs_{facility}_count"] = count
                    metrics[f"phs_{facility}_beds"] = beds
                    label = facility.replace("_", " ")
                    descriptions.append(
                        f"{label}: institutions {count if count is not None else 'not reported'}, "
                        f"beds {beds if beds is not None else 'not reported'}"
                    )
                name = district_config["districts"][slug]
                chunks.append(
                    ParsedChunk(
                        id=f"doc-phs-2024-table-3-{slug}-v1",
                        source_id=config["source_id"],
                        category=config["category"],
                        period=config["period"],
                        text=(
                            f"Punjab Health Statistics 2024, Table 3. District: {name}. "
                            + "; ".join(descriptions)
                            + ". Values are reported public institution and bed counts as at 31 December 2023; "
                            "not-reported cells are not zero."
                        ),
                        locator=f"Table 3; {source_name} District row; PDF page {page_number}; printed page {printed_page}",
                        chunk_type="table_row",
                        district_slug=slug,
                        parent_id=parent_id,
                        page_number=page_number,
                        source_checksum=config["sha256"],
                        parser_version=config["parser_version"],
                        table_reference=config["table_reference"],
                        metrics=metrics,
                        extraction_metadata={
                            "method": "pdfplumber-fixed-columns",
                            "printed_page": printed_page,
                            "source_district_label": source_name,
                            "raw_cells": raw_values,
                        },
                    )
                )
    if seen != expected_districts:
        raise ValueError(f"Incomplete PHS Table 3 district coverage: {sorted(expected_districts - seen)}")
    return chunks


PARSERS = {
    "pbs_table_12": parse_pbs_table_12,
    "phs_2024_table_3": parse_phs_2024_table_3,
}


def parse_sources(source: str) -> tuple[list[ParsedChunk], IngestionReport]:
    registry = _load_json(CONFIG_PATH)
    names = list(registry) if source == "all" else [source]
    if any(name not in registry for name in names):
        raise ValueError(f"Unsupported document source: {source}")
    chunks: list[ParsedChunk] = []
    for name in names:
        config = registry[name]
        chunks.extend(PARSERS[config["parser"]](config))
    ids = [chunk.id for chunk in chunks]
    if len(ids) != len(set(ids)):
        raise ValueError("Document parsers produced duplicate chunk IDs")
    report = IngestionReport(
        sources=names,
        parsed_chunks=len(chunks),
        parent_chunks=sum(chunk.chunk_type == "table_parent" for chunk in chunks),
        child_chunks=sum(chunk.chunk_type == "table_row" for chunk in chunks),
        districts_covered=sorted({chunk.district_slug for chunk in chunks if chunk.district_slug}),
    )
    return chunks, report


def _validate_against_observations(session, chunks: Iterable[ParsedChunk]) -> dict[str, int]:
    districts = dict(session.execute(select(District.slug, District.id)).all())
    for chunk in chunks:
        if not chunk.district_slug:
            continue
        district_id = districts.get(chunk.district_slug)
        if district_id is None:
            raise ValueError(f"Document chunk references unknown district: {chunk.district_slug}")
        rows = session.scalars(
            select(Observation).where(
                Observation.district_id == district_id,
                Observation.source_id == chunk.source_id,
                Observation.period == chunk.period,
                Observation.metric_key.in_(list(chunk.metrics)),
            )
        ).all()
        existing = {row.metric_key: row for row in rows}
        for metric, value in chunk.metrics.items():
            observation = existing.get(metric)
            if value is None:
                if observation is not None:
                    raise ValueError(
                        f"Document reports {chunk.district_slug}/{metric} as missing but the reviewed observation has a value"
                    )
                continue
            if observation is None:
                raise ValueError(f"Missing reviewed observation for {chunk.district_slug}/{metric}/{chunk.period}")
            if observation.value != value:
                raise ValueError(
                    f"Document disagrees with reviewed observation for {chunk.district_slug}/{metric}: "
                    f"{value} != {observation.value}"
                )
    return districts


def _chunk_values(chunk: ParsedChunk, district_ids: dict[str, int]) -> dict[str, Any]:
    return {
        "id": chunk.id,
        "district_id": district_ids[chunk.district_slug] if chunk.district_slug else None,
        "source_id": chunk.source_id,
        "category": chunk.category,
        "period": chunk.period,
        "text": chunk.text,
        "locator": chunk.locator,
        "chunk_type": chunk.chunk_type,
        "parent_id": chunk.parent_id,
        "page_number": chunk.page_number,
        "table_reference": chunk.table_reference,
        "source_checksum": chunk.source_checksum,
        "parser_version": chunk.parser_version,
        "content_hash": chunk.content_hash,
        "extraction_metadata": chunk.extraction_metadata,
    }


def load_chunks(database_url: str, chunks: list[ParsedChunk], report: IngestionReport, data_path: Path, score_version: str) -> None:
    sessions = session_factory(database_url)
    with sessions.begin() as session:
        source_ids = {chunk.source_id for chunk in chunks}
        for source_id in source_ids:
            source = session.get(Source, source_id)
            if source is None:
                raise ValueError(f"Source {source_id} is not registered; run the normal GPIS seed first")
            checksums = {chunk.source_checksum for chunk in chunks if chunk.source_id == source_id}
            if len(checksums) != 1 or source.sha256 not in {*checksums, None}:
                raise ValueError(f"Registered source checksum conflicts with document parser: {source_id}")
            if source.sha256 is None:
                source.sha256 = next(iter(checksums))
        district_ids = _validate_against_observations(session, chunks)
        ordered = sorted(chunks, key=lambda chunk: chunk.parent_id is not None)
        for chunk in ordered:
            values = _chunk_values(chunk, district_ids)
            existing = session.get(EvidenceChunk, chunk.id)
            if existing is None:
                session.add(EvidenceChunk(**values))
                report.inserted += 1
                session.flush()
                continue
            if existing.content_hash == chunk.content_hash:
                report.unchanged += 1
                continue
            for key, value in values.items():
                if key != "id":
                    setattr(existing, key, value)
            existing.embedding = None
            report.updated += 1
        session.flush()
        document_rows = session.execute(
            select(EvidenceChunk.id, EvidenceChunk.content_hash)
            .where(EvidenceChunk.chunk_type.in_(("table_parent", "table_row")))
            .order_by(EvidenceChunk.id)
        ).all()
        document_fingerprint = sha256(
            "\n".join(f"{chunk_id}:{content_hash}" for chunk_id, content_hash in document_rows).encode()
        ).hexdigest()
        corpus_version = sha256(
            (retrieval_corpus_version(data_path, score_version) + document_fingerprint).encode()
        ).hexdigest()
        metadata = session.get(DatasetMetadata, "document_corpus_version")
        if metadata is None:
            session.add(DatasetMetadata(key="document_corpus_version", value=document_fingerprint))
        else:
            metadata.value = document_fingerprint
        retrieval_metadata = session.get(DatasetMetadata, "retrieval_corpus_version")
        if retrieval_metadata is None:
            session.add(DatasetMetadata(key="retrieval_corpus_version", value=corpus_version))
        else:
            retrieval_metadata.value = corpus_version


def ingest_documents(
    source: str,
    *,
    database_url: str | None,
    data_path: Path,
    score_version: str,
    embedder: Embedder | None,
) -> IngestionReport:
    chunks, report = parse_sources(source)
    if database_url is None:
        report.warnings.append("Dry run: PostgreSQL observation parity and writes were not performed.")
        return report
    load_chunks(database_url, chunks, report, data_path, score_version)
    if embedder is not None:
        report.embedded = embed_missing(database_url, embedder)
    else:
        report.warnings.append("Embeddings were not generated; run `python -m app.cli embed` before vector retrieval.")
    return report
