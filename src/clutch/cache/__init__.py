"""Fail-open JSON caching for safe, derived Clutch data."""

from clutch.cache.json_cache import (
    CacheMetrics,
    InMemoryJsonCache,
    JsonCache,
    NullJsonCache,
    RedisJsonCache,
    cache_key,
    cache_metrics_snapshot,
    close_registered_caches,
    json_cache_from_env,
)

__all__ = [
    "CacheMetrics",
    "InMemoryJsonCache",
    "JsonCache",
    "NullJsonCache",
    "RedisJsonCache",
    "cache_key",
    "cache_metrics_snapshot",
    "close_registered_caches",
    "json_cache_from_env",
]
