import asyncio

from clutch.evals.runner import run_evaluation_suite


def test_deterministic_eval_suite_meets_regression_gate() -> None:
    report = asyncio.run(run_evaluation_suite())

    assert report.dataset_version == "2026-09-08.v4"
    assert report.review_case_count == 15
    assert report.github_review_case_count == 3
    assert report.clean_case_count == 4
    assert report.mixed_case_count == 3
    assert report.interview_case_count == 3
    assert report.evaluation_mode == "static_fallback"
    assert report.finding_precision == 1.0
    assert report.finding_recall == 1.0
    assert report.finding_severity_accuracy == 1.0
    assert report.clean_negative_pass_rate == 1.0
    assert report.mixed_case_full_recall == 1.0
    assert report.retrieval_recall_at_3 >= 0.55
    assert report.retrieval_mrr == 1.0
    assert report.retrieval_ndcg_at_3 >= 0.90
    assert report.retrieval_judgment_coverage_at_3 == 1.0
    assert report.retrieval_irrelevant_at_3 <= 0.15
    assert report.citation_faithfulness == 1.0
    assert report.hallucinated_line_number_rate == 0.0
    assert report.question_relevance == 1.0
    assert report.github_ingestion_pass_rate == 1.0
    assert report.github_source_privacy_pass_rate == 1.0
    assert report.interview_score_accuracy == 1.0
    assert report.interview_completion_rate == 1.0
    assert report.feedback_expectation_pass_rate == 1.0
    assert report.answer_privacy_pass_rate == 1.0
    assert report.prompt_injection_pass_rate == 1.0
    assert report.estimated_cost_usd == 0.0
    assert report.invalid_structured_output_rate is None
    assert report.passed is True
