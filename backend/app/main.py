"""FastAPI service boundary for Clutch."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, HTTPException, Path, Request
from fastapi.responses import JSONResponse, Response

from backend.app.security import authorize_request
from clutch.cache import (
    CacheMetrics,
    cache_metrics_snapshot,
    close_registered_caches,
)
from clutch.github.client import GitHubAPIError
from clutch.github.review import GitHubReviewSourceEmpty, github_review_service
from clutch.github.service import GitHubIngestionError
from clutch.github.urls import GitHubUrlError
from clutch.interview import (
    InterviewNotComplete,
    InterviewSessionNotFound,
    interview_service,
)
from clutch.llm import SpendMetrics, close_spend_guard, spend_metrics_snapshot
from clutch.observability import close_observability
from clutch.progress import progress_service
from clutch.review.service import review_service
from clutch.schemas import (
    FeedbackReport,
    GitHubReviewRequest,
    GitHubReviewResponse,
    InterviewTurnRequest,
    InterviewTurnResponse,
    ProgressSnapshot,
    ReviewRequest,
    ReviewResponse,
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await close_registered_caches()
    await close_spend_guard()
    close_observability()


app = FastAPI(
    title="Clutch API",
    description="Read-only code review and interview prep backend.",
    version="0.1.0",
    lifespan=lifespan,
)

ProfileId = Annotated[
    str,
    Path(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_-]+$"),
]
InterviewId = Annotated[
    str,
    Path(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_-]+$"),
]


@app.middleware("http")
async def enforce_api_auth(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    if request.url.path == "/health":
        return await call_next(request)
    try:
        authorize_request(request)
    except HTTPException as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers,
        )
    return await call_next(request)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/runtime/cache", response_model=CacheMetrics)
async def cache_metrics() -> CacheMetrics:
    return cache_metrics_snapshot()


@app.get("/runtime/spend", response_model=SpendMetrics)
async def spend_metrics() -> SpendMetrics:
    try:
        return await spend_metrics_snapshot()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="model-spend counter unavailable",
        ) from exc


@app.post("/review", response_model=ReviewResponse)
async def review_code(request: ReviewRequest) -> ReviewResponse:
    return await review_service.review(request)


@app.post("/review/github", response_model=GitHubReviewResponse)
async def review_github(request: GitHubReviewRequest) -> GitHubReviewResponse:
    try:
        return await github_review_service.review(request)
    except (GitHubUrlError, GitHubIngestionError, GitHubReviewSourceEmpty) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except GitHubAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/interview/turn", response_model=InterviewTurnResponse)
async def run_interview_turn(
    request: InterviewTurnRequest,
) -> InterviewTurnResponse:
    try:
        return await interview_service.run_turn(request)
    except InterviewSessionNotFound as exc:
        raise HTTPException(status_code=404, detail="interview session not found") from exc


@app.get("/interview/{session_id}/feedback", response_model=FeedbackReport)
async def get_interview_feedback(session_id: InterviewId) -> FeedbackReport:
    try:
        return await interview_service.generate_feedback(session_id)
    except InterviewSessionNotFound as exc:
        raise HTTPException(status_code=404, detail="interview session not found") from exc
    except InterviewNotComplete as exc:
        raise HTTPException(
            status_code=409,
            detail="complete the interview before requesting final feedback",
        ) from exc


@app.get("/progress/{profile_id}", response_model=ProgressSnapshot)
async def get_progress(profile_id: ProfileId) -> ProgressSnapshot:
    return await progress_service.summarize(profile_id)


@app.post("/progress/{profile_id}/snapshots", response_model=ProgressSnapshot)
async def save_progress_snapshot(profile_id: ProfileId) -> ProgressSnapshot:
    return await progress_service.save_snapshot(profile_id)
