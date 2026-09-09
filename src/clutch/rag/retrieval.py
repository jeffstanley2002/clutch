"""Hybrid PostgreSQL retrieval with a deterministic lexical fallback."""

from __future__ import annotations

import os
import re
from collections.abc import Sequence
from typing import Any, Protocol, cast

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from clutch.cache import JsonCache, cache_key, json_cache_from_env
from clutch.knowledge_base import (
    CleanCodePrinciple,
    KnowledgeItemKind,
    SeniorityLevel,
    retrieve_clean_code_principles,
)
from clutch.knowledge_base.clean_code import SEED_CLEAN_CODE_PRINCIPLES
from clutch.llm.spend import (
    ModelBudgetUnavailable,
    SpendGuard,
    conservative_token_estimate,
    embedding_cost_usd,
    spend_guard_from_env,
)
from clutch.persistence.database import application_session_factory_from_env
from clutch.persistence.models import KnowledgeBaseItemModel
from clutch.schemas import Citation, FindingCategory

_LOCAL_PROVENANCE_BY_ID = {
    principle.id: principle for principle in SEED_CLEAN_CODE_PRINCIPLES
}


class EmbeddingProvider(Protocol):
    """Small boundary for whichever embedding model is configured later."""

    async def embed(self, text: str) -> list[float]: ...


class KnowledgeSyncReport(BaseModel):
    """Counts from one versioned corpus synchronization."""

    inserted: int = Field(default=0, ge=0)
    updated: int = Field(default=0, ge=0)
    reembedded: int = Field(default=0, ge=0)
    unchanged: int = Field(default=0, ge=0)
    deactivated: int = Field(default=0, ge=0)


class OpenAIEmbeddingProvider:
    """Create bounded 1536-dimensional vectors through the Embeddings API."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "text-embedding-3-small",
        dimensions: int = 1536,
        client: Any | None = None,
        spend_guard: SpendGuard | None = None,
    ) -> None:
        self._model = model
        self._dimensions = dimensions
        self._client = client or AsyncOpenAI(api_key=api_key)
        self._spend_guard = spend_guard or spend_guard_from_env()

    async def embed(self, text: str) -> list[float]:
        return (await self.embed_batch([text]))[0]

    @property
    def model_name(self) -> str:
        return self._model

    async def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed a bounded batch while reserving and reconciling one paid call."""

        if not texts:
            return []
        estimated_tokens = sum(conservative_token_estimate(text) for text in texts)
        reservation = await self._spend_guard.reserve(
            embedding_cost_usd(self._model, input_tokens=estimated_tokens)
        )
        response = await self._client.embeddings.create(
            input=list(texts),
            model=self._model,
            dimensions=self._dimensions,
            encoding_format="float",
        )
        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "total_tokens", None)
        if isinstance(input_tokens, int):
            try:
                await self._spend_guard.reconcile(
                    reservation,
                    embedding_cost_usd(self._model, input_tokens=input_tokens),
                )
            except ModelBudgetUnavailable:
                pass
        ordered = sorted(
            response.data,
            key=lambda item: int(getattr(item, "index", 0)),
        )
        embeddings = [list(item.embedding) for item in ordered]
        if len(embeddings) != len(texts) or any(
            len(embedding) != self._dimensions for embedding in embeddings
        ):
            raise ValueError("embedding dimensions do not match the database schema")
        return embeddings


class CachedEmbeddingProvider:
    """Cache derived vectors under hashed keys; embedding input is never a key."""

    def __init__(
        self,
        delegate: EmbeddingProvider,
        cache: JsonCache,
        *,
        ttl_seconds: int = 604_800,
    ) -> None:
        self._delegate = delegate
        self._cache = cache
        self._ttl_seconds = ttl_seconds

    async def embed(self, text: str) -> list[float]:
        key = cache_key("embedding", "v1", {"text": text})
        cached = await self._cache.get_json(key)
        if isinstance(cached, list) and all(
            isinstance(value, int | float) for value in cached
        ):
            return [float(value) for value in cached]
        embedding = await self._delegate.embed(text)
        await self._cache.set_json(
            key,
            embedding,
            ttl_seconds=self._ttl_seconds,
        )
        return embedding


class KnowledgeRetriever(Protocol):
    """Typed async retrieval interface consumed by LangGraph."""

    async def retrieve(
        self,
        query: str,
        *,
        categories: set[FindingCategory] | None = None,
        limit: int = 3,
    ) -> list[CleanCodePrinciple]: ...


class LocalKnowledgeRetriever:
    """Wrap the existing deterministic lexical retriever."""

    async def retrieve(
        self,
        query: str,
        *,
        categories: set[FindingCategory] | None = None,
        limit: int = 3,
    ) -> list[CleanCodePrinciple]:
        return retrieve_clean_code_principles(
            query,
            categories=categories,
            limit=limit,
        )


class FallbackKnowledgeRetriever:
    """Use durable retrieval when healthy and preserve the local fallback."""

    def __init__(
        self,
        primary: KnowledgeRetriever,
        fallback: KnowledgeRetriever | None = None,
    ) -> None:
        self._primary = primary
        self._fallback = fallback or LocalKnowledgeRetriever()

    async def retrieve(
        self,
        query: str,
        *,
        categories: set[FindingCategory] | None = None,
        limit: int = 3,
    ) -> list[CleanCodePrinciple]:
        try:
            results = await self._primary.retrieve(
                query,
                categories=categories,
                limit=limit,
            )
        except Exception:  # Database/model failures must not break local review.
            results = []
        if results:
            return results
        return await self._fallback.retrieve(
            query,
            categories=categories,
            limit=limit,
        )


class CachedKnowledgeRetriever:
    """Cache only public knowledge-base results, keyed by a query hash."""

    def __init__(
        self,
        delegate: KnowledgeRetriever,
        cache: JsonCache,
        *,
        ttl_seconds: int = 86_400,
    ) -> None:
        self._delegate = delegate
        self._cache = cache
        self._ttl_seconds = ttl_seconds

    async def retrieve(
        self,
        query: str,
        *,
        categories: set[FindingCategory] | None = None,
        limit: int = 3,
    ) -> list[CleanCodePrinciple]:
        key = cache_key(
            "knowledge-retrieval",
            "v1",
            {
                "query": query,
                "categories": sorted(categories or set()),
                "limit": limit,
            },
        )
        cached = await self._cache.get_json(key)
        if isinstance(cached, list):
            try:
                return [CleanCodePrinciple.model_validate(item) for item in cached]
            except Exception:
                pass
        principles = await self._delegate.retrieve(
            query,
            categories=categories,
            limit=limit,
        )
        await self._cache.set_json(
            key,
            [principle.model_dump(mode="json") for principle in principles],
            ttl_seconds=self._ttl_seconds,
        )
        return principles


class SqlAlchemyKnowledgeBase:
    """Seed the durable knowledge table without duplicating stable source IDs."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._embedding_provider = embedding_provider

    async def seed(
        self,
        principles: Sequence[CleanCodePrinciple],
    ) -> KnowledgeSyncReport:
        """Synchronize only versioned seed rows and re-embed changed content."""

        inserted = 0
        updated = 0
        unchanged = 0
        deactivated = 0
        reembedded = 0
        desired_ids = {principle.id for principle in principles}
        embedding_model = getattr(self._embedding_provider, "model_name", None)
        embedding_targets: list[tuple[KnowledgeBaseItemModel, str]] = []
        async with self._session_factory() as session:
            rows = await session.scalars(
                select(KnowledgeBaseItemModel).where(
                    or_(
                        KnowledgeBaseItemModel.is_seeded.is_(True),
                        KnowledgeBaseItemModel.source_id.in_(desired_ids),
                    )
                )
            )
            existing_by_id = {item.source_id: item for item in rows}
            for principle in principles:
                existing = existing_by_id.get(principle.id)
                values = _principle_values(
                    principle,
                    embedding_model=embedding_model,
                )
                if existing is None:
                    model = KnowledgeBaseItemModel(**values)
                    session.add(model)
                    inserted += 1
                    if self._embedding_provider is not None:
                        embedding_targets.append((model, model.search_text))
                    continue
                values.pop("embedding", None)
                if self._embedding_provider is None:
                    values.pop("embedding_model", None)
                content_changed = existing.content_sha256 != principle.content_sha256
                embedding_model_changed = existing.embedding_model != embedding_model
                changed = False
                for field, value in values.items():
                    if getattr(existing, field) != value:
                        setattr(existing, field, value)
                        changed = True
                needs_embedding = self._embedding_provider is not None and (
                    existing.embedding is None
                    or content_changed
                    or embedding_model_changed
                )
                if needs_embedding:
                    embedding_targets.append((existing, existing.search_text))
                if changed:
                    updated += 1
                elif not needs_embedding:
                    unchanged += 1

            for obsolete in existing_by_id.values():
                if obsolete.is_seeded and obsolete.source_id not in desired_ids:
                    if obsolete.is_active:
                        obsolete.is_active = False
                        deactivated += 1

            if embedding_targets:
                embeddings = await _embed_batch(
                    self._embedding_provider,
                    [text for _, text in embedding_targets],
                )
                for (model, _), embedding in zip(
                    embedding_targets,
                    embeddings,
                    strict=True,
                ):
                    model.embedding = embedding
                    model.embedding_model = cast(str | None, embedding_model)
                    reembedded += 1
            await session.commit()
        return KnowledgeSyncReport(
            inserted=inserted,
            updated=updated,
            reembedded=reembedded,
            unchanged=unchanged,
            deactivated=deactivated,
        )


class SqlAlchemyHybridRetriever:
    """Combine PostgreSQL full-text rank with optional pgvector similarity."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._embedding_provider = embedding_provider

    async def retrieve(
        self,
        query: str,
        *,
        categories: set[FindingCategory] | None = None,
        limit: int = 3,
    ) -> list[CleanCodePrinciple]:
        if limit < 1:
            return []

        query_embedding = (
            await self._embedding_provider.embed(query)
            if self._embedding_provider is not None
            else None
        )
        lexical_rank = func.ts_rank_cd(
            func.to_tsvector("english", KnowledgeBaseItemModel.search_text),
            func.websearch_to_tsquery("english", _postgres_websearch_query(query)),
        ).label("lexical_rank")
        statement = select(KnowledgeBaseItemModel, lexical_rank).where(
            KnowledgeBaseItemModel.is_active.is_(True),
            KnowledgeBaseItemModel.is_seeded.is_(True),
        )
        if categories:
            statement = statement.where(KnowledgeBaseItemModel.category.in_(categories))

        if query_embedding is None:
            statement = (
                statement.where(lexical_rank > 0)
                .order_by(desc(lexical_rank), KnowledgeBaseItemModel.source_id)
                .limit(limit)
            )
            async with self._session_factory() as session:
                rows = (await session.execute(statement)).all()
            return [_to_principle(item) for item, _ in rows]

        vector_distance = KnowledgeBaseItemModel.embedding.cosine_distance(
            query_embedding
        ).label("vector_distance")
        statement = (
            statement.add_columns(vector_distance)
            .where(
                or_(
                    lexical_rank > 0,
                    KnowledgeBaseItemModel.embedding.is_not(None),
                )
            )
            .order_by(desc(lexical_rank), vector_distance)
            .limit(max(limit * 4, limit))
        )
        async with self._session_factory() as session:
            rows = (await session.execute(statement)).all()

        candidates = [
            (
                _hybrid_score(
                    lexical_rank=float(rank or 0.0),
                    vector_distance=(float(distance) if distance is not None else None),
                ),
                item.source_id,
                _to_principle(item),
            )
            for item, rank, distance in rows
        ]
        candidates.sort(key=lambda candidate: (-candidate[0], candidate[1]))
        return [candidate[2] for candidate in candidates[:limit]]


class SqlAlchemyVectorRetriever:
    """Rank embedded knowledge items only by pgvector cosine distance."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self._session_factory = session_factory
        self._embedding_provider = embedding_provider

    async def retrieve(
        self,
        query: str,
        *,
        categories: set[FindingCategory] | None = None,
        limit: int = 3,
    ) -> list[CleanCodePrinciple]:
        if limit < 1:
            return []

        query_embedding = await self._embedding_provider.embed(query)
        vector_distance = KnowledgeBaseItemModel.embedding.cosine_distance(
            query_embedding
        )
        statement = select(KnowledgeBaseItemModel).where(
            KnowledgeBaseItemModel.is_active.is_(True),
            KnowledgeBaseItemModel.is_seeded.is_(True),
            KnowledgeBaseItemModel.embedding.is_not(None),
        )
        if categories:
            statement = statement.where(
                KnowledgeBaseItemModel.category.in_(categories)
            )
        statement = statement.order_by(
            vector_distance,
            KnowledgeBaseItemModel.source_id,
        ).limit(limit)
        async with self._session_factory() as session:
            items = (await session.execute(statement)).scalars().all()
        return [_to_principle(item) for item in items]


def knowledge_retriever_from_env() -> KnowledgeRetriever:
    """Prefer durable hybrid search when configured and always retain fallback."""

    load_dotenv()
    cache = json_cache_from_env()
    session_factory = application_session_factory_from_env()
    if session_factory is None:
        local: KnowledgeRetriever = LocalKnowledgeRetriever()
        return CachedKnowledgeRetriever(local, cache) if cache.enabled else local
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    embedding_provider: EmbeddingProvider | None = (
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
    if embedding_provider is not None and cache.enabled:
        embedding_provider = CachedEmbeddingProvider(embedding_provider, cache)
    retriever: KnowledgeRetriever = FallbackKnowledgeRetriever(
        SqlAlchemyHybridRetriever(
            session_factory,
            embedding_provider=embedding_provider,
        )
    )
    return CachedKnowledgeRetriever(retriever, cache) if cache.enabled else retriever


def _hybrid_score(
    *,
    lexical_rank: float,
    vector_distance: float | None,
) -> float:
    lexical_score = lexical_rank / (1.0 + lexical_rank)
    semantic_score = (
        max(0.0, min(1.0, 1.0 - vector_distance))
        if vector_distance is not None
        else 0.0
    )
    return (0.45 * lexical_score) + (0.55 * semantic_score)


def _postgres_websearch_query(query: str, *, max_terms: int = 64) -> str:
    """Match any bounded query term instead of requiring every term."""

    terms = list(dict.fromkeys(re.findall(r"[a-z0-9_]+", query.lower())))[:max_terms]
    return " OR ".join(terms) or "clutch"


def _principle_values(
    principle: CleanCodePrinciple,
    *,
    embedding_model: str | None = None,
) -> dict[str, object]:
    search_text = " ".join(
        [
            principle.id,
            principle.title,
            principle.summary,
            principle.guidance,
            principle.item_type,
            " ".join(principle.roles),
            " ".join(principle.seniority_levels),
            " ".join(principle.tags),
        ]
    )
    return {
        "source_id": principle.id,
        "title": principle.title,
        "category": principle.category,
        "item_type": principle.item_type,
        "roles": principle.roles,
        "seniority_levels": principle.seniority_levels,
        "principle": principle.summary,
        "rationale": principle.guidance,
        "interview_signal": principle.guidance,
        "tags": principle.tags,
        "url": principle.citation.url,
        "search_text": search_text,
        "source_family": principle.source_family,
        "source_title": principle.citation.title,
        "section_locator": principle.section_locator,
        "corpus_version": principle.corpus_version,
        "content_sha256": principle.content_sha256,
        "derived_from_ids": principle.derived_from_ids,
        "is_active": True,
        "is_seeded": True,
        "embedding_model": embedding_model,
        "embedding": None,
    }


def _to_principle(item: KnowledgeBaseItemModel) -> CleanCodePrinciple:
    provenance = _LOCAL_PROVENANCE_BY_ID.get(item.source_id)
    if provenance is None:
        raise ValueError("database knowledge item is absent from the versioned corpus")
    return CleanCodePrinciple(
        id=item.source_id,
        title=item.title,
        category=cast(FindingCategory, item.category),
        summary=item.principle,
        guidance=item.rationale,
        tags=item.tags,
        item_type=cast(KnowledgeItemKind, item.item_type),
        roles=item.roles,
        seniority_levels=cast(list[SeniorityLevel], item.seniority_levels),
        citation=Citation(
            source_id=item.source_id,
            title=item.source_title or item.title,
            url=item.url,
        ),
        source_family=cast(Any, item.source_family or provenance.source_family),
        section_locator=item.section_locator or provenance.section_locator,
        corpus_version=item.corpus_version or provenance.corpus_version,
        content_sha256=item.content_sha256 or provenance.content_sha256,
        derived_from_ids=item.derived_from_ids or provenance.derived_from_ids,
    )


async def _embed_batch(
    provider: EmbeddingProvider | None,
    texts: Sequence[str],
) -> list[list[float]]:
    if provider is None:
        return []
    batch_method = getattr(provider, "embed_batch", None)
    if callable(batch_method):
        result = await batch_method(texts)
        return cast(list[list[float]], result)
    return [await provider.embed(text) for text in texts]
