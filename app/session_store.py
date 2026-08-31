"""Session lifecycle metadata and LangGraph checkpoint coordination."""

from __future__ import annotations

import os
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from sqlalchemy import delete, select

from app.database.models import ChatSession, RetrievalTrace
from app.database.session import session_factory
from app.errors import SessionExpired, SessionNotFound


os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def session_payload(record: ChatSession) -> dict:
    return {
        "session_id": record.id,
        "created_at": record.created_at,
        "last_activity_at": record.last_activity_at,
        "expires_at": record.expires_at,
        "message_count": record.message_count,
        "status": record.status,
    }


class SessionStore(Protocol):
    def ensure_active(self, session_id: str) -> dict: ...
    def touch(self, session_id: str) -> dict: ...
    def get(self, session_id: str) -> dict: ...
    async def delete(self, session_id: str) -> None: ...
    async def cleanup_expired(self) -> int: ...
    def attach_checkpointer(self, checkpointer: Any) -> None: ...


class InMemorySessionStore:
    def __init__(self, ttl_hours: int):
        self.ttl = timedelta(hours=ttl_hours)
        self.records: dict[str, dict] = {}
        self.checkpointer: Any = None

    def attach_checkpointer(self, checkpointer: Any) -> None:
        self.checkpointer = checkpointer

    def ensure_active(self, session_id: str) -> dict:
        now = utcnow()
        record = self.records.get(session_id)
        if record and record["expires_at"] <= now:
            record["status"] = "expired"
            raise SessionExpired("This conversation has expired. Start a new chat.")
        if not record:
            record = {
                "session_id": session_id,
                "created_at": now,
                "last_activity_at": now,
                "expires_at": now + self.ttl,
                "message_count": 0,
                "status": "active",
            }
            self.records[session_id] = record
        return dict(record)

    def touch(self, session_id: str) -> dict:
        record = self.ensure_active(session_id)
        now = utcnow()
        record.update(last_activity_at=now, expires_at=now + self.ttl, message_count=record["message_count"] + 1)
        self.records[session_id] = record
        return dict(record)

    def get(self, session_id: str) -> dict:
        if session_id not in self.records:
            raise SessionNotFound("Conversation not found.")
        return self.ensure_active(session_id)

    async def delete(self, session_id: str) -> None:
        if session_id not in self.records:
            raise SessionNotFound("Conversation not found.")
        if self.checkpointer:
            await self.checkpointer.adelete_thread(session_id)
        del self.records[session_id]

    async def cleanup_expired(self) -> int:
        now = utcnow()
        expired = [key for key, value in self.records.items() if value["expires_at"] <= now]
        for session_id in expired:
            if self.checkpointer:
                await self.checkpointer.adelete_thread(session_id)
            del self.records[session_id]
        return len(expired)


class PostgresSessionStore:
    def __init__(self, database_url: str, ttl_hours: int):
        self.sessions = session_factory(database_url)
        self.ttl = timedelta(hours=ttl_hours)
        self.checkpointer: Any = None

    def attach_checkpointer(self, checkpointer: Any) -> None:
        self.checkpointer = checkpointer

    def ensure_active(self, session_id: str) -> dict:
        now = utcnow()
        expired = False
        with self.sessions.begin() as database:
            record = database.get(ChatSession, session_id)
            if record and record.expires_at <= now:
                record.status = "expired"
                expired = True
            if not record:
                record = ChatSession(
                    id=session_id,
                    created_at=now,
                    last_activity_at=now,
                    expires_at=now + self.ttl,
                    message_count=0,
                    status="active",
                )
                database.add(record)
                database.flush()
            payload = session_payload(record)
        if expired:
            raise SessionExpired("This conversation has expired. Start a new chat.")
        return payload

    def touch(self, session_id: str) -> dict:
        now = utcnow()
        expired = False
        with self.sessions.begin() as database:
            record = database.get(ChatSession, session_id)
            if not record:
                raise SessionNotFound("Conversation not found.")
            if record.expires_at <= now:
                record.status = "expired"
                expired = True
            else:
                record.last_activity_at = now
                record.expires_at = now + self.ttl
                record.message_count += 1
            payload = session_payload(record)
        if expired:
            raise SessionExpired("This conversation has expired. Start a new chat.")
        return payload

    def get(self, session_id: str) -> dict:
        with self.sessions() as database:
            record = database.get(ChatSession, session_id)
            if not record:
                raise SessionNotFound("Conversation not found.")
        return self.ensure_active(session_id)

    async def delete(self, session_id: str) -> None:
        with self.sessions() as database:
            if not database.get(ChatSession, session_id):
                raise SessionNotFound("Conversation not found.")
        if self.checkpointer:
            await self.checkpointer.adelete_thread(session_id)
        with self.sessions.begin() as database:
            database.execute(delete(RetrievalTrace).where(RetrievalTrace.session_id == session_id))
            record = database.get(ChatSession, session_id)
            if record:
                database.delete(record)

    async def cleanup_expired(self) -> int:
        now = utcnow()
        with self.sessions() as database:
            expired = list(database.scalars(select(ChatSession.id).where(ChatSession.expires_at <= now)))
        for session_id in expired:
            if self.checkpointer:
                await self.checkpointer.adelete_thread(session_id)
        if expired:
            with self.sessions.begin() as database:
                database.execute(delete(RetrievalTrace).where(RetrievalTrace.session_id.in_(expired)))
                database.execute(delete(ChatSession).where(ChatSession.id.in_(expired)))
        return len(expired)


class PostgresCheckpointRuntime:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool: Any = None
        self.checkpointer: Any = None

    async def start(self) -> None:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg.rows import dict_row
        from psycopg_pool import AsyncConnectionPool

        conninfo = self.database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        self.pool = AsyncConnectionPool(
            conninfo=conninfo,
            open=False,
            kwargs={"autocommit": True, "row_factory": dict_row},
        )
        self.checkpointer = AsyncPostgresSaver(self.pool)
        await self.pool.open()
        await self.pool.wait()
        await self.checkpointer.setup()

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()
