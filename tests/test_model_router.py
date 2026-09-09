import asyncio
from types import SimpleNamespace

import pytest

from clutch.knowledge_base import retrieve_clean_code_principles
from clutch.llm.providers import (
    InterviewAssessmentContext,
    ModelRouter,
    OpenAIProvider,
    ProviderReview,
    QuestionContext,
    ReviewContext,
    ReviewModelUnavailable,
)
from clutch.llm.spend import InMemorySpendGuard
from clutch.parsing import parse_python_code
from clutch.review.static import run_static_review
from clutch.schemas import (
    CodeFinding,
    InterviewAssessment,
    InterviewQuestion,
    ReviewRequest,
)


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


def _question_context() -> QuestionContext:
    context = _context()
    return QuestionContext(
        role_context=context.request.role_context,
        findings=context.static_findings[:1],
        principles=context.principles,
    )


def _assessment_context() -> InterviewAssessmentContext:
    question_context = _question_context()
    return InterviewAssessmentContext(
        role_context=question_context.role_context,
        question=InterviewQuestion(
            id="question-1",
            finding_id=question_context.findings[0].id,
            question="How would you improve and verify this default?",
            intent="Assess correctness reasoning.",
            difficulty="medium",
        ),
        answer="I would use None because it avoids shared state and test two calls.",
        answer_signal_summary="Answer length: 65 characters; signals: testing.",
        principles=question_context.principles[:3],
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
        self.requests: list[dict[str, object]] = []

    async def parse(self, **kwargs: object) -> SimpleNamespace:
        self.requests.append(kwargs)
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


def test_openai_provider_generates_canonical_grounded_questions() -> None:
    context = _question_context()
    citation = context.principles[0].citation
    responses = FakeResponses(
        [
            {
                "questions": [
                    {
                        "finding_id": context.findings[0].id,
                        "question": "How would you verify the safer default?",
                        "intent": "Assess reasoning about state shared across calls.",
                        "difficulty": "medium",
                        "citation_ids": [citation.source_id],
                    }
                ]
            }
        ]
    )
    provider = OpenAIProvider(
        api_key="test-key",  # pragma: allowlist secret
        client=FakeClient(responses),
    )

    result = asyncio.run(provider.generate_questions(context))

    assert result.questions[0].id == "question-001"
    assert result.questions[0].finding_id == context.findings[0].id
    assert result.questions[0].citations == [citation]
    assert result.questions[0].origin == "ai_generated"
    assert result.prompt_version == "questions.v1"
    assert responses.requests[0]["store"] is False
    assert responses.requests[0]["max_output_tokens"] == 1_600


def test_question_generation_falls_back_after_grounding_validation() -> None:
    context = _question_context()
    invalid = {
        "questions": [
            {
                "finding_id": context.findings[0].id,
                "question": "Invented grounding?",
                "intent": "This should be rejected.",
                "difficulty": "easy",
                "citation_ids": ["invented.source"],
            }
        ]
    }
    responses = FakeResponses([invalid, invalid])
    provider = OpenAIProvider(
        api_key="test-key",  # pragma: allowlist secret
        client=FakeClient(responses),
    )
    template = InterviewQuestion(
        id="template-1",
        finding_id=context.findings[0].id,
        question="How would you improve this issue?",
        intent="Assess practical reasoning.",
        difficulty="medium",
    )

    result = asyncio.run(
        ModelRouter(primary=provider).generate_questions(
            context,
            template_questions=[template],
        )
    )

    assert result.questions == [template]
    assert result.failure_category == "grounding_validation_failed"
    assert result.attempt_count == 2
    assert result.validation_failure_count == 2
    assert responses.calls == 2


def test_openai_provider_assesses_answer_with_canonical_citations() -> None:
    context = _assessment_context()
    citation = context.principles[0].citation
    responses = FakeResponses(
        [
            {
                "score": 4,
                "strengths": ["Explains why shared state is unsafe."],
                "gaps": ["Name one tradeoff."],
                "feedback": "Good reasoning; make the tradeoff explicit.",
                "citation_ids": [citation.source_id],
            }
        ]
    )
    provider = OpenAIProvider(
        api_key="test-key",  # pragma: allowlist secret
        client=FakeClient(responses),
    )

    result = asyncio.run(provider.assess_interview(context))

    assert result.assessment.score == 4
    assert result.assessment.citations == [citation]
    assert result.assessment.origin == "ai_generated"
    assert result.prompt_version == "interview_assessment.v1"
    assert responses.requests[0]["store"] is False
    assert responses.requests[0]["max_output_tokens"] == 1_200


def test_interview_assessment_falls_back_after_invalid_citations() -> None:
    context = _assessment_context()
    invalid = {
        "score": 5,
        "strengths": ["Invented support."],
        "gaps": [],
        "feedback": "This output must not cross the grounding boundary.",
        "citation_ids": ["invented.source"],
    }
    responses = FakeResponses([invalid, invalid])
    provider = OpenAIProvider(
        api_key="test-key",  # pragma: allowlist secret
        client=FakeClient(responses),
    )
    fallback = InterviewAssessment(
        score=2,
        gaps=["Explain the reasoning in more depth."],
        feedback="Rule-based fallback.",
    )

    result = asyncio.run(
        ModelRouter(primary=provider).assess_interview(
            context,
            deterministic_fallback=fallback,
        )
    )

    assert result.assessment == fallback
    assert result.assessment.origin == "deterministic_static"
    assert result.failure_category == "grounding_validation_failed"
    assert result.attempt_count == 2
    assert result.validation_failure_count == 2
