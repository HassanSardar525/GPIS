"""Failure-safe cache-aside support for query embeddings and retrieval results."""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol


LOGGER = logging.getLogger(__name__)
CACHE_SCHEMA_VERSION = "1"


@dataclass(frozen=True, slots=True)
class CacheRead:
    value: str | None
    outcome: Literal["hit", "miss", "error", "disabled"]
    latency_ms: float = 0.0


class CacheBackend(Protocol):
    name: str

    @property
    def status(self) -> Literal["available", "unavailable", "disabled"]: ...
    def get(self, key: str) -> CacheRead: ...
    def set(self, key: str, value: str, ttl_seconds: int) -> bool: ...
    def delete(self, key: str) -> None: ...
    def acquire_lock(self, key: str, ttl_seconds: int) -> str | None: ...
    def release_lock(self, key: str, token: str) -> None: ...
    def close(self) -> None: ...


class NoopCache:
    name = "none"
    status: Literal["disabled"] = "disabled"

    def get(self, key: str) -> CacheRead:
        return CacheRead(None, "disabled")

    def set(self, key: str, value: str, ttl_seconds: int) -> bool:
        return False

    def delete(self, key: str) -> None:
        return None

    def acquire_lock(self, key: str, ttl_seconds: int) -> str | None:
        return None

    def release_lock(self, key: str, token: str) -> None:
        return None

    def close(self) -> None:
        return None


class RedisCache:
    """Redis cache that degrades to misses when Redis is slow or unavailable."""

    name = "redis"
    _RELEASE_LOCK = """
    if redis.call('get', KEYS[1]) == ARGV[1] then
        return redis.call('del', KEYS[1])
    end
    return 0
    """

    def __init__(self, url: str, timeout_seconds: float = 0.5, failure_cooldown_seconds: float = 30.0):
        from redis import Redis

        self.client = Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=timeout_seconds,
            socket_timeout=timeout_seconds,
            health_check_interval=30,
        )
        self.failure_cooldown_seconds = failure_cooldown_seconds
        self.disabled_until = 0.0
        self._status: Literal["available", "unavailable"] = "unavailable"
        try:
            self.client.ping()
            self._status = "available"
        except Exception as error:
            self._trip(error)

    @property
    def status(self) -> Literal["available", "unavailable"]:
        return self._status

    def _trip(self, error: Exception) -> None:
        if self._status != "unavailable" or time.monotonic() >= self.disabled_until:
            LOGGER.warning("Redis cache unavailable; bypassing cache: %s", type(error).__name__)
        self._status = "unavailable"
        self.disabled_until = time.monotonic() + self.failure_cooldown_seconds

    def _bypassed(self) -> bool:
        return time.monotonic() < self.disabled_until

    def get(self, key: str) -> CacheRead:
        if self._bypassed():
            return CacheRead(None, "error")
        started = time.perf_counter()
        try:
            value = self.client.get(key)
            self._status = "available"
            return CacheRead(
                value,
                "hit" if value is not None else "miss",
                round((time.perf_counter() - started) * 1000, 3),
            )
        except Exception as error:
            self._trip(error)
            return CacheRead(None, "error", round((time.perf_counter() - started) * 1000, 3))

    def set(self, key: str, value: str, ttl_seconds: int) -> bool:
        if self._bypassed():
            return False
        try:
            self.client.set(key, value, ex=ttl_seconds)
            self._status = "available"
            return True
        except Exception as error:
            self._trip(error)
            return False

    def delete(self, key: str) -> None:
        if self._bypassed():
            return
        try:
            self.client.delete(key)
        except Exception as error:
            self._trip(error)

    def acquire_lock(self, key: str, ttl_seconds: int) -> str | None:
        if self._bypassed():
            return None
        token = uuid.uuid4().hex
        try:
            return token if self.client.set(key, token, nx=True, ex=ttl_seconds) else None
        except Exception as error:
            self._trip(error)
            return None

    def release_lock(self, key: str, token: str) -> None:
        if self._bypassed():
            return
        try:
            self.client.eval(self._RELEASE_LOCK, 1, key, token)
        except Exception as error:
            self._trip(error)

    def close(self) -> None:
        self.client.close()


def build_cache(url: str | None) -> CacheBackend:
    return RedisCache(url) if url else NoopCache()


def cache_key(namespace: str, payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"gpis:{namespace}:v{CACHE_SCHEMA_VERSION}:{digest}"


def normalized_query(query: str) -> str:
    return " ".join(query.casefold().split())


def retrieval_corpus_version(data_path: Path, score_version: str) -> str:
    """Fingerprint every curated input that can affect retrieval or score explanations."""

    digest = hashlib.sha256()
    digest.update(score_version.encode("utf-8"))
    for path in sorted(
        [
            data_path,
            data_path.with_name("health_capacity_periods.json"),
            data_path.with_name("punjab_census.json"),
            data_path.with_name("evidence_qualification.json"),
        ],
        key=lambda item: item.name,
    ):
        if path.is_file():
            digest.update(path.name.encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()
