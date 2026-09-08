import asyncio

from clutch.evals.retrieval_comparison import evaluate_retrievers
from clutch.rag import LocalKnowledgeRetriever


def test_local_retrieval_comparison_matches_v5_baseline_without_raw_text() -> None:
    report = asyncio.run(
        evaluate_retrievers(
            {"local_lexical": LocalKnowledgeRetriever()},
            unavailable_strategies={
                "postgres_lexical": "not configured",
                "postgres_vector": "not configured",
                "postgres_hybrid": "not configured",
            },
        )
    )

    assert report.dataset_version == "2026-09-08.v5"
    assert report.corpus_size == 100
    assert report.all_strategies_available is False
    assert set(report.unavailable_strategies) == {
        "postgres_lexical",
        "postgres_vector",
        "postgres_hybrid",
    }
    strategy = report.strategies[0]
    assert strategy.strategy == "local_lexical"
    assert strategy.case_count == 15
    assert strategy.precision_at_3 == 0.7857142857142857
    assert strategy.recall_at_3 == 0.559322033898305
    assert strategy.mrr == 1.0
    assert strategy.ndcg_at_3 == 0.9344318390318389
    assert strategy.judgment_coverage_at_3 == 1.0
    assert strategy.irrelevant_at_3 == 0.044444444444444446
    assert strategy.estimated_query_cost_usd == 0.0
    assert strategy.meets_current_gate is True

    serialized = report.model_dump_json()
    assert "EVAL_GITHUB_STATE_SQL_SENTINEL" not in serialized
    assert "SELECT * FROM users" not in serialized
    assert all(len(case.query_sha256) == 64 for case in strategy.cases)
