"""Verify Clutch's PostgreSQL schema and public knowledge seed safely."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict, dataclass

from sqlalchemy import text

from clutch.persistence import create_session_factory
from clutch.persistence.database import (
    database_url_from_env,
    migration_database_url_from_env,
)
from clutch.persistence.models import EMBEDDING_DIMENSIONS

EXPECTED_TABLES = {
    "agent_runs",
    "alembic_version",
    "generated_questions",
    "interview_sessions",
    "interview_turns",
    "knowledge_base_items",
    "progress_snapshots",
    "retrieval_events",
    "review_findings",
    "review_sessions",
}
FORBIDDEN_RAW_COLUMNS = {
    "answer",
    "answer_text",
    "code",
    "raw_answer",
    "raw_code",
    "source_code",
}


@dataclass(frozen=True)
class DatabaseVerification:
    """Privacy-safe production verification result."""

    database_name: str
    postgres_major: int
    migration_revision: str | None
    tables: list[str]
    missing_tables: list[str]
    active_seeded_items: int
    valid_provenance_items: int
    valid_embedding_items: int
    forbidden_raw_columns: list[str]
    runtime_smoke_passed: bool

    def passes(self, *, require_seeded: bool) -> bool:
        schema_ok = (
            not self.missing_tables
            and self.migration_revision == "20260909_0003"
            and not self.forbidden_raw_columns
            and self.runtime_smoke_passed
        )
        if not require_seeded:
            return schema_ok
        return schema_ok and (
            self.active_seeded_items == 120
            and self.valid_provenance_items == 120
            and self.valid_embedding_items == 120
        )


async def verify(*, runtime: bool) -> DatabaseVerification:
    """Inspect only non-sensitive catalog and aggregate seed facts."""

    database_url = database_url_from_env() if runtime else migration_database_url_from_env()
    if not database_url:
        variable = "DATABASE_URL" if runtime else "DIRECT_DATABASE_URL"
        raise RuntimeError(f"{variable} is required")

    engine, session_factory = create_session_factory(database_url)
    try:
        async with session_factory() as session:
            metadata = (
                await session.execute(
                    text(
                        "SELECT current_database(), "
                        "current_setting('server_version_num')::integer / 10000"
                    )
                )
            ).one()
            tables = sorted(
                (
                    await session.execute(
                        text(
                            "SELECT table_name FROM information_schema.tables "
                            "WHERE table_schema = 'public'"
                        )
                    )
                ).scalars()
            )
            table_set = set(tables)
            migration_revision = None
            active_seeded_items = 0
            valid_provenance_items = 0
            valid_embedding_items = 0
            if "alembic_version" in table_set:
                migration_revision = (
                    await session.execute(text("SELECT version_num FROM alembic_version"))
                ).scalar_one_or_none()
            if "knowledge_base_items" in table_set:
                counts = (
                    await session.execute(
                        text(
                            "SELECT "
                            "count(*) FILTER (WHERE is_seeded AND is_active), "
                            "count(*) FILTER (WHERE is_seeded AND is_active "
                            "AND url IS NOT NULL AND url <> '' "
                            "AND source_family IS NOT NULL "
                            "AND section_locator IS NOT NULL "
                            "AND corpus_version IS NOT NULL "
                            "AND content_sha256 IS NOT NULL), "
                            "count(*) FILTER (WHERE is_seeded AND is_active "
                            "AND embedding IS NOT NULL "
                            "AND vector_dims(embedding) = :dimensions) "
                            "FROM knowledge_base_items"
                        ),
                        {"dimensions": EMBEDDING_DIMENSIONS},
                    )
                ).one()
                active_seeded_items = counts[0]
                valid_provenance_items = counts[1]
                valid_embedding_items = counts[2]

            raw_columns = sorted(
                f"{table}.{column}"
                for table, column in (
                    await session.execute(
                        text(
                            "SELECT table_name, column_name "
                            "FROM information_schema.columns "
                            "WHERE table_schema = 'public'"
                        )
                    )
                ).all()
                if column.lower() in FORBIDDEN_RAW_COLUMNS
            )

            runtime_smoke_passed = True
            if runtime:
                await session.execute(
                    text("CREATE TEMP TABLE clutch_runtime_smoke (value integer)")
                )
                await session.execute(
                    text("INSERT INTO clutch_runtime_smoke (value) VALUES (1)")
                )
                runtime_smoke_passed = (
                    await session.execute(
                        text("SELECT value FROM clutch_runtime_smoke")
                    )
                ).scalar_one() == 1
                await session.rollback()

            return DatabaseVerification(
                database_name=metadata[0],
                postgres_major=metadata[1],
                migration_revision=migration_revision,
                tables=tables,
                missing_tables=sorted(EXPECTED_TABLES - table_set),
                active_seeded_items=active_seeded_items,
                valid_provenance_items=valid_provenance_items,
                valid_embedding_items=valid_embedding_items,
                forbidden_raw_columns=raw_columns,
                runtime_smoke_passed=runtime_smoke_passed,
            )
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime",
        action="store_true",
        help="Use DATABASE_URL and exercise a temporary pooled read/write.",
    )
    parser.add_argument(
        "--require-seeded",
        action="store_true",
        help="Require exactly 120 active, sourced, 1536-dimensional seed rows.",
    )
    args = parser.parse_args()
    result = asyncio.run(verify(runtime=args.runtime))
    print(json.dumps(asdict(result), indent=2, sort_keys=True))
    if not result.passes(require_seeded=args.require_seeded):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
