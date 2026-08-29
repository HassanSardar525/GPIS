"""Normalized facts, provenance, evidence, scores, and retrieval traces."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import Computed, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class District(Base):
    __tablename__ = "districts"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    population_2023: Mapped[int] = mapped_column(Integer)
    observations: Mapped[list["Observation"]] = relationship(back_populates="district")


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    publisher: Mapped[str] = mapped_column(String(250))
    title: Mapped[str] = mapped_column(Text)
    period: Mapped[str] = mapped_column(String(100))
    url: Mapped[str] = mapped_column(Text)
    local_file: Mapped[str | None] = mapped_column(Text)
    sha256: Mapped[str | None] = mapped_column(String(64))


class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (UniqueConstraint("district_id", "metric_key", "period", name="uq_observation_identity"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    district_id: Mapped[int] = mapped_column(ForeignKey("districts.id", ondelete="CASCADE"), index=True)
    metric_key: Mapped[str] = mapped_column(String(120), index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    value: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    unit: Mapped[str] = mapped_column(String(50))
    period: Mapped[str] = mapped_column(String(100), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"))
    locator: Mapped[str] = mapped_column(Text)
    definition_version: Mapped[str] = mapped_column(String(80), default="prototype-v1")
    geography_level: Mapped[str] = mapped_column(String(40), default="district")
    population_basis: Mapped[str | None] = mapped_column(String(160), nullable=True)
    comparability_group: Mapped[str | None] = mapped_column(String(120), index=True, nullable=True)
    quality_flags: Mapped[list] = mapped_column(JSONB, default=list)
    district: Mapped[District] = relationship(back_populates="observations")
    source: Mapped[Source] = relationship()


class EvidenceChunk(Base):
    __tablename__ = "evidence_chunks"

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    district_id: Mapped[int | None] = mapped_column(
        ForeignKey("districts.id", ondelete="CASCADE"), index=True, nullable=True
    )
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"))
    category: Mapped[str] = mapped_column(String(40), index=True)
    period: Mapped[str] = mapped_column(String(100), index=True)
    text: Mapped[str] = mapped_column(Text)
    locator: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', coalesce(category, '') || ' ' || coalesce(text, ''))", persisted=True),
    )
    district: Mapped[District] = relationship()
    source: Mapped[Source] = relationship()


Index("ix_evidence_search_vector", EvidenceChunk.search_vector, postgresql_using="gin")
Index("ix_evidence_embedding_hnsw", EvidenceChunk.embedding, postgresql_using="hnsw", postgresql_ops={"embedding": "vector_cosine_ops"})


class ScoreDefinition(Base):
    __tablename__ = "score_definitions"
    __table_args__ = (UniqueConstraint("version", "category", name="uq_score_definition"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[str] = mapped_column(String(80), index=True)
    category: Mapped[str] = mapped_column(String(40))
    formula: Mapped[dict] = mapped_column(JSONB)
    active: Mapped[bool] = mapped_column(default=True)


class ScoreResult(Base):
    __tablename__ = "score_results"
    __table_args__ = (UniqueConstraint("district_id", "version", "category", name="uq_score_result"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    district_id: Mapped[int] = mapped_column(ForeignKey("districts.id", ondelete="CASCADE"), index=True)
    version: Mapped[str] = mapped_column(String(80), index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    score: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    components: Mapped[dict] = mapped_column(JSONB)
    coverage: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    reporting_period: Mapped[str] = mapped_column(String(160), default="mixed-current-period")
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    confidence_factors: Mapped[dict] = mapped_column(JSONB, default=dict)
    missing_components: Mapped[list] = mapped_column(JSONB, default=list)
    warnings: Mapped[list] = mapped_column(JSONB, default=list)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    district: Mapped[District] = relationship()


class DatasetMetadata(Base):
    __tablename__ = "dataset_metadata"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[dict | str | int | float | bool] = mapped_column(JSONB)


class RetrievalTrace(Base):
    __tablename__ = "retrieval_traces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    question: Mapped[str] = mapped_column(Text)
    filters: Mapped[dict] = mapped_column(JSONB)
    route: Mapped[str] = mapped_column(String(40), index=True)
    retrieved_ids: Mapped[list] = mapped_column(JSONB)
    mode: Mapped[str] = mapped_column(String(40), index=True)
    latency_ms: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
