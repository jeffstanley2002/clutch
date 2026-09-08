import asyncio

from clutch.agent import build_review_graph
from clutch.llm import ModelRouter
from clutch.persistence import InMemoryReviewRecorder
from clutch.progress.repository import InMemoryProgressRepository
from clutch.progress.service import ProgressService
from clutch.review.service import ReviewService
from clutch.schemas import ReviewRequest


def test_progress_tracks_improvement_and_persistent_categories() -> None:
    async def exercise() -> None:
        review_store = InMemoryReviewRecorder()
        review_service = ReviewService(
            graph=build_review_graph(ModelRouter(primary=None)),
            recorder=review_store,
        )
        progress_repository = InMemoryProgressRepository(review_store)
        progress_service = ProgressService(progress_repository)
        profile_id = "progress-candidate"

        await review_service.review(
            ReviewRequest(
                code="def first():\n    # TODO finish this\n    return True\n",
                session_id=profile_id,
            )
        )
        await review_service.review(
            ReviewRequest(
                code=(
                    "def second():\n    try:\n        return work()\n"
                    "    except:\n        return None\n"
                ),
                session_id=profile_id,
            )
        )
        await review_service.review(
            ReviewRequest(
                code=(
                    "def third():\n    try:\n        return work()\n"
                    "    except:\n        return None\n"
                ),
                session_id=profile_id,
            )
        )

        snapshot = await progress_service.summarize(profile_id)
        saved = await progress_service.save_snapshot(profile_id)

        assert snapshot.time_window == "3 review session(s)"
        assert snapshot.improved_areas == ["maintainability"]
        assert snapshot.persistent_issues == ["correctness"]
        assert snapshot.next_practice_tasks == [
            "Practice explicit failure cases and boundary-focused tests."
        ]
        assert len(snapshot.evidence_sessions) == 3
        assert saved == snapshot
        assert progress_repository.snapshots == [snapshot]

    asyncio.run(exercise())


def test_empty_progress_gives_a_concrete_next_action() -> None:
    repository = InMemoryProgressRepository(InMemoryReviewRecorder())

    snapshot = asyncio.run(repository.summarize("new-candidate"))

    assert snapshot.time_window == "No review sessions yet"
    assert snapshot.evidence_sessions == []
    assert snapshot.next_practice_tasks
