"""Async JSON cache whose keys never contain raw user or repository content."""

from __future__ import annotations

import json
import os
from hashlib import sha256
from time import perf_counter
from typing import Any, Protocol

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field
from redis.asyncio import Redis
from redis.exceptions import RedisError


class CacheMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    hits: int = Field(default=0, ge=0)
    misses: int = Field(default=0, ge=0)
    writes: int = Field(default=0, ge=0)
    errors: int = Field(default=0, ge=0)
    lookup_ms: float = Field(default=0.0, ge=0.0)


class JsonCache(Protocol):
    @property
    def enabled(self) -> bool: ...

    @property
    def metrics(self) -> CacheMetrics: ...

    async def get_json(self, key: str) -> Any | None: ...

    async def set_json(self, key: str, value: Any, *, ttl_seconds: int) -> None: ...

    async def aclose(self) -> None: ...


class _MutableMetrics:
    def __init__(self) -> None:
        self.hits = 0
        self.misses = 0
        self.writes = 0
        self.errors = 0
        self.lookup_ms = 0.0

    def snapshot(self) -> CacheMetrics:
        return CacheMetrics(
            hits=self.hits,
            misses=self.misses,
            writes=self.writes,
            errors=self.errors,
            lookup_ms=self.lookup_ms,
        )


class NullJsonCache:
    @property
    def enabled(self) -> bool:
        return False

    @property
    def metrics(self) -> CacheMetrics:
        return CacheMetrics()

    async def get_json(self, key: str) -> Any | None:
        return None

    async def set_json(self, key: str, value: Any, *, ttl_seconds: int) -> None:
        return None

    async def aclose(self) -> None:
        return None


class InMemoryJsonCache:
    """Deterministic test/local cache with the same metrics contract as Redis."""

    def __init__(self) -> None:
        self.values: dict[str, Any] = {}
        self._metrics = _MutableMetrics()

    @property
    def enabled(self) -> bool:
        return True

    @property
    def metrics(self) -> CacheMetrics:
        return self._metrics.snapshot()

    async def get_json(self, key: str) -> Any | None:
        started_at = perf_counter()
        value = self.values.get(key)
        self._metrics.lookup_ms += (perf_counter() - started_at) * 1_000
        if value is None:
            self._metrics.misses += 1
        else:
            self._metrics.hits += 1
        return value

    async def set_json(self, key: str, value: Any, *, ttl_seconds: int) -> None:
        self.values[key] = value
        self._metrics.writes += 1

    async def aclose(self) -> None:
        return None


class RedisJsonCache:
    """Shared async Redis client that fails open without exposing cached values."""

    def __init__(self, url: str) -> None:
        self._client: Redis = Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
            max_connections=10,
        )
        self._metrics = _MutableMetrics()

    @property
    def enabled(self) -> bool:
        return True

    @property
    def metrics(self) -> CacheMetrics:
        return self._metrics.snapshot()

    async def get_json(self, key: str) -> Any | None:
        started_at = perf_counter()
        try:
            payload = await self._client.get(key)
        except RedisError:
            self._metrics.errors += 1
            return None
        finally:
            self._metrics.lookup_ms += (perf_counter() - started_at) * 1_000
        if payload is None:
            self._metrics.misses += 1
            return None
        try:
            result = json.loads(payload)
        except json.JSONDecodeError:
            self._metrics.errors += 1
            return None
        self._metrics.hits += 1
        return result

    async def set_json(self, key: str, value: Any, *, ttl_seconds: int) -> None:
        try:
            payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
            await self._client.set(key, payload, ex=ttl_seconds)
        except (RedisError, TypeError, ValueError):
            self._metrics.errors += 1
            return
        self._metrics.writes += 1

    async def aclose(self) -> None:
        await self._client.aclose()


_REGISTERED_CACHES: list[RedisJsonCache] = []


def json_cache_from_env() -> JsonCache:
    load_dotenv()
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        return NullJsonCache()
    cache = RedisJsonCache(redis_url)
    _REGISTERED_CACHES.append(cache)
    return cache


def cache_key(namespace: str, version: str, payload: Any) -> str:
    """Hash canonical input so Redis keys cannot disclose source or prompts."""

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = sha256(canonical.encode("utf-8")).hexdigest()
    return f"clutch:{namespace}:{version}:{digest}"


def cache_metrics_snapshot() -> CacheMetrics:
    snapshots = [cache.metrics for cache in _REGISTERED_CACHES]
    return CacheMetrics(
        hits=sum(item.hits for item in snapshots),
        misses=sum(item.misses for item in snapshots),
        writes=sum(item.writes for item in snapshots),
        errors=sum(item.errors for item in snapshots),
        lookup_ms=sum(item.lookup_ms for item in snapshots),
    )


async def close_registered_caches() -> None:
    for cache in _REGISTERED_CACHES:
        await cache.aclose()
    _REGISTERED_CACHES.clear()
