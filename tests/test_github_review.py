import asyncio

import pytest

from clutch.agent import build_review_graph
from clutch.github.contracts import (
    FetchedRepository,
    GitHubFile,
    PullRequestDiff,
    PullRequestPatch,
)
from clutch.github.review import GitHubReviewService, GitHubReviewSourceEmpty
from clutch.llm import ModelRouter
from clutch.llm.providers import ProviderReview, ReviewContext
from clutch.persistence import InMemoryReviewRecorder
from clutch.review.service import ReviewService
from clutch.schemas import GitHubReviewRequest


class FakeGateway:
    def __init__(
        self,
        *,
        repository: FetchedRepository | None = None,
        diff: PullRequestDiff | None = None,
    ) -> None:
        self.repository = repository
        self.diff = diff

    async def fetch_repo(
        self,
        repository_url: str,
        ref: str | None = None,
    ) -> FetchedRepository:
        assert self.repository is not None
        return self.repository

    async def fetch_pr_diff(self, pull_request_url: str) -> PullRequestDiff:
        assert self.diff is not None
        return self.diff


class StaticTestModelProvider:
    async def review(self, context: ReviewContext) -> ProviderReview:
        return ProviderReview(
            findings=context.static_findings,
            confidence=0.7,
            mode="model",
            model_name="test-model",
            attempt_count=1,
        )


def _reviewer(recorder: InMemoryReviewRecorder) -> ReviewService:
    return ReviewService(
        graph=build_review_graph(ModelRouter(primary=StaticTestModelProvider())),
        recorder=recorder,
    )


def test_repository_review_uses_mcp_content_without_persisting_raw_source() -> None:
    sentinel = "GITHUB_RAW_SOURCE_SENTINEL"
    repository = FetchedRepository(
        owner="acme",
        repository="demo",
        ref="main",
        files=[
            GitHubFile(
                path="app.py",
                sha="a" * 40,
                size=60,
                content=f"def run():\n    # TODO {sentinel}\n    return True\n",
            )
        ],
        total_bytes=60,
    )
    recorder = InMemoryReviewRecorder()
    service = GitHubReviewService(FakeGateway(repository=repository), _reviewer(recorder))

    response = asyncio.run(
        service.review(
            GitHubReviewRequest(
                source_url="https://github.com/acme/demo",
                session_id="candidate-github",
            )
        )
    )

    assert response.ingestion.files_included == ["app.py"]
    assert response.ingestion.source_type == "repository"
    assert any(item.category == "maintainability" for item in response.review.findings)
    assert sentinel not in recorder.records[0].model_dump_json()


def test_pull_request_review_extracts_added_python_source() -> None:
    diff = PullRequestDiff(
        owner="acme",
        repository="demo",
        pull_number=9,
        files=[
            PullRequestPatch(
                path="app.py",
                status="modified",
                additions=2,
                deletions=1,
                changes=3,
                patch="@@ -1 +1,2 @@\n-old = True\n+print('debug')\n+new = True",
            )
        ],
        total_bytes=60,
    )
    service = GitHubReviewService(
        FakeGateway(diff=diff),
        _reviewer(InMemoryReviewRecorder()),
    )

    response = asyncio.run(
        service.review(
            GitHubReviewRequest(
                source_url="https://github.com/acme/demo/pull/9",
            )
        )
    )

    assert response.ingestion.source_type == "pull_request"
    assert response.ingestion.pull_number == 9
    assert any("debug" in item.message.lower() for item in response.review.findings)


def test_repository_without_python_source_is_explicit() -> None:
    repository = FetchedRepository(
        owner="acme",
        repository="docs",
        ref="main",
        files=[
            GitHubFile(
                path="README.md",
                sha="a" * 40,
                size=10,
                content="# Docs",
            )
        ],
        total_bytes=10,
    )
    service = GitHubReviewService(
        FakeGateway(repository=repository),
        _reviewer(InMemoryReviewRecorder()),
    )

    with pytest.raises(GitHubReviewSourceEmpty):
        asyncio.run(
            service.review(
                GitHubReviewRequest(source_url="https://github.com/acme/docs")
            )
        )
