"""Operational commands for reviewed seed data and local embeddings."""

from __future__ import annotations

import argparse

from app.config import Settings
from app.database.seed import embed_missing, seed_database
from app.embeddings import MiniLMEmbedder


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    parser.add_argument("command", choices=("seed", "embed", "bootstrap"))
    args = parser.parse_args()
    settings = Settings.from_env()
    if settings.repository != "postgres" or not settings.database_url:
        parser.error("GPIS_REPOSITORY=postgres and GPIS_DATABASE_URL are required")

    if args.command in {"seed", "bootstrap"}:
        counts = seed_database(settings.database_url, settings.curated_data_path, settings.score_version)
        print(f"Seed complete: {counts}")
    if args.command in {"embed", "bootstrap"}:
        count = embed_missing(settings.database_url, MiniLMEmbedder(settings.embedding_model))
        print(f"Embedded evidence chunks: {count}")


if __name__ == "__main__":
    main()
