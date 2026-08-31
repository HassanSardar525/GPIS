from datetime import timedelta

import pytest

from app.errors import SessionExpired, SessionNotFound
from app.session_store import InMemorySessionStore, utcnow


def test_in_memory_session_expiry_is_explicit():
    store = InMemorySessionStore(ttl_hours=1)
    store.ensure_active("session-expiry-boundary")
    store.records["session-expiry-boundary"]["expires_at"] = utcnow() - timedelta(seconds=1)

    with pytest.raises(SessionExpired, match="expired"):
        store.get("session-expiry-boundary")
    assert store.records["session-expiry-boundary"]["status"] == "expired"


@pytest.mark.asyncio
async def test_in_memory_cleanup_is_idempotent():
    store = InMemorySessionStore(ttl_hours=1)
    store.ensure_active("session-cleanup-expired")
    store.records["session-cleanup-expired"]["expires_at"] = utcnow() - timedelta(seconds=1)

    assert await store.cleanup_expired() == 1
    assert await store.cleanup_expired() == 0
    with pytest.raises(SessionNotFound):
        store.get("session-cleanup-expired")
