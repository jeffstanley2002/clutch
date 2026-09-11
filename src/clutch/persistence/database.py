"""Async SQLAlchemy engine and session construction."""

from __future__ import annotations

import os
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_APPLICATION_ENGINE: AsyncEngine | None = None
_APPLICATION_SESSION_FACTORY: async_sessionmaker[AsyncSession] | None = None
_APPLICATION_DATABASE_URL: str | None = None


def database_url_from_env() -> str:
    """Read a complete URL or safely assemble one from secret-friendly parts."""

    load_dotenv()
    database_url = _clean_configured_database_url(os.getenv("DATABASE_URL", ""))
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


def migration_database_url_from_env() -> str:
    """Prefer Neon's direct URL for migrations and administrative seeding."""

    load_dotenv()
    direct_url = _clean_configured_database_url(
        os.getenv("DIRECT_DATABASE_URL", "")
    )
    return direct_url or database_url_from_env()


def _clean_configured_database_url(configured_url: str) -> str:
    """Tolerate common dashboard paste shapes without changing URL semantics."""

    database_url = configured_url.strip()
    if len(database_url) >= 2 and database_url[0] == database_url[-1]:
        if database_url[0] in {"'", '"'}:
            database_url = database_url[1:-1].strip()
    for prefix in ("DATABASE_URL=", "DIRECT_DATABASE_URL="):
        if database_url.startswith(prefix):
            database_url = database_url.removeprefix(prefix).strip()
    return database_url


def normalize_async_database_url(database_url: str) -> str:
    """Convert common PostgreSQL URLs to SQLAlchemy's async driver form."""

    normalized = database_url
    if normalized.startswith("postgresql://"):
        normalized = normalized.replace(
            "postgresql://",
            "postgresql+asyncpg://",
            1,
        )
    if not normalized.startswith("postgresql+asyncpg://"):
        return normalized

    parts = urlsplit(normalized)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)
    if sslmode in {"require", "verify-ca", "verify-full"}:
        query["ssl"] = "require"
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )


def create_session_factory(
    database_url: str,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Create an async engine and non-expiring session factory."""

    engine = create_async_engine(
        normalize_async_database_url(database_url),
        pool_pre_ping=True,
    )
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def application_session_factory_from_env() -> (
    async_sessionmaker[AsyncSession] | None
):
    """Return the one shared runtime pool used by every application repository."""

    global _APPLICATION_DATABASE_URL
    global _APPLICATION_ENGINE
    global _APPLICATION_SESSION_FACTORY

    database_url = database_url_from_env()
    if not database_url:
        return None
    normalized_url = normalize_async_database_url(database_url)
    if _APPLICATION_SESSION_FACTORY is not None:
        if normalized_url != _APPLICATION_DATABASE_URL:
            raise RuntimeError("application database URL changed after pool creation")
        return _APPLICATION_SESSION_FACTORY
    engine, session_factory = create_session_factory(normalized_url)
    _APPLICATION_ENGINE = engine
    _APPLICATION_SESSION_FACTORY = session_factory
    _APPLICATION_DATABASE_URL = normalized_url
    return session_factory


async def close_application_database() -> None:
    """Close and clear the shared application engine during graceful shutdown."""

    global _APPLICATION_DATABASE_URL
    global _APPLICATION_ENGINE
    global _APPLICATION_SESSION_FACTORY

    if _APPLICATION_ENGINE is not None:
        await _APPLICATION_ENGINE.dispose()
    _APPLICATION_ENGINE = None
    _APPLICATION_SESSION_FACTORY = None
    _APPLICATION_DATABASE_URL = None
