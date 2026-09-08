"""Compare retrieval strategies on the same bounded queries and judgments."""

from __future__ import annotations

import argparse
import asyncio
import os
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import PurePosixPath
from time import perf_counter

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncEngine

from clutch.evals.config import (
    DATASET_VERSION,
    FIXTURE_ROOT,
    MAX_RETRIEVAL_IRRELEVANT_AT_3,
    MIN_RETRIEVAL_NDCG_AT_3,
    MIN_RETRIEVAL_RECALL_AT_3,
)
from clutch.evals.fixtures import load_cases
from clutch.evals.metrics import ndcg_at_k, ratio
from clutch.evals.models import (
    GoldenGitHubReviewCase,
    GoldenReviewCase,
    RetrievalComparisonCaseResult,
    RetrievalComparisonReport,
    RetrievalStrategyReport,
    ReviewExpectations,
)
from clutch.github.review import (
    PYTHON_EXTENSIONS,
    compose_github_review_source,
)
from clutch.knowledge_base.clean_code import SEED_CLEAN_CODE_PRINCIPLES
from clutch.llm.spend import conservative_token_estimate, embedding_cost_usd
from clutch.parsing import parse_python_code
from clutch.persistence import create_session_factory
from clutch.persistence.database import database_url_from_env
from clutch.rag import (
    EmbeddingProvider,
    KnowledgeRetriever,
    LocalKnowledgeRetriever,
    OpenAIEmbeddingProvider,
    RetrievalQuery,
    SqlAlchemyHybridRetriever,
    SqlAlchemyVectorRetriever,
    build_retrieval_query,
)
from clutch.review.static import run_static_review
from clutch.schemas import ReviewRequest

EXPECTED_STRATEGIES = frozenset(
    {
        "local_lexical",
        "postgres_lexical",
        "postgres_vector",
        "postgres_hybrid",
    }
)


@dataclass(frozen=True)
class _BenchmarkCase:
    expectations: ReviewExpectations
    query: RetrievalQuery


class _MemoizedEmbeddingProvider:
    """Avoid paying twice for a query shared by vector and hybrid runs."""

    def __init__(self, delegate: EmbeddingProvider) -> None:
        self._delegate = delegate
        self._cache: dict[str, list[float]] = {}

    async def embed(self, text: str) -> list[float]:
        cached = self._cache.get(text)
        if cached is not None:
            return cached
        embedding = await self._delegate.embed(text)
        self._cache[text] = embedding
        return embedding


async def evaluate_retrievers(
    retrievers: Mapping[str, KnowledgeRetriever],
    *,
    unavailable_strategies: Mapping[str, str] | None = None,
    estimated_costs_usd: Mapping[str, float] | None = None,
) -> RetrievalComparisonReport:
    """Evaluate configured retrievers without emitting source or query text."""

    benchmark_cases = _build_benchmark_cases()
    costs = estimated_costs_usd or {}
    strategy_reports = [
        await _evaluate_strategy(
            strategy,
            retriever,
            benchmark_cases,
            estimated_cost_usd=costs.get(strategy, 0.0),
        )
        for strategy, retriever in retrievers.items()
    ]
    unavailable = dict(unavailable_strategies or {})
    available_names = set(retrievers)
    return RetrievalComparisonReport(
        dataset_version=DATASET_VERSION,
        corpus_size=len(SEED_CLEAN_CODE_PRINCIPLES),
        k=3,
        all_strategies_available=(available_names == EXPECTED_STRATEGIES),
        unavailable_strategies=unavailable,
        strategies=strategy_reports,
    )


async def run_retrieval_comparison() -> RetrievalComparisonReport:
    """Build environment-backed strategies and release database resources."""

    retrievers, unavailable, costs, engine = _retrievers_from_env()
    try:
        return await evaluate_retrievers(
            retrievers,
            unavailable_strategies=unavailable,
            estimated_costs_usd=costs,
        )
    finally:
        if engine is not None:
            await engine.dispose()


async def _evaluate_strategy(
    strategy: str,
    retriever: KnowledgeRetriever,
    benchmark_cases: list[_BenchmarkCase],
    *,
    estimated_cost_usd: float,
) -> RetrievalStrategyReport:
    case_results: list[RetrievalComparisonCaseResult] = []
    for benchmark in benchmark_cases:
        query = benchmark.query
        started_at = perf_counter()
        retrieved = await retriever.retrieve(
            query.text,
            categories=(set(query.categories) if query.categories else None),
            limit=3,
        )
        latency_ms = (perf_counter() - started_at) * 1_000
        retrieved_ids = [item.citation.source_id for item in retrieved[:3]]
        judgments = benchmark.expectations.retrieval_judgments
        grades = [judgments.get(source_id, 0) for source_id in retrieved_ids]
        relevant_ranks = [
            rank for rank, grade in enumerate(grades, start=1) if grade >= 2
        ]
        case_results.append(
            RetrievalComparisonCaseResult(
                case_id=benchmark.expectations.id,
                query_sha256=sha256(query.text.encode("utf-8")).hexdigest(),
                categories=sorted(query.categories or []),
                retrieved_ids=retrieved_ids,
                relevant_retrieved=sum(grade >= 2 for grade in grades),
                relevant_total=sum(grade >= 2 for grade in judgments.values()),
                judged_retrieved=sum(
                    source_id in judgments for source_id in retrieved_ids
                ),
                irrelevant_retrieved=sum(grade == 0 for grade in grades),
                reciprocal_rank=(
                    1.0 / min(relevant_ranks) if relevant_ranks else 0.0
                ),
                ndcg_at_3=ndcg_at_k(grades, list(judgments.values()), k=3),
                latency_ms=latency_ms,
            )
        )

    evaluated = [result for result in case_results if result.relevant_total > 0]
    relevant_retrieved = sum(result.relevant_retrieved for result in evaluated)
    returned_evaluated = sum(len(result.retrieved_ids) for result in evaluated)
    relevant_total = sum(result.relevant_total for result in evaluated)
    all_returned = sum(len(result.retrieved_ids) for result in case_results)
    recall = ratio(relevant_retrieved, relevant_total)
    ndcg = ratio(sum(result.ndcg_at_3 for result in case_results), len(case_results))
    judgment_coverage = ratio(
        sum(result.judged_retrieved for result in case_results),
        all_returned,
    )
    irrelevant = ratio(
        sum(result.irrelevant_retrieved for result in case_results),
        all_returned,
    )
    mrr = ratio(sum(result.reciprocal_rank for result in evaluated), len(evaluated))
    return RetrievalStrategyReport(
        strategy=strategy,
        case_count=len(case_results),
        precision_at_3=ratio(relevant_retrieved, returned_evaluated),
        recall_at_3=recall,
        mrr=mrr,
        ndcg_at_3=ndcg,
        judgment_coverage_at_3=judgment_coverage,
        irrelevant_at_3=irrelevant,
        average_latency_ms=ratio(
            sum(result.latency_ms for result in case_results),
            len(case_results),
        ),
        estimated_query_cost_usd=estimated_cost_usd,
        meets_current_gate=(
            recall >= MIN_RETRIEVAL_RECALL_AT_3
            and mrr == 1.0
            and ndcg >= MIN_RETRIEVAL_NDCG_AT_3
            and judgment_coverage == 1.0
            and irrelevant <= MAX_RETRIEVAL_IRRELEVANT_AT_3
        ),
        cases=case_results,
    )


def _build_benchmark_cases() -> list[_BenchmarkCase]:
    pasted_cases = load_cases(
        FIXTURE_ROOT / "golden_reviews.json",
        GoldenReviewCase,
    )
    github_cases = load_cases(
        FIXTURE_ROOT / "github_reviews.json",
        GoldenGitHubReviewCase,
    )
    benchmark_cases = [
        _benchmark_case(
            case,
            ReviewRequest(code=case.code, role_context=case.role_context),
        )
        for case in pasted_cases
    ]
    for case in github_cases:
        sources = [
            (file.path, file.content)
            for file in case.files
            if PurePosixPath(file.path).suffix.lower() in PYTHON_EXTENSIONS
        ]
        code, _ = compose_github_review_source(sources)
        benchmark_cases.append(
            _benchmark_case(
                case,
                ReviewRequest(code=code, role_context=case.role_context),
            )
        )
    return benchmark_cases


def _benchmark_case(
    expectations: ReviewExpectations,
    request: ReviewRequest,
) -> _BenchmarkCase:
    findings = run_static_review(
        request,
        parsed_code=parse_python_code(request.code),
    )
    return _BenchmarkCase(
        expectations=expectations,
        query=build_retrieval_query(request, findings),
    )


def _retrievers_from_env() -> tuple[
    dict[str, KnowledgeRetriever],
    dict[str, str],
    dict[str, float],
    AsyncEngine | None,
]:
    load_dotenv()
    retrievers: dict[str, KnowledgeRetriever] = {
        "local_lexical": LocalKnowledgeRetriever()
    }
    unavailable: dict[str, str] = {}
    costs: dict[str, float] = {"local_lexical": 0.0}
    database_url = database_url_from_env()
    if not database_url:
        reason = "DATABASE_URL is not configured"
        unavailable.update(
            {
                "postgres_lexical": reason,
                "postgres_vector": reason,
                "postgres_hybrid": reason,
            }
        )
        return retrievers, unavailable, costs, None

    engine, session_factory = create_session_factory(database_url)
    retrievers["postgres_lexical"] = SqlAlchemyHybridRetriever(session_factory)
    costs["postgres_lexical"] = 0.0
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        reason = "OPENAI_API_KEY is not configured"
        unavailable.update(
            {
                "postgres_vector": reason,
                "postgres_hybrid": reason,
            }
        )
        return retrievers, unavailable, costs, engine

    model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    embedding_provider = _MemoizedEmbeddingProvider(
        OpenAIEmbeddingProvider(api_key=api_key, model=model)
    )
    retrievers["postgres_vector"] = SqlAlchemyVectorRetriever(
        session_factory,
        embedding_provider=embedding_provider,
    )
    retrievers["postgres_hybrid"] = SqlAlchemyHybridRetriever(
        session_factory,
        embedding_provider=embedding_provider,
    )
    estimated_query_cost = sum(
        embedding_cost_usd(
            model,
            input_tokens=conservative_token_estimate(case.query.text),
        )
        for case in _build_benchmark_cases()
    )
    costs["postgres_vector"] = estimated_query_cost
    costs["postgres_hybrid"] = estimated_query_cost
    return retrievers, unavailable, costs, engine


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Print compact JSON instead of indented output.",
    )
    parser.add_argument(
        "--require-all",
        action="store_true",
        help="Fail when PostgreSQL, vector-only, or hybrid is unavailable.",
    )
    args = parser.parse_args()
    report = asyncio.run(run_retrieval_comparison())
    print(report.model_dump_json(indent=None if args.compact else 2))
    if any(not strategy.meets_current_gate for strategy in report.strategies):
        raise SystemExit(1)
    if args.require_all and not report.all_strategies_available:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
