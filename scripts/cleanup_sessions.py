"""Delete expired GPIS sessions, checkpoints, and linked telemetry."""

from __future__ import annotations

import asyncio

from app.config import Settings
from app.session_store import PostgresCheckpointRuntime, PostgresSessionStore


async def cleanup() -> int:
    settings = Settings.from_env()
    if settings.repository != "postgres" or not settings.database_url:
        raise RuntimeError("GPIS_REPOSITORY=postgres and GPIS_DATABASE_URL are required")
    runtime = PostgresCheckpointRuntime(settings.database_url)
    store = PostgresSessionStore(settings.database_url, settings.session_ttl_hours)
    await runtime.start()
    store.attach_checkpointer(runtime.checkpointer)
    try:
        deleted = await store.cleanup_expired()
        print(f"Deleted {deleted} expired session(s).")
        return deleted
    finally:
        await runtime.close()


if __name__ == "__main__":
    asyncio.run(cleanup())
