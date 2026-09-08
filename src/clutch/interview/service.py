"""Deterministic multi-turn interview service with privacy-safe persistence."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from hashlib import sha256

from clutch.interview.contracts import InterviewTurnRecord
from clutch.interview.repository import (
    InterviewRepository,
    interview_repository_from_env,
)
from clutch.persistence.repository import (
    ReviewFindingReader,
    review_finding_reader_from_env,
)
from clutch.schemas import (
    FeedbackReport,
    InterviewAssessment,
    InterviewQuestion,
    InterviewStatus,
    InterviewTurnRequest,
    InterviewTurnResponse,
    SupportingFinding,
)


class InterviewNotComplete(RuntimeError):
    """Raised when final feedback is requested before all questions are answered."""


class InterviewService:
    def __init__(
        self,
        repository: InterviewRepository | None = None,
        review_store: ReviewFindingReader | None = None,
    ) -> None:
        self._repository = repository or interview_repository_from_env()
        self._review_store = review_store or review_finding_reader_from_env()

    async def run_turn(self, request: InterviewTurnRequest) -> InterviewTurnResponse:
        if request.interview_session_id is None:
            state = await self._repository.create_session(
                review_session_id=request.review_session_id,
                profile_id=request.profile_id,
                role_context=request.role_context,
                questions=request.questions,
            )
            return InterviewTurnResponse(
                interview_session_id=state.session_id,
                status=state.status,
                turn_number=1,
                question=state.current_question,
                completed=False,
            )

        state = await self._repository.get_session(request.interview_session_id)
        if state.current_question is None or state.status == "completed":
            return InterviewTurnResponse(
                interview_session_id=state.session_id,
                status="completed",
                turn_number=max(1, state.turn_count),
                completed=True,
            )

        answer = (request.answer or "").strip()
        assessment = _assess_answer(answer, state.current_question)
        next_question = (
            state.remaining_questions[0] if state.remaining_questions else None
        )
        remaining = (
            state.remaining_questions[1:] if state.remaining_questions else []
        )
        turn_number = state.turn_count + 1
        status: InterviewStatus = (
            "active" if next_question is not None else "completed"
        )
        await self._repository.record_turn(
            InterviewTurnRecord(
                session_id=state.session_id,
                turn_number=turn_number,
                question=state.current_question,
                answer_sha256=sha256(answer.encode("utf-8")).hexdigest(),
                answer_summary=_summarize_answer(answer),
                assessment=assessment,
                next_question=next_question,
                remaining_questions=remaining,
                status=status,
            )
        )
        return InterviewTurnResponse(
            interview_session_id=state.session_id,
            status=status,
            turn_number=turn_number + (1 if next_question is not None else 0),
            question=next_question,
            assessment=assessment,
            completed=status == "completed",
        )

    async def generate_feedback(self, session_id: str) -> FeedbackReport:
        state = await self._repository.get_session(session_id)
        if state.status != "completed":
            raise InterviewNotComplete(session_id)

        turns = await self._repository.list_turns(session_id)
        strengths = _rank_signals(
            signal
            for turn in turns
            for signal in turn.assessment.strengths
        )
        gap_counts = Counter(
            signal for turn in turns for signal in turn.assessment.gaps
        )
        recurring_issues = [
            signal
            for signal, count in sorted(
                gap_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )
            if count >= 2
        ]
        recommended_tasks = _recommended_tasks(gap_counts)
        findings = (
            await self._review_store.get_findings(state.review_session_id)
            if state.review_session_id is not None
            else []
        )
        scores = [turn.assessment.score for turn in turns]
        average_score = sum(scores) / len(scores) if scores else 0.0

        return FeedbackReport(
            session_id=session_id,
            strengths=strengths[:5],
            recurring_issues=recurring_issues[:5],
            recommended_tasks=recommended_tasks[:5],
            interview_readiness_summary=_readiness_summary(
                average_score=average_score,
                turn_count=len(turns),
            ),
            supporting_findings=[
                SupportingFinding(
                    id=finding.finding_id,
                    severity=finding.severity,
                    category=finding.category,
                    message=finding.message,
                    explanation=finding.explanation,
                    suggestion=finding.suggestion,
                    line_start=finding.line_start,
                    line_end=finding.line_end,
                    citation_ids=finding.citation_ids,
                )
                for finding in findings[:5]
            ],
        )


def _assess_answer(
    answer: str,
    question: InterviewQuestion,
) -> InterviewAssessment:
    normalized = answer.lower()
    strengths: list[str] = []
    gaps: list[str] = []
    score = 1

    if len(answer.split()) >= 20:
        score += 1
        strengths.append("Explained the approach with useful detail.")
    else:
        gaps.append("Explain the reasoning in more depth.")
    if any(term in normalized for term in ("tradeoff", "because", "however")):
        score += 1
        strengths.append("Made the decision rationale explicit.")
    else:
        gaps.append("Name at least one tradeoff behind the decision.")
    if any(term in normalized for term in ("test", "edge case", "verify")):
        score += 1
        strengths.append("Included a way to verify the change.")
    else:
        gaps.append("Describe how tests or edge cases would verify the change.")
    rubric_aliases = {
        "correctness": ("correct", "failure", "exception"),
        "design": ("design", "boundary", "responsibility"),
        "maintainability": ("maintain", "helper", "readable"),
        "readability": ("readable", "naming", "clear"),
        "security": ("secure", "untrusted", "validate"),
        "testing": ("test", "verify", "edge case"),
    }
    intent = question.intent.lower()
    matches_intent = any(
        category in intent and any(alias in normalized for alias in aliases)
        for category, aliases in rubric_aliases.items()
    )
    if matches_intent:
        score += 1
        strengths.append("Connected the answer to the interviewer’s intent.")

    bounded_score = min(score, 5)
    return InterviewAssessment(
        score=bounded_score,
        strengths=strengths,
        gaps=gaps,
        feedback=(
            "Strong interview answer with concrete reasoning."
            if bounded_score >= 4
            else "Promising direction; make the tradeoff and verification plan explicit."
        ),
    )


def _summarize_answer(answer: str) -> str:
    normalized = answer.lower()
    signals = [
        label
        for label, terms in (
            ("tradeoffs", ("tradeoff", "however")),
            ("testing", ("test", "verify", "edge case")),
            ("failure handling", ("error", "exception", "failure")),
            ("maintainability", ("maintain", "readable", "helper")),
        )
        if any(term in normalized for term in terms)
    ]
    signal_text = ", ".join(signals) if signals else "no rubric signals"
    return f"Answer length: {len(answer)} characters; signals: {signal_text}."


def _rank_signals(signals: Iterable[str]) -> list[str]:
    values = list(signals)
    counts = Counter(values)
    first_seen = {value: index for index, value in enumerate(values)}
    return sorted(counts, key=lambda value: (-counts[value], first_seen[value]))


def _recommended_tasks(gap_counts: Counter[str]) -> list[str]:
    task_by_gap = {
        "Explain the reasoning in more depth.": (
            "Practice a 60-second answer that states the change, why it works, "
            "and the expected outcome."
        ),
        "Name at least one tradeoff behind the decision.": (
            "For the next review, name one rejected alternative and the tradeoff "
            "that made you choose your approach."
        ),
        "Describe how tests or edge cases would verify the change.": (
            "Write a verification matrix covering the happy path, failure path, "
            "and one edge case before answering."
        ),
    }
    ordered_gaps = sorted(gap_counts, key=lambda gap: (-gap_counts[gap], gap))
    tasks = [
        task_by_gap.get(
            gap,
            f"Rehearse a concrete example that addresses: {gap.rstrip('.')}",
        )
        for gap in ordered_gaps
    ]
    if tasks:
        return tasks
    return [
        "Repeat one answer under a two-minute limit while preserving the decision, "
        "tradeoff, and verification plan."
    ]


def _readiness_summary(*, average_score: float, turn_count: int) -> str:
    evidence = (
        f"Average assessment {average_score:.1f}/5 across {turn_count} "
        f"completed {'turn' if turn_count == 1 else 'turns'}."
    )
    if average_score >= 4:
        return f"Ready to explain the reviewed decisions with concrete reasoning. {evidence}"
    if average_score >= 3:
        return f"Developing interview readiness; tighten the listed practice areas. {evidence}"
    return f"More practice is needed before relying on these explanations. {evidence}"


interview_service = InterviewService()
