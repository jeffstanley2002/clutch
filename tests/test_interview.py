import asyncio

import pytest
from sqlalchemy import func, select

from clutch.interview.contracts import InterviewTurnRecord
from clutch.interview.repository import (
    InMemoryInterviewRepository,
    InterviewSessionNotFound,
    SqlAlchemyInterviewRepository,
)
from clutch.interview.service import InterviewService
from clutch.persistence import Base, InMemoryReviewRecorder, create_session_factory
from clutch.persistence.contracts import PersistedFinding, ReviewPersistenceRecord
from clutch.persistence.models import InterviewSessionModel, InterviewTurnModel
from clutch.schemas import InterviewQuestion, InterviewTurnRequest


def _questions() -> list[InterviewQuestion]:
    return [
        InterviewQuestion(
            id="question-1",
            finding_id="finding-1",
            question="How would you make this error handling narrower?",
            intent="Assess correctness tradeoffs and failure handling.",
            difficulty="medium",
        ),
        InterviewQuestion(
            id="question-2",
            finding_id="finding-2",
            question="How would you verify the refactor?",
            intent="Assess testing and edge-case reasoning.",
            difficulty="easy",
        ),
    ]


def test_interview_runs_multiple_turns_without_retaining_raw_answers() -> None:
    repository = InMemoryInterviewRepository()
    service = InterviewService(repository)

    started = asyncio.run(
        service.run_turn(
            InterviewTurnRequest(
                profile_id="candidate-1",
                questions=_questions(),
            )
        )
    )
    sentinel = "RAW_INTERVIEW_ANSWER_76ad"
    first_answer = asyncio.run(
        service.run_turn(
            InterviewTurnRequest(
                interview_session_id=started.interview_session_id,
                answer=(
                    f"{sentinel} I would catch the specific exception because it "
                    "preserves correctness. The tradeoff is extra branches, and I "
                    "would test the failure and edge case to verify the behavior."
                ),
            )
        )
    )
    completed = asyncio.run(
        service.run_turn(
            InterviewTurnRequest(
                interview_session_id=started.interview_session_id,
                answer=(
                    "I would add testing around the original behavior and verify "
                    "both the happy path and edge case. However, I would avoid "
                    "overfitting the tests to implementation details."
                ),
            )
        )
    )

    assert started.turn_number == 1
    assert started.question == _questions()[0]
    assert first_answer.turn_number == 2
    assert first_answer.question == _questions()[1]
    assert first_answer.assessment is not None
    assert first_answer.assessment.score == 5
    assert completed.completed is True
    assert completed.status == "completed"
    assert completed.question is None
    assert len(repository.turns) == 2
    assert sentinel not in " ".join(
        turn.model_dump_json() for turn in repository.turns
    )


def test_unknown_interview_session_is_explicit() -> None:
    service = InterviewService(InMemoryInterviewRepository())

    with pytest.raises(InterviewSessionNotFound):
        asyncio.run(
            service.run_turn(
                InterviewTurnRequest(
                    interview_session_id="missing-session",
                    answer="A valid but unmatched answer.",
                )
            )
        )


def test_completed_interview_generates_privacy_safe_feedback_report() -> None:
    async def exercise() -> None:
        repository = InMemoryInterviewRepository()
        review_store = InMemoryReviewRecorder()
        await review_store.record_review(
            ReviewPersistenceRecord(
                review_session_id="review-feedback-1",
                external_session_id="candidate-feedback",
                code_sha256="a" * 64,
                language="python",
                line_count=4,
                role_context="backend intern",
                mode="static_fallback",
                confidence=0.8,
                latency_ms=2.0,
                findings=[
                    PersistedFinding(
                        finding_id="finding-1",
                        severity="medium",
                        category="correctness",
                        message="Catch a narrower exception.",
                        explanation="Broad catches can hide unrelated failures.",
                        suggestion="Handle the expected exception explicitly.",
                        line_start=2,
                        line_end=3,
                        citation_ids=["seed.clean_code.explicit_failures"],
                    )
                ],
            )
        )
        service = InterviewService(repository, review_store)
        started = await service.run_turn(
            InterviewTurnRequest(
                review_session_id="review-feedback-1",
                questions=_questions(),
            )
        )
        sentinel = "RAW_FEEDBACK_ANSWER_f48c"
        for answer in (sentinel, "Still brief"):
            await service.run_turn(
                InterviewTurnRequest(
                    interview_session_id=started.interview_session_id,
                    answer=answer,
                )
            )

        report = await service.generate_feedback(started.interview_session_id)

        assert report.recurring_issues == [
            "Describe how tests or edge cases would verify the change.",
            "Explain the reasoning in more depth.",
            "Name at least one tradeoff behind the decision.",
        ]
        assert len(report.recommended_tasks) == 3
        assert report.supporting_findings[0].id == "finding-1"
        assert "1.0/5 across 2 completed turns" in (
            report.interview_readiness_summary
        )
        assert sentinel not in report.model_dump_json()

    asyncio.run(exercise())


def test_sqlalchemy_interview_repository_round_trip() -> None:
    async def exercise() -> None:
        engine, session_factory = create_session_factory("sqlite+aiosqlite://")
        async with engine.begin() as connection:
            await connection.run_sync(
                lambda sync_connection: Base.metadata.create_all(
                    sync_connection,
                    tables=[
                        InterviewSessionModel.__table__,
                        InterviewTurnModel.__table__,
                    ],
                )
            )
        repository = SqlAlchemyInterviewRepository(session_factory)
        state = await repository.create_session(
            review_session_id=None,
            profile_id="candidate-2",
            role_context="backend intern",
            questions=_questions(),
        )
        await repository.record_turn(
            InterviewTurnRecord(
                session_id=state.session_id,
                turn_number=1,
                question=_questions()[0],
                answer_sha256="1" * 64,
                answer_summary="Answer length: 80 characters; signals: testing.",
                assessment={
                    "score": 3,
                    "strengths": ["Included verification."],
                    "gaps": ["Explain the tradeoff."],
                    "feedback": "Promising direction.",
                },
                next_question=_questions()[1],
                status="active",
            )
        )

        restored = await repository.get_session(state.session_id)
        turns = await repository.list_turns(state.session_id)
        async with session_factory() as session:
            turn_count = await session.scalar(
                select(func.count()).select_from(InterviewTurnModel)
            )
        assert restored.current_question == _questions()[1]
        assert restored.turn_count == 1
        assert turns[0].assessment.score == 3
        assert turns[0].answer_summary.endswith("signals: testing.")
        assert turn_count == 1
        await engine.dispose()

    asyncio.run(exercise())
