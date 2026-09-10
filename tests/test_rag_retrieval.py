import asyncio
from hashlib import sha256
from types import SimpleNamespace
from typing import Any, cast

import pytest
from sqlalchemy import func, select

from clutch.knowledge_base.clean_code import SEED_CLEAN_CODE_PRINCIPLES
from clutch.persistence import Base, create_session_factory
from clutch.persistence.models import KnowledgeBaseItemModel
from clutch.rag import (
    FallbackKnowledgeRetriever,
    LocalKnowledgeRetriever,
    OpenAIEmbeddingProvider,
    SqlAlchemyKnowledgeBase,
    SqlAlchemyVectorRetriever,
    knowledge_retriever_from_env,
)
from clutch.rag.retrieval import (
    _hybrid_score,
    _postgres_websearch_query,
    _principle_values,
    _to_principle,
)


class FailingRetriever:
    async def retrieve(self, query: str, **kwargs: object):
        raise RuntimeError("database unavailable")


class FakeEmbeddings:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        dimensions = int(kwargs["dimensions"])
        return SimpleNamespace(
            data=[SimpleNamespace(index=0, embedding=[0.25] * dimensions)]
        )


class FakeEmbeddingProvider:
    def __init__(self) -> None:
        self.queries: list[str] = []

    async def embed(self, text: str) -> list[float]:
        self.queries.append(text)
        return [0.25] * 1536


class FakeBatchEmbeddingProvider(FakeEmbeddingProvider):
    model_name = "fake-embedding-v1"

    def __init__(self) -> None:
        super().__init__()
        self.batches: list[list[str]] = []

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.batches.append(list(texts))
        return [[float(index + 1)] * 1536 for index, _ in enumerate(texts)]


class FakeScalarResult:
    def __init__(self, items: list[KnowledgeBaseItemModel]) -> None:
        self._items = items

    def all(self) -> list[KnowledgeBaseItemModel]:
        return self._items


class FakeExecuteResult:
    def __init__(self, items: list[KnowledgeBaseItemModel]) -> None:
        self._items = items

    def scalars(self) -> FakeScalarResult:
        return FakeScalarResult(self._items)


class FakeVectorSession:
    def __init__(self, items: list[KnowledgeBaseItemModel]) -> None:
        self._items = items
        self.executions = 0

    async def __aenter__(self) -> "FakeVectorSession":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def execute(self, statement: object) -> FakeExecuteResult:
        self.executions += 1
        return FakeExecuteResult(self._items)


class FakeVectorSessionFactory:
    def __init__(self, session: FakeVectorSession) -> None:
        self._session = session

    def __call__(self) -> FakeVectorSession:
        return self._session


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
            "input": ["narrow error handling"],
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

        first_report = await knowledge_base.seed(SEED_CLEAN_CODE_PRINCIPLES)
        second_report = await knowledge_base.seed(SEED_CLEAN_CODE_PRINCIPLES)

        async with session_factory() as session:
            item_count = await session.scalar(
                select(func.count()).select_from(KnowledgeBaseItemModel)
            )
            sql_item = await session.get(
                KnowledgeBaseItemModel,
                "seed.clean_code.parameterized_queries",
            )
        assert first_report.inserted == 120
        assert first_report.reembedded == 0
        assert second_report.unchanged == 120
        assert item_count == 120
        assert sql_item is not None
        assert "security" in sql_item.tags
        assert sql_item.item_type == "reference"
        assert "backend" in sql_item.roles

        round_tripped = _to_principle(sql_item)
        assert round_tripped.item_type == "reference"
        assert "backend" in round_tripped.roles
        await engine.dispose()

    asyncio.run(exercise())


def test_seed_sync_updates_reembeds_deactivates_and_preserves_unrelated_rows() -> None:
    async def exercise() -> None:
        engine, session_factory = create_session_factory("sqlite+aiosqlite://")
        async with engine.begin() as connection:
            await connection.run_sync(
                lambda sync_connection: Base.metadata.create_all(
                    sync_connection,
                    tables=[KnowledgeBaseItemModel.__table__],
                )
            )

        provider = FakeBatchEmbeddingProvider()
        knowledge_base = SqlAlchemyKnowledgeBase(
            session_factory,
            embedding_provider=provider,
        )
        original = SEED_CLEAN_CODE_PRINCIPLES[:2]
        first_report = await knowledge_base.seed(original)

        changed_summary = f"{original[0].summary} Updated for a new corpus release."
        changed = original[0].model_copy(
            update={
                "summary": changed_summary,
                "content_sha256": sha256(
                    f"{changed_summary}\n{original[0].guidance}".encode()
                ).hexdigest(),
            }
        )
        unrelated_values = _principle_values(original[1])
        unrelated_values.update(
            {
                "source_id": "custom.user_owned",
                "title": "User-owned item",
                "is_seeded": False,
            }
        )
        async with session_factory() as session:
            session.add(KnowledgeBaseItemModel(**unrelated_values))
            await session.commit()

        second_report = await knowledge_base.seed([changed])

        async with session_factory() as session:
            changed_row = await session.get(KnowledgeBaseItemModel, changed.id)
            obsolete_row = await session.get(
                KnowledgeBaseItemModel,
                original[1].id,
            )
            unrelated_row = await session.get(
                KnowledgeBaseItemModel,
                "custom.user_owned",
            )

        assert first_report.inserted == 2
        assert first_report.reembedded == 2
        assert second_report.updated == 1
        assert second_report.reembedded == 1
        assert second_report.deactivated == 1
        assert len(provider.batches) == 2
        assert changed_row is not None
        assert changed_row.principle == changed_summary
        assert changed_row.embedding_model == provider.model_name
        assert obsolete_row is not None and obsolete_row.is_active is False
        assert unrelated_row is not None and unrelated_row.is_active is True
        await engine.dispose()

    asyncio.run(exercise())


def test_hybrid_score_rewards_semantic_and_lexical_evidence() -> None:
    lexical_only = _hybrid_score(lexical_rank=1.0, vector_distance=None)
    semantic_only = _hybrid_score(lexical_rank=0.0, vector_distance=0.1)
    combined = _hybrid_score(lexical_rank=1.0, vector_distance=0.1)

    assert combined > semantic_only > lexical_only


def test_postgres_lexical_query_uses_bounded_or_terms() -> None:
    query = _postgres_websearch_query(
        "Backend intern rubric narrow exception handling narrow"
    )

    assert query == "backend OR intern OR rubric OR narrow OR exception OR handling"
    assert (
        len(
            _postgres_websearch_query(" ".join(f"term{n}" for n in range(80))).split(
                " OR "
            )
        )
        == 64
    )


def test_local_retriever_keeps_category_filtering() -> None:
    results = asyncio.run(
        LocalKnowledgeRetriever().retrieve(
            "shared behavior extraction",
            categories={"design"},
            limit=1,
        )
    )

    assert results[0].category == "design"


def test_measured_retrieval_default_is_local_lexical(monkeypatch: Any) -> None:
    monkeypatch.delenv("CLUTCH_RETRIEVAL_STRATEGY", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)

    assert isinstance(knowledge_retriever_from_env(), LocalKnowledgeRetriever)


def test_unknown_retrieval_strategy_fails_configuration(monkeypatch: Any) -> None:
    monkeypatch.setenv("CLUTCH_RETRIEVAL_STRATEGY", "unmeasured")

    with pytest.raises(ValueError, match="CLUTCH_RETRIEVAL_STRATEGY"):
        knowledge_retriever_from_env()


def test_vector_retriever_embeds_query_and_returns_typed_items() -> None:
    principle = SEED_CLEAN_CODE_PRINCIPLES[0]
    item = KnowledgeBaseItemModel(**_principle_values(principle))
    item.embedding = [0.5] * 1536
    session = FakeVectorSession([item])
    provider = FakeEmbeddingProvider()
    retriever = SqlAlchemyVectorRetriever(
        cast(Any, FakeVectorSessionFactory(session)),
        embedding_provider=provider,
    )

    results = asyncio.run(
        retriever.retrieve(
            "explicit incomplete work",
            categories={"maintainability"},
            limit=1,
        )
    )

    assert provider.queries == ["explicit incomplete work"]
    assert session.executions == 1
    assert [result.id for result in results] == [principle.id]
