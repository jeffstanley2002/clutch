"""Seed the durable Clutch knowledge base from the versioned local corpus."""

from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv

from clutch.knowledge_base.clean_code import SEED_CLEAN_CODE_PRINCIPLES
from clutch.persistence import create_session_factory
from clutch.rag import OpenAIEmbeddingProvider, SqlAlchemyKnowledgeBase


async def seed() -> int:
    """Upsert seed principles and optionally add OpenAI embeddings."""

    load_dotenv()
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is required to seed the knowledge base")
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
    added = asyncio.run(seed())
    print(f"Knowledge base seeded; {added} new items added.")


if __name__ == "__main__":
    main()
