"""Centralized environment-driven application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError as error:
        raise ValueError(f"{name} must be a number") from error


@dataclass(frozen=True, slots=True)
class Settings:
    environment: str = "development"
    repository: str = "json"
    database_url: str | None = None
    score_version: str = "prototype-v1"
    curated_data_path: Path = ROOT / "data" / "curated" / "districts.json"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    semantic_threshold: float = 0.35
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-20b"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_timeout_seconds: float = 15.0

    @classmethod
    def from_env(cls) -> "Settings":
        defaults = cls()
        repository = os.getenv("GPIS_REPOSITORY", "json").casefold()
        if repository not in {"json", "postgres"}:
            raise ValueError("GPIS_REPOSITORY must be 'json' or 'postgres'")
        database_url = os.getenv("GPIS_DATABASE_URL") or None
        if repository == "postgres" and not database_url:
            raise ValueError("GPIS_DATABASE_URL is required for the postgres repository")
        return cls(
            environment=os.getenv("GPIS_ENV", "development"),
            repository=repository,
            database_url=database_url,
            score_version=os.getenv("GPIS_SCORE_VERSION", "prototype-v1"),
            curated_data_path=Path(os.getenv("GPIS_CURATED_DATA", str(defaults.curated_data_path))),
            embedding_model=os.getenv("GPIS_EMBEDDING_MODEL", defaults.embedding_model),
            semantic_threshold=_float("GPIS_SEMANTIC_THRESHOLD", 0.35),
            groq_api_key=os.getenv("GROQ_API_KEY") or None,
            groq_model=os.getenv("GROQ_MODEL", defaults.groq_model),
            groq_base_url=os.getenv("GROQ_BASE_URL", defaults.groq_base_url),
            groq_timeout_seconds=_float("GROQ_TIMEOUT_SECONDS", 15.0),
        )
