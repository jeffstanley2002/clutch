"""Run the reproducible, zero-cost Clutch regression evaluation."""

import argparse
import asyncio
import json
from hashlib import sha256
from time import perf_counter

from langgraph.graph.state import CompiledStateGraph

from clutch.agent import build_review_graph
from clutch.evals.config import (
    DATASET_VERSION,
    FIXTURE_ROOT,
    MAX_RETRIEVAL_IRRELEVANT_AT_3,
    MIN_RETRIEVAL_JUDGMENT_COVERAGE_AT_3,
    MIN_RETRIEVAL_NDCG_AT_3,
    MIN_RETRIEVAL_RECALL_AT_3,
    MIN_SCORE,
)
from clutch.evals.fixtures import load_cases
from clutch.evals.metrics import ratio
from clutch.evals.models import (
    EvalCaseResult,
    EvalReport,
    GoldenGitHubReviewCase,
    GoldenInterviewCase,
    GoldenReviewCase,
    InjectionCaseResult,
    InterviewCaseResult,
    PromptInjectionCase,
)
from clutch.evals.review_metrics import evaluate_review_output
from clutch.github.contracts import FetchedRepository, GitHubFile, PullRequestDiff
from clutch.github.review import GitHubReviewService
from clutch.interview.repository import InMemoryInterviewRepository
from clutch.interview.service import InterviewService
from clutch.knowledge_base import CleanCodePrinciple
from clutch.knowledge_base.clean_code import SEED_CLEAN_CODE_PRINCIPLES
from clutch.llm import ModelRouter
from clutch.persistence.contracts import ReviewPersistenceRecord
from clutch.persistence.repository import InMemoryReviewRecorder
from clutch.rag import KnowledgeRetriever, LocalKnowledgeRetriever
from clutch.review.service import ReviewService
from clutch.schemas import (
    FindingCategory,
    GitHubReviewRequest,
    InterviewTurnRequest,
    ReviewRequest,
)


async def run_evaluation_suite() -> EvalReport:
    """Evaluate review, guardrail, interview, report, and privacy contracts."""

    golden_cases = load_cases(
        FIXTURE_ROOT / "golden_reviews.json",
        GoldenReviewCase,
    )
    injection_cases = load_cases(
        FIXTURE_ROOT / "prompt_injection_cases.json",
        PromptInjectionCase,
    )
    interview_cases = load_cases(
        FIXTURE_ROOT / "interview_cases.json",
        GoldenInterviewCase,
    )
    github_cases = load_cases(
        FIXTURE_ROOT / "github_reviews.json",
        GoldenGitHubReviewCase,
    )
    graph = build_review_graph(ModelRouter(primary=None))
    case_results = [
        await _evaluate_golden_case(case, graph=graph) for case in golden_cases
    ]
    github_case_results = [
        await _evaluate_github_case(case) for case in github_cases
    ]
    all_case_results = [*case_results, *github_case_results]
    injection_results = [
        await _evaluate_injection_case(case, graph=graph) for case in injection_cases
    ]
    interview_results = [
        await _evaluate_interview_case(case) for case in interview_cases
    ]

    true_positives = sum(result.true_positives for result in all_case_results)
    false_positives = sum(result.false_positives for result in all_case_results)
    false_negatives = sum(result.false_negatives for result in all_case_results)
    predicted = true_positives + false_positives
    expected = true_positives + false_negatives
    severity_matches = sum(result.severity_matches for result in all_case_results)
    retrieval_results = [
        result for result in all_case_results if result.retrieval_evaluated
    ]
    retrieved_relevant = sum(result.retrieval_relevant for result in retrieval_results)
    retrieved_total = sum(result.retrieval_returned for result in retrieval_results)
    relevant_total = sum(
        result.retrieval_relevant_total for result in retrieval_results
    )
    finding_count = sum(result.predicted_findings for result in all_case_results)
    hallucinated_lines = sum(
        result.hallucinated_line_numbers for result in all_case_results
    )
    clean_results = [result for result in all_case_results if result.kind == "clean"]
    mixed_results = [result for result in all_case_results if result.kind == "mixed"]

    finding_precision = ratio(true_positives, predicted)
    finding_recall = ratio(true_positives, expected)
    finding_severity_accuracy = ratio(severity_matches, expected)
    clean_negative_pass_rate = ratio(
        sum(
            result.predicted_findings == 0 and result.question_relevant
            for result in clean_results
        ),
        len(clean_results),
    )
    mixed_case_full_recall = ratio(
        sum(result.false_negatives == 0 for result in mixed_results),
        len(mixed_results),
    )
    retrieval_precision = ratio(retrieved_relevant, retrieved_total)
    retrieval_recall = ratio(retrieved_relevant, relevant_total)
    retrieval_mrr = ratio(
        sum(result.retrieval_reciprocal_rank for result in retrieval_results),
        len(retrieval_results),
    )
    retrieval_ndcg = ratio(
        sum(result.retrieval_ndcg for result in all_case_results),
        len(all_case_results),
    )
    all_retrieved = sum(result.retrieval_returned for result in all_case_results)
    retrieval_judgment_coverage = ratio(
        sum(result.retrieval_judged for result in all_case_results),
        all_retrieved,
    )
    retrieval_irrelevant = ratio(
        sum(result.retrieval_irrelevant for result in all_case_results),
        all_retrieved,
    )
    citation_faithfulness = ratio(
        sum(result.citation_faithful for result in all_case_results),
        len(all_case_results),
    )
    question_relevance = ratio(
        sum(result.question_relevant for result in all_case_results),
        len(all_case_results),
    )
    github_ingestion_pass_rate = ratio(
        sum(result.ingestion_matched is True for result in github_case_results),
        len(github_case_results),
    )
    github_source_privacy_pass_rate = ratio(
        sum(
            result.source_privacy_preserved is True
            for result in github_case_results
        ),
        len(github_case_results),
    )
    injection_pass_rate = ratio(
        sum(result.passed for result in injection_results),
        len(injection_results),
    )
    hallucinated_line_rate = ratio(hallucinated_lines, finding_count)
    interview_turn_count = sum(result.turn_count for result in interview_results)
    interview_score_accuracy = ratio(
        sum(result.exact_score_matches for result in interview_results),
        interview_turn_count,
    )
    interview_completion_rate = ratio(
        sum(result.completed for result in interview_results),
        len(interview_results),
    )
    feedback_expectation_pass_rate = ratio(
        sum(_feedback_expectations_met(result) for result in interview_results),
        len(interview_results),
    )
    answer_privacy_pass_rate = ratio(
        sum(result.answer_privacy_preserved for result in interview_results),
        len(interview_results),
    )

    gated_scores = [
        finding_precision,
        finding_recall,
        finding_severity_accuracy,
        clean_negative_pass_rate,
        mixed_case_full_recall,
        retrieval_mrr,
        citation_faithfulness,
        question_relevance,
        github_ingestion_pass_rate,
        github_source_privacy_pass_rate,
        injection_pass_rate,
        interview_score_accuracy,
        interview_completion_rate,
        feedback_expectation_pass_rate,
        answer_privacy_pass_rate,
    ]
    passed = (
        all(score >= MIN_SCORE for score in gated_scores)
        and retrieval_recall >= MIN_RETRIEVAL_RECALL_AT_3
        and retrieval_ndcg >= MIN_RETRIEVAL_NDCG_AT_3
        and retrieval_judgment_coverage >= MIN_RETRIEVAL_JUDGMENT_COVERAGE_AT_3
        and retrieval_irrelevant <= MAX_RETRIEVAL_IRRELEVANT_AT_3
        and hallucinated_line_rate == 0.0
    )
    return EvalReport(
        dataset_version=DATASET_VERSION,
        evaluation_mode="static_fallback",
        review_case_count=len(all_case_results),
        github_review_case_count=len(github_case_results),
        clean_case_count=len(clean_results),
        mixed_case_count=len(mixed_results),
        interview_case_count=len(interview_results),
        finding_precision=finding_precision,
        finding_recall=finding_recall,
        finding_severity_accuracy=finding_severity_accuracy,
        clean_negative_pass_rate=clean_negative_pass_rate,
        mixed_case_full_recall=mixed_case_full_recall,
        retrieval_precision_at_3=retrieval_precision,
        retrieval_recall_at_3=retrieval_recall,
        retrieval_mrr=retrieval_mrr,
        retrieval_ndcg_at_3=retrieval_ndcg,
        retrieval_judgment_coverage_at_3=retrieval_judgment_coverage,
        retrieval_irrelevant_at_3=retrieval_irrelevant,
        citation_faithfulness=citation_faithfulness,
        hallucinated_line_number_rate=hallucinated_line_rate,
        question_relevance=question_relevance,
        github_ingestion_pass_rate=github_ingestion_pass_rate,
        github_source_privacy_pass_rate=github_source_privacy_pass_rate,
        interview_score_accuracy=interview_score_accuracy,
        interview_completion_rate=interview_completion_rate,
        feedback_expectation_pass_rate=feedback_expectation_pass_rate,
        answer_privacy_pass_rate=answer_privacy_pass_rate,
        invalid_structured_output_rate=None,
        prompt_injection_pass_rate=injection_pass_rate,
        average_latency_ms=sum(result.latency_ms for result in all_case_results)
        / len(all_case_results),
        estimated_cost_usd=0.0,
        passed=passed,
        cases=all_case_results,
        injection_cases=injection_results,
        interview_cases=interview_results,
    )


async def _evaluate_golden_case(
    case: GoldenReviewCase, *, graph: CompiledStateGraph
) -> EvalCaseResult:
    started_at = perf_counter()
    state = await graph.ainvoke(
        {
            "request": ReviewRequest(
                code=case.code,
                role_context=case.role_context,
            )
        }
    )
    latency_ms = (perf_counter() - started_at) * 1_000
    return evaluate_review_output(
        case,
        findings=state["findings"],
        retrieved=state["retrieved_principles"][:3],
        questions=state["questions"],
        line_count=max(1, len(case.code.splitlines())),
        latency_ms=latency_ms,
    )


async def _evaluate_github_case(case: GoldenGitHubReviewCase) -> EvalCaseResult:
    recorder = InMemoryReviewRecorder()
    retriever = _CapturingRetriever(LocalKnowledgeRetriever())
    graph = build_review_graph(ModelRouter(primary=None), retriever=retriever)
    repository_files = [
        GitHubFile(
            path=file.path,
            sha=sha256(file.content.encode("utf-8")).hexdigest(),
            size=len(file.content.encode("utf-8")),
            content=file.content,
        )
        for file in case.files
    ]
    repository = FetchedRepository(
        owner="eval",
        repository=case.id,
        ref=case.ref,
        files=repository_files,
        total_bytes=sum(file.size for file in repository_files),
    )
    service = GitHubReviewService(
        _FixtureGitHubGateway(repository),
        ReviewService(graph=graph, recorder=recorder),
    )
    started_at = perf_counter()
    response = await service.review(
        GitHubReviewRequest(
            source_url=case.source_url,
            ref=case.ref,
            role_context=case.role_context,
            session_id=f"eval-github-{case.id}",
        )
    )
    latency_ms = (perf_counter() - started_at) * 1_000
    included_paths = [
        file.path for file in case.files if file.path.endswith((".py", ".pyi"))
    ]
    persisted_payload = " ".join(
        record.model_dump_json() for record in recorder.records
    )
    result = evaluate_review_output(
        case,
        findings=response.review.findings,
        retrieved=retriever.results[:3],
        questions=response.review.questions,
        line_count=recorder.records[0].line_count,
        latency_ms=latency_ms,
    )
    return result.model_copy(
        update={
            "source": "github_repository",
            "ingestion_matched": (
                response.ingestion.source_type == "repository"
                and response.ingestion.owner == "eval"
                and response.ingestion.repository == case.id
                and response.ingestion.ref == case.ref
                and response.ingestion.files_included == included_paths
                and not response.ingestion.truncated
            ),
            "source_privacy_preserved": (
                len(recorder.records) == 1
                and case.privacy_sentinel not in persisted_payload
            ),
        }
    )


class _CapturingRetriever:
    """Record request-scoped results while delegating to the real local ranker."""

    def __init__(self, delegate: KnowledgeRetriever) -> None:
        self._delegate = delegate
        self.results: list[CleanCodePrinciple] = []

    async def retrieve(
        self,
        query: str,
        *,
        categories: set[FindingCategory] | None = None,
        limit: int = 3,
    ) -> list[CleanCodePrinciple]:
        results = await self._delegate.retrieve(
            query,
            categories=categories,
            limit=limit,
        )
        self.results = list(results)
        return self.results


class _FixtureGitHubGateway:
    """Read-only gateway that drives the production coordinator without I/O."""

    def __init__(self, repository: FetchedRepository) -> None:
        self._repository = repository

    async def fetch_repo(
        self,
        repository_url: str,
        ref: str | None = None,
    ) -> FetchedRepository:
        return self._repository

    async def fetch_pr_diff(self, pull_request_url: str) -> PullRequestDiff:
        raise AssertionError("repository fixture unexpectedly requested a PR diff")


async def _evaluate_injection_case(
    case: PromptInjectionCase, *, graph: CompiledStateGraph
) -> InjectionCaseResult:
    state = await graph.ainvoke({"request": ReviewRequest(code=case.code)})
    behavior_text = " ".join(
        [
            *(
                f"{finding.message} {finding.explanation} {finding.suggestion}"
                for finding in state["findings"]
            ),
            *(
                f"{question.question} {question.intent}"
                for question in state["questions"]
            ),
        ]
    ).lower()
    prohibited_terms = [
        term for term in case.prohibited_output_terms if term.lower() in behavior_text
    ]
    known_citations = {
        principle.citation.source_id for principle in SEED_CLEAN_CODE_PRINCIPLES
    }
    observed_citations = {
        citation.source_id
        for finding in state["findings"]
        for citation in finding.citations
    }
    unknown_citations = sorted(observed_citations - known_citations)
    passed = (
        state["mode"] == "static_fallback"
        and not prohibited_terms
        and not unknown_citations
    )
    return InjectionCaseResult(
        case_id=case.id,
        passed=passed,
        prohibited_terms_found=prohibited_terms,
        unknown_citation_ids=unknown_citations,
    )


async def _evaluate_interview_case(
    case: GoldenInterviewCase,
) -> InterviewCaseResult:
    repository = InMemoryInterviewRepository()
    review_store = InMemoryReviewRecorder()
    service = InterviewService(repository, review_store)
    review_session_id = f"eval-review-{case.id}"
    await review_store.record_review(
        ReviewPersistenceRecord(
            review_session_id=review_session_id,
            external_session_id=None,
            code_sha256="0" * 64,
            language="python",
            line_count=1,
            role_context="backend intern",
            mode="static_fallback",
            confidence=1.0,
            latency_ms=0.0,
            findings=case.supporting_findings,
            questions=[],
        )
    )
    start = await service.run_turn(
        InterviewTurnRequest(
            review_session_id=review_session_id,
            profile_id=f"eval-profile-{case.id}",
            role_context="backend intern",
            questions=case.questions,
        )
    )
    session_id = start.interview_session_id
    observed_scores: list[int] = []
    completed = start.completed
    for answer in case.answers:
        response = await service.run_turn(
            InterviewTurnRequest(
                interview_session_id=session_id,
                answer=answer,
            )
        )
        if response.assessment is None:
            raise AssertionError("completed interview turn did not return assessment")
        observed_scores.append(response.assessment.score)
        completed = response.completed

    report = await service.generate_feedback(session_id)
    persisted_payload = json.dumps(
        [turn.model_dump(mode="json") for turn in repository.turns],
        sort_keys=True,
    )
    report_payload = report.model_dump_json()
    task_text = " ".join(report.recommended_tasks).lower()
    expected_finding_ids = {finding.finding_id for finding in case.supporting_findings}
    reported_finding_ids = {finding.id for finding in report.supporting_findings}
    return InterviewCaseResult(
        case_id=case.id,
        turn_count=len(case.answers),
        exact_score_matches=sum(
            observed == expected
            for observed, expected in zip(
                observed_scores,
                case.expected_scores,
                strict=True,
            )
        ),
        completed=completed,
        expected_strengths_met=(set(report.strengths) == set(case.expected_strengths)),
        expected_recurring_issues_met=(
            set(report.recurring_issues) == set(case.expected_recurring_issues)
        ),
        recommended_tasks_met=all(
            keyword.lower() in task_text for keyword in case.recommended_task_keywords
        ),
        readiness_matched=(
            case.readiness_keyword.lower() in report.interview_readiness_summary.lower()
        ),
        supporting_findings_matched=(reported_finding_ids == expected_finding_ids),
        answer_privacy_preserved=(
            case.privacy_sentinel not in persisted_payload
            and case.privacy_sentinel not in report_payload
        ),
    )


def _feedback_expectations_met(result: InterviewCaseResult) -> bool:
    return all(
        [
            result.expected_strengths_met,
            result.expected_recurring_issues_met,
            result.recommended_tasks_met,
            result.readiness_matched,
            result.supporting_findings_matched,
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Print compact JSON instead of indented output.",
    )
    args = parser.parse_args()
    report = asyncio.run(run_evaluation_suite())
    print(report.model_dump_json(indent=None if args.compact else 2))
    if not report.passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
