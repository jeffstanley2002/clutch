"""Async SQLAlchemy engine and session construction."""

from __future__ import annotations

import os
from urllib.parse import quote

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def database_url_from_env() -> str:
    """Read a complete URL or safely assemble one from secret-friendly parts."""

    load_dotenv()
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        return database_url

    host = os.getenv("CLUTCH_DB_HOST", "").strip()
    password = os.getenv("CLUTCH_DB_PASSWORD", "")
    if not host or not password:
        return ""
    port = os.getenv("CLUTCH_DB_PORT", "5432").strip()
    name = os.getenv("CLUTCH_DB_NAME", "clutch").strip()
    user = os.getenv("CLUTCH_DB_USER", "clutch").strip()
    if not port.isdigit() or not name or not user:
        raise ValueError("database connection components are invalid")
    return (
        "postgresql+asyncpg://"
        f"{quote(user, safe='')}:{quote(password, safe='')}@{host}:{port}/"
        f"{quote(name, safe='')}"
    )


def normalize_async_database_url(database_url: str) -> str:
    """Convert common PostgreSQL URLs to SQLAlchemy's async driver form."""

    if database_url.startswith("postgresql://"):
        return database_url.replace(
            "postgresql://",
            "postgresql+asyncpg://",
            1,
        )
    return database_url


def create_session_factory(
    database_url: str,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Create an async engine and non-expiring session factory."""

    engine = create_async_engine(
        normalize_async_database_url(database_url),
        pool_pre_ping=True,
    )
    return engine, async_sessionmaker(engine, expire_on_commit=False)
