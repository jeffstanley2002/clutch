# Cache Memory

## Current state

Async null, in-memory, and Redis JSON caches share one contract. Redis uses
short connect/socket timeouts, a bounded pool, TTLs, fail-open behavior, and
graceful close. Keys are `clutch:<namespace>:<version>:<sha256>`.

Only knowledge retrieval results and embedding vectors are cached. Safe
aggregate hits/misses/writes/errors/lookup time appear at `/runtime/cache`.

## Decisions

- Do not cache review responses because finding evidence can contain source.
- Do not place raw queries/source in Redis keys.
- Cache failures affect metrics, not review availability.

## Verified evidence

The container smoke produced miss=1/write=1, then hit=1 for the same synthetic
request; application latency was ~111 ms cold and ~8.6 ms cached.
