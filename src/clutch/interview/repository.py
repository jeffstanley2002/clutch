"""In-memory and SQLAlchemy repositories for interview state."""

from __future__ import annotations

from typing import Protocol, cast
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from clutch.interview.contracts import (
    InterviewSessionState,
    InterviewTurnEvidence,
    InterviewTurnRecord,
)
from clutch.persistence.database import application_session_factory_from_env
from clutch.persistence.models import (
    AgentRunModel,
    InterviewSessionModel,
    InterviewTurnModel,
)
from clutch.schemas import InterviewAssessment, InterviewQuestion, InterviewStatus


class InterviewSessionNotFound(LookupError):
    """Raised when a requested interview session does not exist."""


class InterviewRepository(Protocol):
    async def create_session(
        self,
        *,
        review_session_id: str | None,
        profile_id: str | None,
        role_context: str,
        questions: list[InterviewQuestion],
    ) -> InterviewSessionState: ...

    async def get_session(self, session_id: str) -> InterviewSessionState: ...

    async def record_turn(self, record: InterviewTurnRecord) -> None: ...

    async def list_turns(self, session_id: str) -> list[InterviewTurnEvidence]: ...


class InMemoryInterviewRepository:
    """Process-local state for a runnable setup without PostgreSQL."""

    def __init__(self) -> None:
        self.sessions: dict[str, InterviewSessionState] = {}
        self.turns: list[InterviewTurnRecord] = []

    async def create_session(
        self,
        *,
        review_session_id: str | None,
        profile_id: str | None,
        role_context: str,
        questions: list[InterviewQuestion],
    ) -> InterviewSessionState:
        state = InterviewSessionState(
            session_id=str(uuid4()),
            review_session_id=review_session_id,
            profile_id=profile_id,
            role_context=role_context,
            current_question=questions[0],
            remaining_questions=questions[1:],
        )
        self.sessions[state.session_id] = state
        return state.model_copy(deep=True)

    async def get_session(self, session_id: str) -> InterviewSessionState:
        state = self.sessions.get(session_id)
        if state is None:
            raise InterviewSessionNotFound(session_id)
        return state.model_copy(deep=True)

    async def record_turn(self, record: InterviewTurnRecord) -> None:
        state = self.sessions.get(record.session_id)
        if state is None:
            raise InterviewSessionNotFound(record.session_id)
        self.turns.append(record.model_copy(deep=True))
        state.current_question = record.next_question
        state.remaining_questions = record.remaining_questions
        state.turn_count = record.turn_number
        state.status = record.status

    async def list_turns(self, session_id: str) -> list[InterviewTurnEvidence]:
        if session_id not in self.sessions:
            raise InterviewSessionNotFound(session_id)
        return [
            InterviewTurnEvidence(
                turn_number=turn.turn_number,
                answer_summary=turn.answer_summary,
                assessment=InterviewAssessment.model_validate(turn.assessment),
            )
            for turn in self.turns
            if turn.session_id == session_id
        ]


class SqlAlchemyInterviewRepository:
    """Persist interview state and privacy-reduced answer records."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_factory = session_factory

    async def create_session(
        self,
        *,
        review_session_id: str | None,
        profile_id: str | None,
        role_context: str,
        questions: list[InterviewQuestion],
    ) -> InterviewSessionState:
        state = InterviewSessionState(
            session_id=str(uuid4()),
            review_session_id=review_session_id,
            profile_id=profile_id,
            role_context=role_context,
            current_question=questions[0],
            remaining_questions=questions[1:],
        )
        model = InterviewSessionModel(
            id=state.session_id,
            review_session_id=state.review_session_id,
            profile_id=state.profile_id,
            role_context=state.role_context,
            status=state.status,
            current_question=questions[0].model_dump(mode="json"),
            remaining_questions=[
                question.model_dump(mode="json")
                for question in state.remaining_questions
            ],
            turn_count=0,
        )
        async with self._session_factory() as session:
            session.add(model)
            await session.commit()
        return state

    async def get_session(self, session_id: str) -> InterviewSessionState:
        async with self._session_factory() as session:
            model = await session.get(InterviewSessionModel, session_id)
        if model is None:
            raise InterviewSessionNotFound(session_id)
        return _state_from_model(model)

    async def record_turn(self, record: InterviewTurnRecord) -> None:
        async with self._session_factory() as session:
            model = await session.get(InterviewSessionModel, record.session_id)
            if model is None:
                raise InterviewSessionNotFound(record.session_id)
            turn_id = str(uuid4())
            session.add(
                InterviewTurnModel(
                    id=turn_id,
                    interview_session_id=record.session_id,
                    turn_number=record.turn_number,
                    question=record.question.question,
                    answer_sha256=record.answer_sha256,
                    answer_summary=record.answer_summary,
                    assessment=record.assessment.model_dump(mode="json"),
                    assessment_origin=record.assessment.origin,
                )
            )
            session.add_all(
                [
                    AgentRunModel(
                        id=str(uuid4()),
                        review_session_id=model.review_session_id,
                        workflow=f"interview.{stage.stage}",
                        mode=stage.origin,
                        status=stage.status,
                        model_name=stage.model_name,
                        input_tokens=stage.input_tokens,
                        output_tokens=stage.output_tokens,
                        estimated_cost_usd=stage.estimated_cost_usd,
                        latency_ms=stage.latency_ms,
                        prompt_version=stage.prompt_version,
                        attempt_count=stage.attempt_count,
                        validation_failure_count=stage.validation_failure_count,
                        failure_category=stage.failure_category,
                    )
                    for stage in record.provenance
                ]
            )
            model.current_question = (
                record.next_question.model_dump(mode="json")
                if record.next_question is not None
                else None
            )
            model.remaining_questions = [
                question.model_dump(mode="json")
                for question in record.remaining_questions
            ]
            model.turn_count = record.turn_number
            model.status = record.status
            await session.commit()

    async def list_turns(self, session_id: str) -> list[InterviewTurnEvidence]:
        async with self._session_factory() as session:
            exists = await session.get(InterviewSessionModel, session_id)
            if exists is None:
                raise InterviewSessionNotFound(session_id)
            result = await session.scalars(
                select(InterviewTurnModel)
                .where(InterviewTurnModel.interview_session_id == session_id)
                .order_by(InterviewTurnModel.turn_number)
            )
            turns = list(result)
        return [
            InterviewTurnEvidence(
                turn_number=turn.turn_number,
                answer_summary=turn.answer_summary,
                assessment=InterviewAssessment.model_validate(turn.assessment),
            )
            for turn in turns
        ]


def interview_repository_from_env() -> InterviewRepository:
    session_factory = application_session_factory_from_env()
    if session_factory is None:
        return InMemoryInterviewRepository()
    return SqlAlchemyInterviewRepository(session_factory)


def _state_from_model(model: InterviewSessionModel) -> InterviewSessionState:
    return InterviewSessionState(
        session_id=model.id,
        review_session_id=model.review_session_id,
        profile_id=model.profile_id,
        role_context=model.role_context,
        status=cast(InterviewStatus, model.status),
        current_question=(
            InterviewQuestion.model_validate(model.current_question)
            if model.current_question is not None
            else None
        ),
        remaining_questions=[
            InterviewQuestion.model_validate(question)
            for question in model.remaining_questions
        ],
        turn_count=model.turn_count,
    )
