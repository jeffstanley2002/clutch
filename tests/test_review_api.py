import pytest
from fastapi.testclient import TestClient

import backend.app.main as main_module
from backend.app.main import app
from clutch.github.contracts import FetchedRepository, GitHubFile
from clutch.github.review import GitHubReviewService
from clutch.review.service import ReviewService

client = TestClient(app)


@pytest.fixture(autouse=True)
def _disable_api_auth_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep local deployment secrets from changing API test behavior."""

    monkeypatch.setenv("CLUTCH_REQUIRE_AUTH", "false")
    monkeypatch.setenv("CLUTCH_API_KEY", "")


def _use_fake_model_review(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from clutch.agent import build_review_graph
    from clutch.llm import ModelRouter
    from clutch.llm.providers import ProviderReview, ReviewContext
    from clutch.persistence.repository import IN_MEMORY_REVIEW_RECORDER

    class StaticTestModelProvider:
        async def review(self, context: ReviewContext) -> ProviderReview:
            return ProviderReview(
                findings=context.static_findings,
                confidence=0.7,
                mode="model",
                model_name="test-model",
                attempt_count=1,
            )

    service = ReviewService(
        graph=build_review_graph(ModelRouter(primary=StaticTestModelProvider())),
        recorder=IN_MEMORY_REVIEW_RECORDER,
    )
    monkeypatch.setattr(main_module, "review_service", service)


def test_health_check_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cache_metrics_endpoint_is_safe_and_structured() -> None:
    response = client.get("/runtime/cache")

    assert response.status_code == 200
    assert set(response.json()) == {"hits", "misses", "writes", "errors", "lookup_ms"}


def test_spend_metrics_endpoint_is_safe_and_structured() -> None:
    response = client.get("/runtime/spend")

    assert response.status_code == 200
    assert set(response.json()) == {
        "day_utc",
        "reserved_usd",
        "daily_limit_usd",
        "per_request_limit_usd",
    }


def test_api_key_auth_can_protect_every_non_health_route(monkeypatch) -> None:
    monkeypatch.setenv("CLUTCH_REQUIRE_AUTH", "true")
    monkeypatch.setenv(  # pragma: allowlist secret
        "CLUTCH_API_KEY", "test-api-key"
    )

    health = client.get("/health")
    rejected = client.get("/runtime/cache")
    accepted = client.get(
        "/runtime/cache",
        headers={"X-Clutch-API-Key": "test-api-key"},  # pragma: allowlist secret
    )

    assert health.status_code == 200
    assert rejected.status_code == 401
    assert rejected.json() == {"detail": "invalid or missing API key"}
    assert accepted.status_code == 200


def test_required_auth_fails_closed_without_configured_key(monkeypatch) -> None:
    monkeypatch.setenv("CLUTCH_REQUIRE_AUTH", "true")
    monkeypatch.setenv("CLUTCH_API_KEY", "")

    response = client.get("/runtime/cache")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "API authentication is required but not configured"
    }


def test_review_plainly_labels_retrieval_only_without_model(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("OPENAI_API_KEY", "")

    response = client.post(
        "/review",
        json={
            "code": "def value():\n    return 1\n",
            "language": "python",
            "role_context": "backend intern",
        },
    )

    assert response.status_code == 200
    review = response.json()
    assert review["mode"] == "retrieval_only"
    assert review["findings"] == []
    assert review["citations_used"]
    synthesis = next(
        stage
        for stage in review["provenance"]
        if stage["stage"] == "review_synthesis"
    )
    assert synthesis["status"] == "fallback"
    assert synthesis["origin"] == "deterministic_static"
    assert synthesis["failure_category"] == "model_not_configured"


def test_review_returns_structured_findings_for_model_issues(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _use_fake_model_review(monkeypatch)
    code = "\n".join(
        [
            "def collect(value, bucket=[]):",
            "    # TODO clean this up",
            "    print(value)",
            "    return bucket",
        ]
    )
    response = client.post(
        "/review",
        json={
            "code": code,
            "language": "python",
            "role_context": "backend intern",
        },
    )

    assert response.status_code == 200
    review = response.json()
    findings = review["findings"]

    assert len(findings) == 3
    assert {finding["category"] for finding in findings} == {
        "correctness",
        "maintainability",
    }
    assert all(finding["citations"] for finding in findings)
    assert all("id" in finding for finding in findings)
    citation_source_ids = {
        citation["source_id"]
        for finding in findings
        for citation in finding["citations"]
    }
    assert citation_source_ids == {
        "seed.clean_code.explicit_incomplete_work",
        "seed.clean_code.boundary_observability",
        "seed.clean_code.safe_python_defaults",
    }
    assert review["mode"] == "model"
    assert all(finding["origin"] == "ai_generated" for finding in findings)
    assert 0 <= review["confidence"] <= 1
    assert review["request_id"]
    assert review["latency_ms"] >= 0
    assert len(review["questions"]) == 3
    assert {citation["source_id"] for citation in review["citations_used"]} == (
        citation_source_ids
    )


def test_review_uses_parsed_line_metadata_for_large_functions(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _use_fake_model_review(monkeypatch)
    body = "\n".join(f"    value += {number}" for number in range(45))
    response = client.post(
        "/review",
        json={
            "code": f"def calculate(value):\n{body}\n    return value\n",
            "language": "python",
            "role_context": "backend intern",
        },
    )

    assert response.status_code == 200
    findings = response.json()["findings"]
    long_function = next(
        finding
        for finding in findings
        if finding["id"].startswith("finding-long-function")
    )

    assert long_function["line_start"] == 1
    assert long_function["line_end"] == 47
    assert "`calculate`" in long_function["evidence"]
    assert (
        long_function["citations"][0]["source_id"]
        == "seed.clean_code.small_reviewable_units"
    )


def test_review_preserves_long_snippet_finding_for_top_level_code(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _use_fake_model_review(monkeypatch)
    code = "\n".join(f"value += {number}" for number in range(65))
    response = client.post(
        "/review",
        json={
            "code": code,
            "language": "python",
            "role_context": "backend intern",
        },
    )

    assert response.status_code == 200
    findings = response.json()["findings"]
    assert any(finding["id"] == "finding-long-snippet" for finding in findings)


def test_review_rejects_blank_code() -> None:
    response = client.post(
        "/review",
        json={
            "code": "   ",
            "language": "python",
            "role_context": "backend intern",
        },
    )

    assert response.status_code == 422


def test_interview_route_starts_and_answers_a_session() -> None:
    question = {
        "id": "question-api-1",
        "finding_id": "finding-api-1",
        "question": "How would you test this boundary?",
        "intent": "Assess testing and edge-case reasoning.",
        "difficulty": "easy",
        "citations": [],
    }
    started = client.post(
        "/interview/turn",
        json={"profile_id": "api-candidate", "questions": [question]},
    )

    assert started.status_code == 200
    session_id = started.json()["interview_session_id"]
    answered = client.post(
        "/interview/turn",
        json={
            "interview_session_id": session_id,
            "answer": (
                "I would add a focused test for the expected behavior and one edge "
                "case, then verify the boundary contract."
            ),
        },
    )

    assert answered.status_code == 200
    assert answered.json()["completed"] is True
    assert answered.json()["assessment"]["score"] >= 3

    feedback = client.get(f"/interview/{session_id}/feedback")

    assert feedback.status_code == 200
    assert feedback.json()["session_id"] == session_id
    assert feedback.json()["strengths"]
    assert feedback.json()["recommended_tasks"]
    assert "completed turn" in feedback.json()["interview_readiness_summary"]


def test_feedback_route_requires_a_completed_interview() -> None:
    question = {
        "id": "question-api-active",
        "question": "How would you test this boundary?",
        "intent": "Assess testing decisions.",
        "difficulty": "easy",
    }
    started = client.post(
        "/interview/turn",
        json={"profile_id": "api-active-candidate", "questions": [question]},
    )

    response = client.get(
        f"/interview/{started.json()['interview_session_id']}/feedback"
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "complete the interview before requesting final feedback"
    }


def test_interview_route_returns_404_for_unknown_session() -> None:
    response = client.post(
        "/interview/turn",
        json={
            "interview_session_id": "unknown-session",
            "answer": "A complete answer that belongs to no session.",
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "interview session not found"}


def test_progress_route_aggregates_reviews_for_one_profile(
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    _use_fake_model_review(monkeypatch)
    profile_id = "api-progress-candidate"
    for code in (
        "def one():\n    # TODO finish\n    return True\n",
        "def two():\n    # TODO remove workaround\n    return True\n",
    ):
        review = client.post(
            "/review",
            json={"code": code, "session_id": profile_id},
        )
        assert review.status_code == 200

    progress = client.get(f"/progress/{profile_id}")
    saved = client.post(f"/progress/{profile_id}/snapshots")

    assert progress.status_code == 200
    assert progress.json()["persistent_issues"] == ["maintainability"]
    assert len(progress.json()["evidence_sessions"]) == 2
    assert saved.status_code == 200
    assert saved.json() == progress.json()


def test_profile_routes_reject_invalid_identifiers() -> None:
    response = client.get("/progress/not%20a%20safe%20id")

    assert response.status_code == 422


def test_interview_route_rejects_invalid_profile_identifier() -> None:
    question = {
        "id": "question-api-safe-id",
        "question": "How would you test this boundary?",
        "intent": "Assess testing decisions.",
        "difficulty": "easy",
    }
    response = client.post(
        "/interview/turn",
        json={"profile_id": "not a safe id", "questions": [question]},
    )

    assert response.status_code == 422


def test_github_review_route_returns_ingestion_metadata(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _use_fake_model_review(monkeypatch)

    class FakeGateway:
        async def fetch_repo(
            self,
            repository_url: str,
            ref: str | None = None,
        ) -> FetchedRepository:
            return FetchedRepository(
                owner="acme",
                repository="demo",
                ref=ref or "main",
                files=[
                    GitHubFile(
                        path="app.py",
                        sha="a" * 40,
                        size=32,
                        content="def run():\n    # TODO finish\n",
                    )
                ],
                total_bytes=32,
            )

        async def fetch_pr_diff(self, pull_request_url: str):  # type: ignore[no-untyped-def]
            raise AssertionError("repository URL should not fetch a PR")

    monkeypatch.setattr(
        main_module,
        "github_review_service",
        GitHubReviewService(FakeGateway(), main_module.review_service),
    )

    response = client.post(
        "/review/github",
        json={
            "source_url": "https://github.com/acme/demo",
            "role_context": "platform intern",
            "session_id": "api-github-candidate",
        },
    )

    assert response.status_code == 200
    assert response.json()["ingestion"]["source_type"] == "repository"
    assert response.json()["ingestion"]["files_included"] == ["app.py"]
    assert response.json()["review"]["findings"]
