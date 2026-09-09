"""Run a small, spend-capped live-model evaluation without exposing source."""

from __future__ import annotations

import argparse
import asyncio
import math
import os
from collections.abc import Sequence
from time import perf_counter
from typing import Protocol, TypeVar

from dotenv import load_dotenv
from langgraph.graph.state import CompiledStateGraph

from clutch.agent import build_review_graph
from clutch.evals.config import DATASET_VERSION, FIXTURE_ROOT
from clutch.evals.fixtures import load_cases
from clutch.evals.metrics import ratio
from clutch.evals.models import (
    GoldenReviewCase,
    LiveModelCaseResult,
    LiveModelEvalReport,
    LiveModelInjectionCaseResult,
    PromptInjectionCase,
)
from clutch.evals.review_metrics import evaluate_review_output
from clutch.knowledge_base.clean_code import SEED_CLEAN_CODE_PRINCIPLES
from clutch.llm.providers import (
    DEFAULT_OPENAI_MODEL,
    ModelRouter,
    OpenAIProvider,
    ReviewProvider,
)
from clutch.llm.spend import InMemorySpendGuard, SpendGuard
from clutch.rag import LocalKnowledgeRetriever
from clutch.schemas import ReviewRequest

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
    graph = build_review_graph(
        ModelRouter(primary=provider),
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
        latency_ms = (perf_counter() - started_at) * 1_000
        quality = evaluate_review_output(
            case,
            findings=state["findings"],
            retrieved=state["retrieved_principles"][:3],
            questions=state["questions"],
            line_count=max(1, len(case.code.splitlines())),
            latency_ms=latency_ms,
            require_id_prefix=False,
        )
        case_results.append(
            LiveModelCaseResult(
                quality=quality,
                mode=state["mode"],
                model_name=state.get("model_name"),
                input_tokens=state.get("input_tokens"),
                output_tokens=state.get("output_tokens"),
                attempt_count=state.get("attempt_count", 0),
                validation_failure_count=state.get(
                    "validation_failure_count",
                    0,
                ),
                fallback_reason=state.get("fallback_reason"),
            )
        )

    injection_results = [
        await _evaluate_injection_case(case, graph=graph)
        for case in injection_cases
    ]
    total_runs = len(case_results) + len(injection_results)
    attempts = sum(result.attempt_count for result in case_results) + sum(
        result.attempt_count for result in injection_results
    )
    validation_failures = sum(
        result.validation_failure_count for result in case_results
    ) + sum(
        result.validation_failure_count for result in injection_results
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
    ]
    charged_cost = 0.0
    if spend_guard is not None:
        charged_cost = (await spend_guard.metrics()).reserved_usd

    return LiveModelEvalReport(
        dataset_version=DATASET_VERSION,
        available=True,
        complete=True,
        model_name=model_name,
        configured_max_cost_usd=configured_max_cost_usd,
        selected_review_case_ids=list(review_case_ids),
        selected_injection_case_ids=list(injection_case_ids),
        review_case_count=len(case_results),
        injection_case_count=len(injection_results),
        model_mode_rate=ratio(
            sum(result.mode == "model" for result in case_results)
            + sum(result.mode == "model" for result in injection_results),
            total_runs,
        ),
        fallback_rate=ratio(
            sum(result.mode == "static_fallback" for result in case_results)
            + sum(
                result.mode == "static_fallback" for result in injection_results
            ),
            total_runs,
        ),
        validation_failure_attempt_rate=ratio(validation_failures, attempts),
        finding_precision=ratio(true_positives, predicted_findings),
        finding_recall=ratio(true_positives, expected_findings),
        finding_severity_accuracy=ratio(severity_matches, expected_findings),
        clean_negative_pass_rate=ratio(
            sum(result.quality.predicted_findings == 0 for result in clean_results),
            len(clean_results),
        ),
        mixed_case_full_recall=ratio(
            sum(result.quality.false_negatives == 0 for result in mixed_results),
            len(mixed_results),
        ),
        citation_faithfulness=ratio(
            sum(result.quality.citation_faithful for result in case_results),
            len(case_results),
        ),
        hallucinated_line_number_rate=ratio(
            sum(
                result.quality.hallucinated_line_numbers
                for result in case_results
            ),
            finding_count,
        ),
        prompt_injection_pass_rate=ratio(
            sum(result.passed for result in injection_results),
            len(injection_results),
        ),
        average_latency_ms=ratio(sum(latencies), len(latencies)),
        p95_latency_ms=_p95(latencies),
        total_input_tokens=sum(
            result.input_tokens or 0 for result in case_results
        )
        + sum(result.input_tokens or 0 for result in injection_results),
        total_output_tokens=sum(
            result.output_tokens or 0 for result in case_results
        )
        + sum(result.output_tokens or 0 for result in injection_results),
        charged_cost_usd=charged_cost,
        cases=case_results,
        injection_cases=injection_results,
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
        return await evaluate_live_model(
            provider,
            model_name=model_name,
            configured_max_cost_usd=max_cost,
            spend_guard=spend_guard,
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
    return LiveModelInjectionCaseResult(
        case_id=case.id,
        mode=state["mode"],
        passed=not prohibited_terms and not unknown_citations,
        prohibited_terms_found=prohibited_terms,
        unknown_citation_ids=unknown_citations,
        latency_ms=latency_ms,
        model_name=state.get("model_name"),
        input_tokens=state.get("input_tokens"),
        output_tokens=state.get("output_tokens"),
        attempt_count=state.get("attempt_count", 0),
        validation_failure_count=state.get("validation_failure_count", 0),
        fallback_reason=state.get("fallback_reason"),
    )


def _select_cases(
    cases: Sequence[_CaseT],
    selected_ids: Sequence[str],
) -> list[_CaseT]:
    cases_by_id = {case.id: case for case in cases}
    missing = set(selected_ids) - set(cases_by_id)
    if missing:
        raise ValueError("unknown live eval cases: " + ", ".join(sorted(missing)))
    return [cases_by_id[case_id] for case_id in selected_ids]


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
    if not report.complete or report.fallback_rate:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
