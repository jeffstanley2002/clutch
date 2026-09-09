"""Seed the durable Clutch knowledge base from the versioned local corpus."""

from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv

from clutch.knowledge_base.clean_code import SEED_CLEAN_CODE_PRINCIPLES
from clutch.persistence import create_session_factory, migration_database_url_from_env
from clutch.rag import (
    KnowledgeSyncReport,
    OpenAIEmbeddingProvider,
    SqlAlchemyKnowledgeBase,
)


async def seed() -> KnowledgeSyncReport:
    """Synchronize versioned seed rows and optionally refresh embeddings."""

    load_dotenv()
    database_url = migration_database_url_from_env()
    if not database_url:
        raise RuntimeError(
            "DIRECT_DATABASE_URL or DATABASE_URL is required to seed knowledge"
        )
    engine, session_factory = create_session_factory(database_url)
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    embedding_provider = (
        OpenAIEmbeddingProvider(
            api_key=api_key,
            model=os.getenv(
                "OPENAI_EMBEDDING_MODEL",
                "text-embedding-3-small",
            ),
        )
        if api_key
        else None
    )
    try:
        return await SqlAlchemyKnowledgeBase(
            session_factory,
            embedding_provider=embedding_provider,
        ).seed(SEED_CLEAN_CODE_PRINCIPLES)
    finally:
        await engine.dispose()


def main() -> None:
    report = asyncio.run(seed())
    print(
        "Knowledge synchronization complete: "
        f"inserted={report.inserted} updated={report.updated} "
        f"re-embedded={report.reembedded} unchanged={report.unchanged} "
        f"deactivated={report.deactivated}."
    )


if __name__ == "__main__":
    main()
