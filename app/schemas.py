"""Typed public contracts and internal retrieval records."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


Category = Literal["education", "health", "accountability"]
RankingCategory = Literal["overall", "education", "health", "accountability"]


class AnswerMode(StrEnum):
    GROQ = "groq"
    EXTRACTIVE = "extractive"
    ABSTAINED = "abstained"


class QuestionRoute(StrEnum):
    CONVERSATION = "conversation"
    EXACT_FACT = "exact_fact"
    COMPARISON = "comparison"
    METHODOLOGY = "methodology"
    SCORE_EXPLANATION = "score_explanation"
    PROJECT = "project"
    EVIDENCE = "evidence"
    TEMPORAL_COMPARISON = "temporal_comparison"
    UNSUPPORTED = "unsupported"


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    publisher: str
    title: str
    period: str
    url: str
    local_file: str | None = None
    sha256: str | None = None


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    source_id: str
    publisher: str
    title: str
    period: str
    url: str
    locator: str


class ScoreSet(BaseModel):
    education: float = Field(ge=0, le=100)
    health: float = Field(ge=0, le=100)
    accountability: float = Field(ge=0, le=100)
    overall: float = Field(ge=0, le=100)


class ScoreResult(BaseModel):
    category: RankingCategory
    score: float = Field(ge=0, le=100)
    version: str
    components: dict[str, float]
    coverage: float = Field(ge=0, le=1)
    calculated_at: str | None = None


class RankingEntry(BaseModel):
    rank: int = Field(ge=1)
    slug: str
    name: str
    score: float = Field(ge=0, le=100)


class DistrictSummary(BaseModel):
    slug: str
    name: str
    scores: ScoreSet


class DistrictListResponse(BaseModel):
    districts: list[DistrictSummary]
    metadata: dict[str, Any]


class DistrictDetail(BaseModel):
    model_config = ConfigDict(extra="allow")

    slug: str
    name: str
    population_2023: int = Field(gt=0)
    education: dict[str, float | int]
    health: dict[str, float | int]
    accountability: dict[str, float | int]
    derived: dict[str, Any]
    evidence: list[dict[str, Any]]
    rankings: dict[RankingCategory, RankingEntry]
    sources: dict[str, dict[str, Any]]
    metadata: dict[str, Any]


class RankingResponse(BaseModel):
    category: RankingCategory
    rankings: list[RankingEntry]


class TrendPeriod(BaseModel):
    period: str
    final_grant_million_pkr: float
    expenditure_million_pkr: float
    utilization_pct: float


class TrendResponse(BaseModel):
    district_slug: str
    district_name: str
    metric: Literal["development_budget_utilization_pct"]
    periods: list[TrendPeriod]
    change_percentage_points: float
    direction: Literal["increased", "decreased", "unchanged"]
    warnings: list[str]
    citation: Citation


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=500)
    districts: list[str] = Field(default_factory=list, max_length=10)
    district: str | None = Field(default=None, description="Compatibility alias for one selected district")
    category: Category | None = None
    period: str | None = Field(default=None, max_length=80)
    session_id: str | None = Field(default=None, min_length=8, max_length=100)

    @field_validator("question")
    @classmethod
    def clean_question(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("question must not be blank")
        return value

    def selected_districts(self) -> list[str]:
        selected = list(dict.fromkeys(self.districts))
        if self.district and self.district not in selected:
            selected.append(self.district)
        return selected


class RetrievedEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    district_slug: str
    district_name: str
    category: str
    text: str
    source_id: str
    locator: str
    period: str
    keyword_rank: int | None = None
    vector_rank: int | None = None
    semantic_similarity: float | None = None
    rrf_score: float = 0
    citation: Citation


class ChatResponse(BaseModel):
    answer: str
    mode: AnswerMode
    route: QuestionRoute
    citations: list[Citation]
    warnings: list[str] = Field(default_factory=list)
    trace_id: str
    abstained: bool
    session_id: str | None = None
    tools_used: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    repository: Literal["json", "postgres"]
    database: Literal["available", "not_configured", "unavailable"]
    groq: Literal["configured", "fallback"]
    embedding_model: str
    phoenix: Literal["configured", "disabled", "unavailable"]


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
