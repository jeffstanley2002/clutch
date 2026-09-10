"""Run a small, spend-capped live-model evaluation without exposing source."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
from collections.abc import Mapping, Sequence
from time import perf_counter
from typing import Protocol, TypeVar, cast

from dotenv import load_dotenv
from langgraph.graph.state import CompiledStateGraph

from clutch.agent import build_review_graph
from clutch.evals.config import (
    DATASET_VERSION,
    FIXTURE_ROOT,
    MIN_CITATION_SUPPORT,
    MIN_CITATION_VALIDITY,
    MIN_FINDING_PRECISION,
    MIN_FINDING_RECALL,
    MIN_INTERVIEW_SCORE_WITHIN_ONE,
    MIN_PROMPT_INJECTION_PASS_RATE,
    MIN_QUESTION_RELEVANCE,
)
from clutch.evals.fixtures import load_cases
from clutch.evals.metrics import ratio
from clutch.evals.models import (
    GoldenInterviewCase,
    GoldenReviewCase,
    LiveModelCaseResult,
    LiveModelEvalReport,
    LiveModelInjectionCaseResult,
    LiveModelInterviewCaseResult,
    LiveStageMetrics,
    PromptInjectionCase,
)
from clutch.evals.review_metrics import evaluate_review_output
from clutch.interview.repository import InMemoryInterviewRepository
from clutch.interview.service import InterviewService
from clutch.knowledge_base.clean_code import SEED_CLEAN_CODE_PRINCIPLES
from clutch.llm.providers import (
    DEFAULT_OPENAI_MODEL,
    ModelRouter,
    OpenAIProvider,
    ReviewModelUnavailable,
    ReviewProvider,
)
from clutch.llm.spend import InMemorySpendGuard, SpendGuard
from clutch.observability import NullObservability
from clutch.persistence.contracts import ReviewPersistenceRecord
from clutch.persistence.repository import InMemoryReviewRecorder
from clutch.rag import LocalKnowledgeRetriever
from clutch.schemas import (
    InterviewTurnRequest,
    ReviewRequest,
    SafeFailureCategory,
    StageProvenance,
)

LIVE_REVIEW_CASE_IDS = (
    "bare-except",
    "unsafe-sql",
    "clean-pure-function",
    "clean-parameterized-sql",
    "mixed-boundary-state",
    "mixed-errors-and-sql",
)
LIVE_INJECTION_CASE_IDS = (
    "comment-instruction",
    "tool-call-string",
    "readme-style-exfiltration",
)
LIVE_INTERVIEW_CASE_IDS = (
    "weak-repeated-gaps",
    "strong-complete-reasoning",
    "mixed-answer-quality",
)
DEFAULT_LIVE_EVAL_MAX_USD = 0.50
DEFAULT_LIVE_EVAL_PER_REQUEST_USD = 0.10


class _IdentifiedCase(Protocol):
    id: str


_CaseT = TypeVar("_CaseT", bound=_IdentifiedCase)


async def evaluate_live_model(
    provider: ReviewProvider,
    *,
    model_name: str,
    configured_max_cost_usd: float = DEFAULT_LIVE_EVAL_MAX_USD,
    spend_guard: SpendGuard | None = None,
    review_case_ids: Sequence[str] = LIVE_REVIEW_CASE_IDS,
    injection_case_ids: Sequence[str] = LIVE_INJECTION_CASE_IDS,
    interview_case_ids: Sequence[str] = LIVE_INTERVIEW_CASE_IDS,
) -> LiveModelEvalReport:
    """Evaluate one provider through the production graph and local retrieval."""

    review_cases = _select_cases(
        load_cases(FIXTURE_ROOT / "golden_reviews.json", GoldenReviewCase),
        review_case_ids,
    )
    injection_cases = _select_cases(
        load_cases(
            FIXTURE_ROOT / "prompt_injection_cases.json",
            PromptInjectionCase,
        ),
        injection_case_ids,
    )
    interview_cases = _select_cases(
        load_cases(FIXTURE_ROOT / "interview_cases.json", GoldenInterviewCase),
        interview_case_ids,
    )
    router = ModelRouter(primary=provider)
    graph = build_review_graph(
        router,
        retriever=LocalKnowledgeRetriever(),
    )

    case_results: list[LiveModelCaseResult] = []
    for case in review_cases:
        started_at = perf_counter()
        state = await graph.ainvoke(
            {
                "request": ReviewRequest(
                    code=case.code,
                    role_context=case.role_context,
                )
            }
        )
        _require_model_backed_state(state)
        latency_ms = (perf_counter() - started_at) * 1_000
        quality = evaluate_review_output(
            case,
            findings=state["findings"],
            retrieved=state["retrieved_principles"],
            questions=state["questions"],
            line_count=max(1, len(case.code.splitlines())),
            latency_ms=latency_ms,
            require_id_prefix=False,
        )
        stages = _state_stages(state)
        case_results.append(
            LiveModelCaseResult(
                quality=quality,
                mode=state["mode"],
                model_name=state.get("model_name"),
                input_tokens=sum(stage.input_tokens or 0 for stage in stages),
                output_tokens=sum(stage.output_tokens or 0 for stage in stages),
                attempt_count=sum(stage.attempt_count for stage in stages),
                validation_failure_count=sum(
                    stage.validation_failure_count for stage in stages
                ),
                stages=stages,
            )
        )

    injection_results = [
        await _evaluate_injection_case(case, graph=graph)
        for case in injection_cases
    ]
    interview_results = [
        await _evaluate_live_interview_case(case, router=router)
        for case in interview_cases
    ]
    total_runs = len(case_results) + len(injection_results)
    attempts = (
        sum(result.attempt_count for result in case_results)
        + sum(result.attempt_count for result in injection_results)
        + sum(result.attempt_count for result in interview_results)
    )
    validation_failures = (
        sum(result.validation_failure_count for result in case_results)
        + sum(result.validation_failure_count for result in injection_results)
        + sum(result.validation_failure_count for result in interview_results)
    )
    true_positives = sum(result.quality.true_positives for result in case_results)
    false_positives = sum(result.quality.false_positives for result in case_results)
    false_negatives = sum(result.quality.false_negatives for result in case_results)
    expected_findings = true_positives + false_negatives
    predicted_findings = true_positives + false_positives
    severity_matches = sum(
        result.quality.severity_matches for result in case_results
    )
    finding_count = sum(
        result.quality.predicted_findings for result in case_results
    )
    clean_results = [
        result for result in case_results if result.quality.kind == "clean"
    ]
    mixed_results = [
        result for result in case_results if result.quality.kind == "mixed"
    ]
    latencies = [
        *(result.quality.latency_ms for result in case_results),
        *(result.latency_ms for result in injection_results),
        *(result.latency_ms for result in interview_results),
    ]
    charged_cost = 0.0
    if spend_guard is not None:
        charged_cost = (await spend_guard.metrics()).reserved_usd

    interview_turn_count = sum(result.turn_count for result in interview_results)
    finding_precision = ratio(true_positives, predicted_findings)
    finding_recall = ratio(true_positives, expected_findings)
    finding_accuracy = ratio(
        true_positives,
        true_positives + false_positives + false_negatives,
    )
    citation_validity = ratio(
        sum(result.quality.citation_valid for result in case_results),
        len(case_results),
    )
    citation_support = ratio(
        sum(result.quality.citation_supported for result in case_results),
        len(case_results),
    )
    question_relevance = ratio(
        sum(result.quality.question_relevant for result in case_results),
        len(case_results),
    )
    interview_score_within_one = ratio(
        sum(result.within_one_score_matches for result in interview_results),
        interview_turn_count,
    )
    prompt_injection_pass_rate = ratio(
        sum(result.passed for result in injection_results),
        len(injection_results),
    )
    hallucinated_line_number_rate = ratio(
        sum(result.quality.hallucinated_line_numbers for result in case_results),
        finding_count,
    )
    interview_citation_validity = ratio(
        sum(result.citation_valid for result in interview_results),
        len(interview_results),
    )
    answer_privacy_pass_rate = ratio(
        sum(result.answer_privacy_preserved for result in interview_results),
        len(interview_results),
    )
    model_mode_rate = ratio(
        sum(result.mode == "model" for result in case_results)
        + sum(result.mode == "model" for result in injection_results),
        total_runs,
    )
    interview_model_backed_rate = ratio(
        sum(result.model_backed_turns for result in interview_results),
        interview_turn_count,
    )
    all_stages = [
        *(stage for result in case_results for stage in result.stages),
        *(stage for result in injection_results for stage in result.stages),
        *(stage for result in interview_results for stage in result.stages),
    ]
    passed = (
        finding_precision >= MIN_FINDING_PRECISION
        and finding_recall >= MIN_FINDING_RECALL
        and citation_validity >= MIN_CITATION_VALIDITY
        and citation_support >= MIN_CITATION_SUPPORT
        and question_relevance >= MIN_QUESTION_RELEVANCE
        and prompt_injection_pass_rate >= MIN_PROMPT_INJECTION_PASS_RATE
        and hallucinated_line_number_rate == 0.0
        and model_mode_rate == 1.0
        and (
            not interview_results
            or (
                interview_score_within_one >= MIN_INTERVIEW_SCORE_WITHIN_ONE
                and interview_model_backed_rate == 1.0
                and interview_citation_validity == 1.0
                and answer_privacy_pass_rate == 1.0
            )
        )
        and validation_failures == 0
    )

    return LiveModelEvalReport(
        dataset_version=DATASET_VERSION,
        available=True,
        complete=True,
        model_name=model_name,
        configured_max_cost_usd=configured_max_cost_usd,
        selected_review_case_ids=list(review_case_ids),
        selected_injection_case_ids=list(injection_case_ids),
        selected_interview_case_ids=list(interview_case_ids),
        review_case_count=len(case_results),
        injection_case_count=len(injection_results),
        interview_case_count=len(interview_results),
        model_mode_rate=model_mode_rate,
        validation_failure_attempt_rate=ratio(validation_failures, attempts),
        finding_precision=finding_precision,
        finding_recall=finding_recall,
        finding_accuracy=finding_accuracy,
        finding_severity_accuracy=ratio(severity_matches, expected_findings),
        clean_negative_pass_rate=ratio(
            sum(result.quality.predicted_findings == 0 for result in clean_results),
            len(clean_results),
        ),
        mixed_case_full_recall=ratio(
            sum(result.quality.false_negatives == 0 for result in mixed_results),
            len(mixed_results),
        ),
        citation_validity=citation_validity,
        citation_support=citation_support,
        question_relevance=question_relevance,
        interview_score_accuracy=ratio(
            sum(result.exact_score_matches for result in interview_results),
            interview_turn_count,
        ),
        interview_score_within_one=interview_score_within_one,
        interview_model_backed_rate=interview_model_backed_rate,
        interview_citation_validity=interview_citation_validity,
        answer_privacy_pass_rate=answer_privacy_pass_rate,
        hallucinated_line_number_rate=hallucinated_line_number_rate,
        prompt_injection_pass_rate=prompt_injection_pass_rate,
        average_latency_ms=ratio(sum(latencies), len(latencies)),
        p95_latency_ms=_p95(latencies),
        total_input_tokens=sum(
            result.input_tokens or 0 for result in case_results
        )
        + sum(result.input_tokens or 0 for result in injection_results)
        + sum(result.input_tokens for result in interview_results),
        total_output_tokens=sum(
            result.output_tokens or 0 for result in case_results
        )
        + sum(result.output_tokens or 0 for result in injection_results)
        + sum(result.output_tokens for result in interview_results),
        charged_cost_usd=charged_cost,
        cost_per_review_usd=ratio(charged_cost, len(case_results)),
        schema_validation_failures=validation_failures,
        stage_metrics=_aggregate_stage_metrics(all_stages),
        passed=passed,
        cases=case_results,
        injection_cases=injection_results,
        interview_cases=interview_results,
    )


async def run_live_model_evaluation() -> LiveModelEvalReport:
    """Build a bounded OpenAI provider from environment configuration."""

    load_dotenv()
    model_name = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL).strip()
    max_cost = _positive_env(
        "CLUTCH_LIVE_EVAL_MAX_USD",
        DEFAULT_LIVE_EVAL_MAX_USD,
    )
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return LiveModelEvalReport(
            dataset_version=DATASET_VERSION,
            available=False,
            unavailable_reason="OPENAI_API_KEY is not configured",
            model_name=model_name,
            configured_max_cost_usd=max_cost,
            selected_review_case_ids=list(LIVE_REVIEW_CASE_IDS),
            selected_injection_case_ids=list(LIVE_INJECTION_CASE_IDS),
            selected_interview_case_ids=list(LIVE_INTERVIEW_CASE_IDS),
        )

    per_request = min(
        _positive_env(
            "CLUTCH_LIVE_EVAL_PER_REQUEST_USD",
            DEFAULT_LIVE_EVAL_PER_REQUEST_USD,
        ),
        max_cost,
    )
    spend_guard = InMemorySpendGuard(
        per_request_limit_usd=per_request,
        daily_limit_usd=max_cost,
    )
    provider = OpenAIProvider(
        api_key=api_key,
        model=model_name,
        spend_guard=spend_guard,
    )
    try:
        try:
            return await evaluate_live_model(
                provider,
                model_name=model_name,
                configured_max_cost_usd=max_cost,
                spend_guard=spend_guard,
            )
        except ReviewModelUnavailable as exc:
            metrics = await spend_guard.metrics()
            return LiveModelEvalReport(
                dataset_version=DATASET_VERSION,
                available=True,
                complete=False,
                unavailable_reason=f"live model path failed: {exc.failure_category}",
                model_name=model_name,
                configured_max_cost_usd=max_cost,
                selected_review_case_ids=list(LIVE_REVIEW_CASE_IDS),
                selected_injection_case_ids=list(LIVE_INJECTION_CASE_IDS),
                selected_interview_case_ids=list(LIVE_INTERVIEW_CASE_IDS),
                charged_cost_usd=metrics.reserved_usd,
            )
    finally:
        await spend_guard.aclose()


async def _evaluate_injection_case(
    case: PromptInjectionCase,
    *,
    graph: CompiledStateGraph,
) -> LiveModelInjectionCaseResult:
    started_at = perf_counter()
    state = await graph.ainvoke({"request": ReviewRequest(code=case.code)})
    _require_model_backed_state(state)
    latency_ms = (perf_counter() - started_at) * 1_000
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
    stages = _state_stages(state)
    return LiveModelInjectionCaseResult(
        case_id=case.id,
        mode=state["mode"],
        passed=not prohibited_terms and not unknown_citations,
        prohibited_terms_found=prohibited_terms,
        unknown_citation_ids=unknown_citations,
        latency_ms=latency_ms,
        model_name=state.get("model_name"),
        input_tokens=sum(stage.input_tokens or 0 for stage in stages),
        output_tokens=sum(stage.output_tokens or 0 for stage in stages),
        attempt_count=sum(stage.attempt_count for stage in stages),
        validation_failure_count=sum(
            stage.validation_failure_count for stage in stages
        ),
        stages=stages,
    )


async def _evaluate_live_interview_case(
    case: GoldenInterviewCase,
    *,
    router: ModelRouter,
) -> LiveModelInterviewCaseResult:
    """Run real structured assessment while retaining only privacy-safe evidence."""

    repository = InMemoryInterviewRepository()
    review_store = InMemoryReviewRecorder()
    service = InterviewService(
        repository,
        review_store,
        model_router=router,
        retriever=LocalKnowledgeRetriever(),
        observability=NullObservability(),
    )
    review_session_id = f"live-eval-review-{case.id}"
    await review_store.record_review(
        ReviewPersistenceRecord(
            review_session_id=review_session_id,
            code_sha256="0" * 64,
            language="python",
            line_count=1,
            role_context="backend intern",
            mode="model",
            confidence=1.0,
            latency_ms=0.0,
            findings=case.supporting_findings,
        )
    )
    started = await service.run_turn(
        InterviewTurnRequest(
            review_session_id=review_session_id,
            profile_id=f"live-eval-profile-{case.id}",
            role_context="backend intern",
            questions=case.questions,
        )
    )
    started_at = perf_counter()
    observed_scores: list[int] = []
    stages: list[StageProvenance] = []
    citation_ids: set[str] = set()
    model_backed_turns = 0
    for answer in case.answers:
        response = await service.run_turn(
            InterviewTurnRequest(
                interview_session_id=started.interview_session_id,
                answer=answer,
            )
        )
        if response.assessment is None:
            raise ReviewModelUnavailable(
                failure_reason="provider_error",
                failure_category="provider_error",
            )
        observed_scores.append(response.assessment.score)
        stages.extend(response.provenance)
        citation_ids.update(
            citation.source_id for citation in response.assessment.citations
        )
        if response.assessment.origin == "ai_generated":
            model_backed_turns += 1
        else:
            provenance = response.assessment.provenance
            raise ReviewModelUnavailable(
                failure_reason=(
                    provenance.failure_category
                    if provenance is not None and provenance.failure_category
                    else "provider_error"
                ),
                failure_category=(
                    provenance.failure_category
                    if provenance is not None and provenance.failure_category
                    else "provider_error"
                ),
            )
    latency_ms = (perf_counter() - started_at) * 1_000
    persisted_payload = json.dumps(
        [turn.model_dump(mode="json") for turn in repository.turns],
        sort_keys=True,
    )
    known_citations = {
        principle.citation.source_id for principle in SEED_CLEAN_CODE_PRINCIPLES
    }
    assessment_stages = [
        stage for stage in stages if stage.stage == "interview_assessment"
    ]
    return LiveModelInterviewCaseResult(
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
        within_one_score_matches=sum(
            abs(observed - expected) <= 1
            for observed, expected in zip(
                observed_scores,
                case.expected_scores,
                strict=True,
            )
        ),
        model_backed_turns=model_backed_turns,
        citation_valid=bool(citation_ids) and citation_ids <= known_citations,
        answer_privacy_preserved=case.privacy_sentinel not in persisted_payload,
        latency_ms=latency_ms,
        input_tokens=sum(stage.input_tokens or 0 for stage in assessment_stages),
        output_tokens=sum(stage.output_tokens or 0 for stage in assessment_stages),
        attempt_count=sum(stage.attempt_count for stage in assessment_stages),
        validation_failure_count=sum(
            stage.validation_failure_count for stage in assessment_stages
        ),
        stages=stages,
    )


def _state_stages(state: Mapping[str, object]) -> list[StageProvenance]:
    return [
        stage
        for key in (
            "retrieval_provenance",
            "review_provenance",
            "question_provenance",
        )
        if isinstance((stage := state.get(key)), StageProvenance)
    ]


def _select_cases(
    cases: Sequence[_CaseT],
    selected_ids: Sequence[str],
) -> list[_CaseT]:
    cases_by_id = {case.id: case for case in cases}
    missing = set(selected_ids) - set(cases_by_id)
    if missing:
        raise ValueError("unknown live eval cases: " + ", ".join(sorted(missing)))
    return [cases_by_id[case_id] for case_id in selected_ids]


def _require_model_backed_state(state: Mapping[str, object]) -> None:
    """Prevent a credentialed baseline from silently measuring a fallback."""

    review_stage = state.get("review_provenance")
    if state.get("mode") != "model":
        observed = getattr(review_stage, "failure_category", None)
        failure_category = observed if isinstance(observed, str) else "provider_error"
        raise ReviewModelUnavailable(
            failure_reason=failure_category,
            failure_category=cast(SafeFailureCategory, failure_category),
        )
    findings = state.get("findings")
    question_stage = state.get("question_provenance")
    if isinstance(findings, list) and findings and (
        not isinstance(question_stage, StageProvenance)
        or question_stage.origin != "ai_generated"
    ):
        observed = getattr(question_stage, "failure_category", None)
        failure_category = observed if isinstance(observed, str) else "provider_error"
        raise ReviewModelUnavailable(
            failure_reason=failure_category,
            failure_category=cast(SafeFailureCategory, failure_category),
        )


def _positive_env(name: str, default: float) -> float:
    raw = os.getenv(name, str(default))
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return value


def _p95(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * 0.95) - 1)
    return ordered[index]


def _aggregate_stage_metrics(
    stages: Sequence[StageProvenance],
) -> dict[str, LiveStageMetrics]:
    grouped: dict[str, list[StageProvenance]] = {}
    for stage in stages:
        grouped.setdefault(stage.stage, []).append(stage)
    return {
        name: LiveStageMetrics(
            call_count=len(stage_group),
            average_latency_ms=ratio(
                sum(stage.latency_ms for stage in stage_group),
                len(stage_group),
            ),
            p95_latency_ms=_p95([stage.latency_ms for stage in stage_group]),
            input_tokens=sum(stage.input_tokens or 0 for stage in stage_group),
            output_tokens=sum(stage.output_tokens or 0 for stage in stage_group),
            estimated_cost_usd=sum(
                stage.estimated_cost_usd for stage in stage_group
            ),
        )
        for name, stage_group in sorted(grouped.items())
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = asyncio.run(run_live_model_evaluation())
    print(
        report.model_dump_json(
            indent=None if args.compact else 2,
            exclude_none=args.compact,
        )
    )
    if not report.available:
        raise SystemExit(2)
    if not report.complete or not report.passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
