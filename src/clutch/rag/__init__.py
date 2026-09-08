"""Retrieval adapters for local and PostgreSQL-backed knowledge search."""

from clutch.rag.query import extract_code_retrieval_terms
from clutch.rag.retrieval import (
    CachedEmbeddingProvider,
    CachedKnowledgeRetriever,
    EmbeddingProvider,
    FallbackKnowledgeRetriever,
    KnowledgeRetriever,
    LocalKnowledgeRetriever,
    OpenAIEmbeddingProvider,
    SqlAlchemyHybridRetriever,
    SqlAlchemyKnowledgeBase,
    knowledge_retriever_from_env,
)

__all__ = [
    "CachedEmbeddingProvider",
    "CachedKnowledgeRetriever",
    "EmbeddingProvider",
    "FallbackKnowledgeRetriever",
    "KnowledgeRetriever",
    "LocalKnowledgeRetriever",
    "OpenAIEmbeddingProvider",
    "SqlAlchemyHybridRetriever",
    "SqlAlchemyKnowledgeBase",
    "extract_code_retrieval_terms",
    "knowledge_retriever_from_env",
]
