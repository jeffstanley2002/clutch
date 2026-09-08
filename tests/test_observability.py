import asyncio
import json

import pytest

from clutch.agent import build_review_graph
from clutch.llm import ModelRouter
from clutch.observability import InMemoryObservability, redact_sensitive_data
from clutch.observability.tracing import _sample_rate_from_env
from clutch.persistence import InMemoryReviewRecorder
from clutch.review.service import ReviewService
from clutch.schemas import ReviewRequest


def test_review_tracing_records_nodes_without_raw_code() -> None:
    observer = InMemoryObservability()
    graph = build_review_graph(
        ModelRouter(primary=None),
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
    }
    root = next(record for record in observer.records if record["name"] == "review.request")
    assert root["input"]["source_sha256"]
    assert root["output"]["mode"] == "static_fallback"


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
