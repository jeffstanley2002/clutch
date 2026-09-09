import asyncio
from types import SimpleNamespace

import pytest

from clutch.knowledge_base import retrieve_clean_code_principles
from clutch.llm.providers import (
    ModelRouter,
    OpenAIProvider,
    ProviderReview,
    ReviewContext,
    ReviewModelUnavailable,
)
from clutch.llm.spend import InMemorySpendGuard
from clutch.parsing import parse_python_code
from clutch.review.static import run_static_review
from clutch.schemas import CodeFinding, ReviewRequest


def _context() -> ReviewContext:
    request = ReviewRequest(
        code="def collect(value, bucket=[]):\n    return bucket\n",
        role_context="backend intern",
    )
    parsed = parse_python_code(request.code)
    findings = run_static_review(request, parsed_code=parsed)
    principles = retrieve_clean_code_principles(
        "safe python mutable default argument",
        limit=3,
    )
    return ReviewContext(
        request=request,
        parsed_code=parsed,
        static_findings=findings,
        principles=principles,
    )


class FailingProvider:
    async def review(self, context: ReviewContext) -> ProviderReview:
        raise RuntimeError("provider unavailable")


def test_model_router_labels_static_fallback_when_primary_fails() -> None:
    router = ModelRouter(primary=FailingProvider())

    result = asyncio.run(router.review(_context()))

    assert result.mode == "static_fallback"
    assert result.failure_category == "provider_error"
    assert result.attempt_count == 0
    assert result.validation_failure_count == 0
    assert all(finding.origin == "deterministic_static" for finding in result.findings)


def test_provider_review_rejects_impossible_diagnostic_counts() -> None:
    with pytest.raises(
        ValueError,
        match="validation failures cannot exceed provider attempts",
    ):
        ProviderReview(
            findings=[],
            confidence=0.7,
            mode="model",
            attempt_count=0,
            validation_failure_count=1,
        )


class FakeResponses:
    def __init__(self, outputs: list[object]) -> None:
        self.outputs = outputs
        self.calls = 0

    async def parse(self, **kwargs: object) -> SimpleNamespace:
        output = self.outputs[self.calls]
        self.calls += 1
        return SimpleNamespace(output_parsed=output)


class FakeClient:
    def __init__(self, responses: FakeResponses) -> None:
        self.responses = responses


def test_openai_provider_retries_ungrounded_output_once() -> None:
    context = _context()
    valid_finding = context.static_findings[0]
    invalid_finding = CodeFinding.model_validate(
        {
            **valid_finding.model_dump(),
            "citations": [
                {
                    "source_id": "invented.source",
                    "title": "Invented source",
                }
            ]
        }
    )
    responses = FakeResponses(
        [
            {"findings": [invalid_finding], "confidence": 0.9},
            {"findings": [valid_finding], "confidence": 0.8},
        ]
    )
    provider = OpenAIProvider(
        api_key="test-key",  # pragma: allowlist secret
        client=FakeClient(responses),
    )

    result = asyncio.run(provider.review(context))

    assert responses.calls == 2
    assert result.mode == "model"
    assert result.model_name == "gpt-5.4-mini"
    assert result.confidence == 0.8
    assert result.findings == [
        valid_finding.model_copy(update={"origin": "ai_generated"})
    ]
    assert result.attempt_count == 2
    assert result.validation_failure_count == 1


def test_openai_provider_labels_bounded_validation_fallback() -> None:
    context = _context()
    invalid = {"findings": [], "confidence": 2.0}
    responses = FakeResponses([invalid, invalid])
    provider = OpenAIProvider(
        api_key="test-key",  # pragma: allowlist secret
        client=FakeClient(responses),
    )
    router = ModelRouter(primary=provider)

    result = asyncio.run(router.review(context))

    assert result.mode == "static_fallback"
    assert result.failure_category == "schema_validation_failed"
    assert result.attempt_count == 2
    assert result.validation_failure_count == 2


def test_model_router_labels_budget_fallback_before_provider_call() -> None:
    responses = FakeResponses([])
    provider = OpenAIProvider(
        api_key="test-key",  # pragma: allowlist secret
        client=FakeClient(responses),
        spend_guard=InMemorySpendGuard(
            per_request_limit_usd=0.001,
            daily_limit_usd=1.0,
        ),
    )
    router = ModelRouter(primary=provider)

    result = asyncio.run(router.review(_context()))

    assert result.mode == "static_fallback"
    assert result.failure_category == "budget_rejected"
    assert responses.calls == 0


def test_model_router_returns_retrieval_only_when_model_and_static_findings_absent() -> None:
    router = ModelRouter(primary=None)
    context = _context().model_copy(update={"static_findings": []})

    result = asyncio.run(router.review(context))

    assert result.mode == "retrieval_only"
    assert result.failure_category == "model_not_configured"
    assert result.findings == []


class FailingFallback:
    async def review(self, context: ReviewContext) -> ProviderReview:
        raise ValueError("fallback internals must remain private")


def test_model_router_raises_typed_failure_only_when_both_paths_fail() -> None:
    router = ModelRouter(primary=FailingProvider(), fallback=FailingFallback())

    with pytest.raises(ReviewModelUnavailable) as error:
        asyncio.run(router.review(_context()))

    assert error.value.failure_reason == "fallback_failed"
    assert error.value.failure_category == "fallback_failed"
    assert "internals" not in str(error.value)
