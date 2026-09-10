import asyncio
import json

import pytest

from clutch.agent import build_review_graph
from clutch.llm import ModelRouter
from clutch.llm.providers import (
    ProviderQuestions,
    ProviderReview,
    QuestionContext,
    ReviewContext,
)
from clutch.observability import InMemoryObservability, redact_sensitive_data
from clutch.observability.tracing import _sample_rate_from_env
from clutch.persistence import InMemoryReviewRecorder
from clutch.review.service import ReviewService
from clutch.schemas import InterviewQuestion, ReviewRequest


class StaticTestModelProvider:
    async def review(self, context: ReviewContext) -> ProviderReview:
        return ProviderReview(
            findings=context.static_findings,
            confidence=0.7,
            mode="model",
            model_name="test-model",
            input_tokens=80,
            output_tokens=40,
            attempt_count=1,
            prompt_version="review.v2",
            latency_ms=5.0,
            estimated_cost_usd=0.002,
        )

    async def generate_questions(
        self,
        context: QuestionContext,
    ) -> ProviderQuestions:
        return ProviderQuestions(
            questions=[
                InterviewQuestion(
                    id="question-001",
                    finding_id=context.findings[0].id,
                    question="How would you resolve and verify this TODO?",
                    intent="Assess maintainability reasoning.",
                    difficulty="medium",
                    citations=context.findings[0].citations,
                    origin="ai_generated",
                )
            ],
            model_name="test-model",
            input_tokens=30,
            output_tokens=20,
            attempt_count=1,
            prompt_version="questions.v1",
            latency_ms=3.0,
            estimated_cost_usd=0.001,
        )


def test_review_tracing_records_nodes_without_raw_code() -> None:
    observer = InMemoryObservability()
    graph = build_review_graph(
        ModelRouter(primary=StaticTestModelProvider()),
        observability=observer,
    )
    service = ReviewService(
        graph=graph,
        recorder=InMemoryReviewRecorder(),
        observability=observer,
    )
    sentinel = "RAW_TRACE_SOURCE_SENTINEL_4fd"

    response = asyncio.run(
        service.review(
            ReviewRequest(
                code=f"def run():\n    # TODO {sentinel}\n    return True\n",
                session_id="trace-candidate",
            )
        )
    )
    recorded = json.dumps(observer.records)

    assert response.findings
    assert sentinel not in recorded
    assert {record["name"] for record in observer.records} == {
        "review.request",
        "review.parse_code",
        "review.static_review",
        "review.retrieve_principles",
        "review.synthesize",
        "review.validate_findings",
        "review.generate_questions",
        "review.persistence",
    }
    root = next(record for record in observer.records if record["name"] == "review.request")
    assert root["input"]["source_sha256"]
    assert root["output"]["mode"] == "model"
    synthesis = next(
        record for record in observer.records if record["name"] == "review.synthesize"
    )
    assert synthesis["model"] == "test-model"
    assert synthesis["version"] == "review.v2"
    assert synthesis["usage_details"] == {"input": 80, "output": 40, "total": 120}
    assert synthesis["cost_details"] == {"total": 0.002}
    assert synthesis["level"] == "DEFAULT"
    assert synthesis["status_message"] == "succeeded"
    assert all(
        record["metadata"]["redaction_policy"] == "hashes_counts_ids_only.v1"
        for record in observer.records
    )


def test_review_tracing_marks_fallbacks_with_safe_failure_category() -> None:
    observer = InMemoryObservability()
    service = ReviewService(
        graph=build_review_graph(ModelRouter(primary=None), observability=observer),
        recorder=InMemoryReviewRecorder(),
        observability=observer,
    )

    response = asyncio.run(
        service.review(ReviewRequest(code="def run():\n    # TODO finish\n"))
    )

    assert response.mode == "static_fallback"
    fallback_names = {
        record["name"] for record in observer.records if "fallback" in record["name"]
    }
    assert fallback_names == {"review.fallback", "questions.fallback"}
    for record in observer.records:
        if record["name"] in fallback_names:
            assert record["level"] == "WARNING"
            assert record["metadata"]["failure_category"] == "model_not_configured"


def test_trace_mask_redacts_sensitive_fields_and_bearer_tokens() -> None:
    masked = redact_sensitive_data(
        {
            "code": "raw source",
            "nested": {"answer": "private", "safe": "Bearer abc.def"},
        }
    )

    assert masked == {
        "code": "[REDACTED]",
        "nested": {"answer": "[REDACTED]", "safe": "Bearer [REDACTED]"},
    }


def test_langfuse_sample_rate_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGFUSE_SAMPLE_RATE", "0.25")
    assert _sample_rate_from_env() == 0.25

    monkeypatch.setenv("LANGFUSE_SAMPLE_RATE", "1.5")
    with pytest.raises(ValueError, match="between zero and one"):
        _sample_rate_from_env()
