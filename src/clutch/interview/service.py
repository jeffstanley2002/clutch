"""RAG-grounded interview service with privacy-safe deterministic fallback."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from hashlib import sha256
from time import perf_counter

from clutch.interview.contracts import InterviewTurnRecord
from clutch.interview.repository import (
    InterviewRepository,
    interview_repository_from_env,
)
from clutch.knowledge_base import CleanCodePrinciple
from clutch.knowledge_base.clean_code import SEED_CLEAN_CODE_PRINCIPLES
from clutch.llm import InterviewAssessmentContext, ModelRouter
from clutch.observability import (
    OBSERVABILITY,
    Observability,
    update_span_from_provenance,
)
from clutch.persistence.repository import (
    ReviewFindingReader,
    review_finding_reader_from_env,
)
from clutch.rag import KnowledgeRetriever, knowledge_retriever_from_env
from clutch.schemas import (
    FeedbackReport,
    FindingCategory,
    InterviewAssessment,
    InterviewQuestion,
    InterviewStatus,
    InterviewTurnRequest,
    InterviewTurnResponse,
    StageProvenance,
    SupportingFinding,
)

_CORPUS_BY_ID = {
    principle.id: principle for principle in SEED_CLEAN_CODE_PRINCIPLES
}


class InterviewNotComplete(RuntimeError):
    """Raised when final feedback is requested before all questions are answered."""


class InterviewService:
    def __init__(
        self,
        repository: InterviewRepository | None = None,
        review_store: ReviewFindingReader | None = None,
        model_router: ModelRouter | None = None,
        retriever: KnowledgeRetriever | None = None,
        observability: Observability | None = None,
    ) -> None:
        self._repository = repository or interview_repository_from_env()
        self._review_store = review_store or review_finding_reader_from_env()
        self._model_router = model_router or ModelRouter.from_env()
        self._retriever = retriever or knowledge_retriever_from_env()
        self._observability = observability or OBSERVABILITY

    async def run_turn(self, request: InterviewTurnRequest) -> InterviewTurnResponse:
        started_at = perf_counter()
        with self._observability.span(
            "interview.turn",
            as_type="agent",
            input={
                "interview_session_id": request.interview_session_id,
                "review_session_id": request.review_session_id,
                "question_count": len(request.questions),
                "answer_sha256": (
                    sha256(request.answer.encode("utf-8")).hexdigest()
                    if request.answer is not None
                    else None
                ),
            },
        ) as span:
            response = await self._run_turn(request)
            span.update(
                output={
                    "interview_session_id": response.interview_session_id,
                    "status": response.status,
                    "completed": response.completed,
                    "assessment_origin": (
                        response.assessment.origin
                        if response.assessment is not None
                        else None
                    ),
                },
                metadata={
                    "stage_status": "succeeded",
                    "latency_ms": (perf_counter() - started_at) * 1_000,
                },
                level="DEFAULT",
                status_message="succeeded",
            )
            return response

    async def _run_turn(
        self,
        request: InterviewTurnRequest,
    ) -> InterviewTurnResponse:
        if request.interview_session_id is None:
            persistence_started = perf_counter()
            with self._observability.span(
                "interview.persistence",
                input={"operation": "create_session"},
            ) as persistence_span:
                state = await self._repository.create_session(
                    review_session_id=request.review_session_id,
                    profile_id=request.profile_id,
                    role_context=request.role_context,
                    questions=request.questions,
                )
                persistence_span.update(
                    output={"persisted": True},
                    metadata={
                        "stage_status": "succeeded",
                        "latency_ms": (perf_counter() - persistence_started)
                        * 1_000,
                    },
                    level="DEFAULT",
                    status_message="succeeded",
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
        answer_summary = _summarize_answer(answer)
        principles, retrieval_provenance = await self._retrieve_grounding(
            role_context=state.role_context,
            question=state.current_question,
        )
        fallback = _assess_answer_deterministically(
            answer,
            state.current_question,
        ).model_copy(
            update={
                "citations": [principle.citation for principle in principles],
                "origin": "deterministic_static",
            }
        )
        if principles:
            with self._observability.span(
                "interview.assess_answer",
                as_type="generation",
                input={
                    "question_id": state.current_question.id,
                    "answer_sha256": sha256(answer.encode("utf-8")).hexdigest(),
                    "grounding_ids": [principle.id for principle in principles],
                },
                metadata={"prompt_version": "interview_assessment.v1"},
            ) as span:
                result = await self._model_router.assess_interview(
                    InterviewAssessmentContext(
                        role_context=state.role_context,
                        question=state.current_question,
                        answer=answer,
                        answer_signal_summary=answer_summary,
                        principles=principles,
                    ),
                    deterministic_fallback=fallback,
                )
                assessment_provenance = StageProvenance(
                    stage="interview_assessment",
                    status=(
                        "succeeded"
                        if result.assessment.origin == "ai_generated"
                        else "fallback"
                    ),
                    origin=result.assessment.origin,
                    model_name=result.model_name,
                    prompt_version=result.prompt_version,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    latency_ms=result.latency_ms,
                    estimated_cost_usd=result.estimated_cost_usd,
                    attempt_count=result.attempt_count,
                    validation_failure_count=result.validation_failure_count,
                    failure_category=result.failure_category,
                )
                assessment = result.assessment.model_copy(
                    update={"provenance": assessment_provenance}
                )
                update_span_from_provenance(
                    span,
                    assessment_provenance,
                    output={
                        "origin": assessment.origin,
                        "score": assessment.score,
                        "citation_ids": [
                            citation.source_id for citation in assessment.citations
                        ],
                    }
                )
                if assessment_provenance.status == "fallback":
                    with self._observability.span(
                        "interview.fallback",
                        as_type="guardrail",
                    ) as fallback_span:
                        fallback_span.update(
                            output={"origin": assessment.origin},
                            metadata={
                                "failure_category": (
                                    assessment_provenance.failure_category
                                ),
                                "stage_status": "fallback",
                            },
                            level="WARNING",
                            status_message=(
                                assessment_provenance.failure_category
                            ),
                        )
        else:
            assessment_provenance = StageProvenance(
                stage="interview_assessment",
                status="fallback",
                origin="deterministic_static",
                failure_category="retrieval_failed",
            )
            assessment = fallback.model_copy(
                update={"provenance": assessment_provenance}
            )
            with self._observability.span(
                "interview.fallback",
                as_type="guardrail",
            ) as fallback_span:
                fallback_span.update(
                    output={"origin": assessment.origin},
                    metadata={
                        "failure_category": "retrieval_failed",
                        "stage_status": "fallback",
                    },
                    level="WARNING",
                    status_message="retrieval_failed",
                )
        provenance = [retrieval_provenance, assessment_provenance]
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
        persistence_started = perf_counter()
        with self._observability.span(
            "interview.persistence",
            input={
                "interview_session_id": state.session_id,
                "operation": "record_turn",
            },
        ) as persistence_span:
            await self._repository.record_turn(
                InterviewTurnRecord(
                    session_id=state.session_id,
                    turn_number=turn_number,
                    question=state.current_question,
                    answer_sha256=sha256(answer.encode("utf-8")).hexdigest(),
                    answer_summary=answer_summary,
                    assessment=assessment,
                    provenance=provenance,
                    next_question=next_question,
                    remaining_questions=remaining,
                    status=status,
                )
            )
            persistence_span.update(
                output={"persisted": True, "status": status},
                metadata={
                    "stage_status": "succeeded",
                    "latency_ms": (perf_counter() - persistence_started) * 1_000,
                },
                level="DEFAULT",
                status_message="succeeded",
            )
        return InterviewTurnResponse(
            interview_session_id=state.session_id,
            status=status,
            turn_number=turn_number + (1 if next_question is not None else 0),
            question=next_question,
            assessment=assessment,
            provenance=provenance,
            completed=status == "completed",
        )

    async def _retrieve_grounding(
        self,
        *,
        role_context: str,
        question: InterviewQuestion,
    ) -> tuple[list[CleanCodePrinciple], StageProvenance]:
        """Retrieve up to three public rubric/reference items without the answer."""

        category = _question_category(question)
        cited = [
            principle
            for citation in question.citations
            if (principle := _CORPUS_BY_ID.get(citation.source_id)) is not None
            and principle.item_type in {"reference", "rubric"}
        ]
        query = " ".join(
            [
                role_context,
                "rubric reference interview assessment",
                category or "",
                question.question,
                question.intent,
                *(citation.title for citation in question.citations),
            ]
        )
        started_at = perf_counter()
        with self._observability.span(
            "interview.retrieve_grounding",
            as_type="retriever",
            input={
                "question_id": question.id,
                "category": category,
                "cited_source_ids": [
                    citation.source_id for citation in question.citations
                ],
            },
        ) as span:
            try:
                retrieved = await self._retriever.retrieve(
                    query,
                    categories={category} if category is not None else None,
                    limit=3,
                )
                candidates = [*cited, *retrieved]
                principles = list(
                    {
                        principle.id: principle
                        for principle in candidates
                        if principle.item_type in {"reference", "rubric"}
                    }.values()
                )[:3]
                provenance = StageProvenance(
                    stage="interview_retrieval",
                    status="succeeded" if principles else "failed",
                    origin="retrieved_citation",
                    latency_ms=(perf_counter() - started_at) * 1_000,
                    failure_category=None if principles else "retrieval_failed",
                )
            except Exception:
                principles = list({item.id: item for item in cited}.values())[:3]
                provenance = StageProvenance(
                    stage="interview_retrieval",
                    status="succeeded" if principles else "failed",
                    origin="retrieved_citation",
                    latency_ms=(perf_counter() - started_at) * 1_000,
                    failure_category=None if principles else "retrieval_failed",
                )
            update_span_from_provenance(
                span,
                provenance,
                output={
                    "knowledge_source_ids": [
                        principle.id for principle in principles
                    ],
                    "status": provenance.status,
                    "failure_category": provenance.failure_category,
                }
            )
        return principles, provenance

    async def generate_feedback(self, session_id: str) -> FeedbackReport:
        started_at = perf_counter()
        with self._observability.span(
            "interview.final_aggregation",
            input={"interview_session_id": session_id},
        ) as span:
            report = await self._generate_feedback(session_id)
            span.update(
                output={
                    "strength_count": len(report.strengths),
                    "recurring_issue_count": len(report.recurring_issues),
                    "recommended_task_count": len(report.recommended_tasks),
                    "aggregation_label": report.aggregation_label,
                },
                metadata={
                    "stage_status": "succeeded",
                    "origin": "deterministic_static",
                    "latency_ms": (perf_counter() - started_at) * 1_000,
                },
                level="DEFAULT",
                status_message="succeeded",
            )
            return report

    async def _generate_feedback(self, session_id: str) -> FeedbackReport:
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
                    origin=finding.origin,
                )
                for finding in findings[:5]
            ],
            aggregation_label=_aggregation_label(turns),
        )


def _assess_answer_deterministically(
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
        origin="deterministic_static",
    )


def _question_category(
    question: InterviewQuestion,
) -> FindingCategory | None:
    for citation in question.citations:
        principle = _CORPUS_BY_ID.get(citation.source_id)
        if principle is not None:
            return principle.category
    text = f"{question.intent} {question.question}".lower()
    for category in (
        "maintainability",
        "readability",
        "correctness",
        "testing",
        "design",
        "security",
    ):
        if category in text:
            return category
    return None


def _aggregation_label(turns: Iterable[object]) -> str:
    origins = {
        getattr(getattr(turn, "assessment", None), "origin", None)
        for turn in turns
    }
    if origins == {"ai_generated"}:
        return "Rule-based report aggregation from AI-assessed turns."
    if "ai_generated" in origins:
        return "Rule-based report aggregation from AI and rule-based turns."
    return "Rule-based report aggregation from rule-based assessed turns."


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
