"""FastAPI service boundary for Clutch."""

from fastapi import FastAPI

from clutch.review.static import run_static_review
from clutch.schemas import CodeFinding, ReviewRequest


app = FastAPI(
    title="Clutch API",
    description="Read-only code review and interview prep backend.",
    version="0.1.0",
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/review", response_model=list[CodeFinding])
async def review_code(request: ReviewRequest) -> list[CodeFinding]:
    return run_static_review(request)

