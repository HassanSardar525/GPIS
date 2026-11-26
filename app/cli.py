"""Operational commands for reviewed seed data and local embeddings."""

from __future__ import annotations

import argparse
import json

from app.config import Settings
from app.database.seed import embed_missing, seed_database
from app.embeddings import MiniLMEmbedder


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("seed", "embed", "bootstrap"):
        commands.add_parser(name)
    ingest = commands.add_parser("ingest-documents", help="Parse registered official documents into retrieval chunks")
    ingest.add_argument(
        "--source",
        choices=("all", "pbs_table_12", "phs_2024_table_3"),
        default="all",
    )
    ingest.add_argument("--dry-run", action="store_true", help="Parse and validate source layouts without database writes")
    ingest.add_argument("--no-embed", action="store_true", help="Store chunks without generating missing embeddings")
    args = parser.parse_args()
    settings = Settings.from_env()
    if args.command == "ingest-documents":
        from app.document_ingestion import ingest_documents

        if not args.dry_run and (settings.repository != "postgres" or not settings.database_url):
            parser.error("GPIS_REPOSITORY=postgres and GPIS_DATABASE_URL are required unless --dry-run is used")
        report = ingest_documents(
            args.source,
            database_url=None if args.dry_run else settings.database_url,
            data_path=settings.curated_data_path,
            score_version=settings.score_version,
            embedder=(
                None
                if args.dry_run or args.no_embed
                else MiniLMEmbedder(settings.embedding_model)
            ),
        )
        print(json.dumps(report.to_dict(), indent=2))
        return

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
