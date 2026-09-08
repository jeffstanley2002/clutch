import asyncio

from clutch.cache import InMemoryJsonCache, cache_key
from clutch.knowledge_base import CleanCodePrinciple
from clutch.rag import CachedEmbeddingProvider, CachedKnowledgeRetriever
from clutch.schemas import Citation, FindingCategory


class CountingRetriever:
    def __init__(self) -> None:
        self.calls = 0

    async def retrieve(
        self,
        query: str,
        *,
        categories: set[FindingCategory] | None = None,
        limit: int = 3,
    ) -> list[CleanCodePrinciple]:
        self.calls += 1
        return [
            CleanCodePrinciple(
                id="cache.principle",
                title="Cache principle",
                category="testing",
                summary="Cache safe derived knowledge.",
                guidance="Never use raw source in a cache key.",
                tags=["cache"],
                citation=Citation(
                    source_id="cache.principle",
                    title="Cache principle",
                ),
            )
        ][:limit]


class CountingEmbeddingProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def embed(self, text: str) -> list[float]:
        self.calls += 1
        return [0.25, 0.75]


def test_cache_keys_hash_raw_inputs() -> None:
    sentinel = "RAW_QUERY_SENTINEL_29f"
    key = cache_key("retrieval", "v1", {"query": sentinel})

    assert key.startswith("clutch:retrieval:v1:")
    assert sentinel not in key
    assert len(key.rsplit(":", 1)[1]) == 64


def test_retrieval_cache_reports_hit_miss_and_avoids_duplicate_work() -> None:
    async def exercise() -> None:
        delegate = CountingRetriever()
        cache = InMemoryJsonCache()
        retriever = CachedKnowledgeRetriever(delegate, cache)
        sentinel = "untrusted retrieval query sentinel"

        first = await retriever.retrieve(sentinel)
        second = await retriever.retrieve(sentinel)

        assert first == second
        assert delegate.calls == 1
        assert cache.metrics.misses == 1
        assert cache.metrics.hits == 1
        assert cache.metrics.writes == 1
        assert all(sentinel not in key for key in cache.values)

    asyncio.run(exercise())


def test_embedding_cache_reuses_vectors_under_hashed_keys() -> None:
    async def exercise() -> None:
        delegate = CountingEmbeddingProvider()
        cache = InMemoryJsonCache()
        provider = CachedEmbeddingProvider(delegate, cache)
        sentinel = "private embedding input sentinel"

        first = await provider.embed(sentinel)
        second = await provider.embed(sentinel)

        assert first == second == [0.25, 0.75]
        assert delegate.calls == 1
        assert cache.metrics.hits == 1
        assert all(sentinel not in key for key in cache.values)

    asyncio.run(exercise())
