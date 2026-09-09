"""Retrieval adapters for local and PostgreSQL-backed knowledge search."""

from clutch.rag.query import (
    RetrievalQuery,
    build_retrieval_query,
    extract_code_retrieval_terms,
)
from clutch.rag.retrieval import (
    CachedEmbeddingProvider,
    CachedKnowledgeRetriever,
    EmbeddingProvider,
    FallbackKnowledgeRetriever,
    KnowledgeRetriever,
    KnowledgeSyncReport,
    LocalKnowledgeRetriever,
    OpenAIEmbeddingProvider,
    SqlAlchemyHybridRetriever,
    SqlAlchemyKnowledgeBase,
    SqlAlchemyVectorRetriever,
    knowledge_retriever_from_env,
)

__all__ = [
    "CachedEmbeddingProvider",
    "CachedKnowledgeRetriever",
    "EmbeddingProvider",
    "FallbackKnowledgeRetriever",
    "KnowledgeRetriever",
    "KnowledgeSyncReport",
    "LocalKnowledgeRetriever",
    "OpenAIEmbeddingProvider",
    "RetrievalQuery",
    "SqlAlchemyHybridRetriever",
    "SqlAlchemyKnowledgeBase",
    "SqlAlchemyVectorRetriever",
    "build_retrieval_query",
    "extract_code_retrieval_terms",
    "knowledge_retriever_from_env",
]
