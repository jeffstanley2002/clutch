import asyncio
from types import SimpleNamespace

from sqlalchemy import func, select

from clutch.knowledge_base.clean_code import SEED_CLEAN_CODE_PRINCIPLES
from clutch.persistence import Base, create_session_factory
from clutch.persistence.models import KnowledgeBaseItemModel
from clutch.rag import (
    FallbackKnowledgeRetriever,
    LocalKnowledgeRetriever,
    OpenAIEmbeddingProvider,
    SqlAlchemyKnowledgeBase,
)
from clutch.rag.retrieval import _hybrid_score, _to_principle


class FailingRetriever:
    async def retrieve(self, query: str, **kwargs: object):
        raise RuntimeError("database unavailable")


class FakeEmbeddings:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        dimensions = int(kwargs["dimensions"])
        return SimpleNamespace(data=[SimpleNamespace(embedding=[0.25] * dimensions)])


def test_fallback_retriever_preserves_local_review_when_database_fails() -> None:
    retriever = FallbackKnowledgeRetriever(FailingRetriever())

    results = asyncio.run(retriever.retrieve("parameterized sql query", limit=1))

    assert results[0].id == "seed.clean_code.parameterized_queries"


def test_openai_embedding_provider_requests_schema_dimensions() -> None:
    embeddings = FakeEmbeddings()
    provider = OpenAIEmbeddingProvider(
        api_key="test-key",  # pragma: allowlist secret
        client=SimpleNamespace(embeddings=embeddings),
    )

    vector = asyncio.run(provider.embed("narrow error handling"))

    assert len(vector) == 1536
    assert embeddings.calls == [
        {
            "input": "narrow error handling",
            "model": "text-embedding-3-small",
            "dimensions": 1536,
            "encoding_format": "float",
        }
    ]


def test_seed_knowledge_base_is_idempotent() -> None:
    async def exercise() -> None:
        engine, session_factory = create_session_factory("sqlite+aiosqlite://")
        async with engine.begin() as connection:
            await connection.run_sync(
                lambda sync_connection: Base.metadata.create_all(
                    sync_connection,
                    tables=[KnowledgeBaseItemModel.__table__],
                )
            )
        knowledge_base = SqlAlchemyKnowledgeBase(session_factory)

        first_added = await knowledge_base.seed(SEED_CLEAN_CODE_PRINCIPLES)
        second_added = await knowledge_base.seed(SEED_CLEAN_CODE_PRINCIPLES)

        async with session_factory() as session:
            item_count = await session.scalar(
                select(func.count()).select_from(KnowledgeBaseItemModel)
            )
            sql_item = await session.get(
                KnowledgeBaseItemModel,
                "seed.clean_code.parameterized_queries",
            )
        assert first_added == 60
        assert second_added == 0
        assert item_count == 60
        assert sql_item is not None
        assert "security" in sql_item.tags
        assert sql_item.item_type == "reference"
        assert "backend" in sql_item.roles

        round_tripped = _to_principle(sql_item)
        assert round_tripped.item_type == "reference"
        assert "backend" in round_tripped.roles
        await engine.dispose()

    asyncio.run(exercise())


def test_hybrid_score_rewards_semantic_and_lexical_evidence() -> None:
    lexical_only = _hybrid_score(lexical_rank=1.0, vector_distance=None)
    semantic_only = _hybrid_score(lexical_rank=0.0, vector_distance=0.1)
    combined = _hybrid_score(lexical_rank=1.0, vector_distance=0.1)

    assert combined > semantic_only > lexical_only


def test_local_retriever_keeps_category_filtering() -> None:
    results = asyncio.run(
        LocalKnowledgeRetriever().retrieve(
            "shared behavior extraction",
            categories={"design"},
            limit=1,
        )
    )

    assert results[0].category == "design"
