import asyncio
import logging

from clutch.agent import build_review_graph
from clutch.llm import ModelRouter
from clutch.persistence import NullReviewRecorder
from clutch.review.service import ReviewService
from clutch.schemas import ReviewRequest


def test_review_does_not_log_raw_submitted_code(caplog) -> None:
    sentinel = "RAW_CODE_SENTINEL_47f35d"
    service = ReviewService(
        graph=build_review_graph(ModelRouter(primary=None)),
        recorder=NullReviewRecorder(),
    )

    with caplog.at_level(logging.DEBUG):
        response = asyncio.run(
            service.review(
                ReviewRequest(
                    code=f"def value():\n    return '{sentinel}'\n",
                )
            )
        )

    assert response.mode == "static_fallback"
    assert sentinel not in caplog.text
