# Progress Memory

## Current state

Progress aggregates category counts over review history for a validated local
profile ID and returns improved areas, persistent issues, next practice tasks,
and evidence session IDs. Snapshots can be stored in memory or PostgreSQL.

## Decisions

- Profiles are local opaque IDs; no raw source or answer history is required.
- Recommendations are deterministic category-to-task mappings until richer
  evidence justifies model generation.

## Known gaps

- No authenticated identity, snapshot history endpoint, or time-window trend
  visualization yet.
