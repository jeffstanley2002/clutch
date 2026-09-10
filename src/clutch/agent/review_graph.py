"""LangGraph spine for the pasted-code review workflow."""

from time import perf_counter
from typing import Literal, NotRequired, TypedDict, cast

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from clutch.knowledge_base import CleanCodePrinciple
from clutch.llm import ModelRouter, QuestionContext, ReviewContext
from clutch.observability import (
    OBSERVABILITY,
    Observability,
    update_span_from_provenance,
)
from clutch.parsing import parse_python_code
from clutch.rag import (
    KnowledgeRetriever,
    build_retrieval_query,
    knowledge_retriever_from_env,
)
from clutch.review.static import run_static_review
from clutch.schemas import (
    Citation,
    CodeFinding,
    InterviewQuestion,
    ParsedCode,
    ReviewMode,
    ReviewRequest,
    StageProvenance,
)


class ReviewGraphState(TypedDict):
    """Typed state passed between review graph nodes."""

    request: ReviewRequest
    parsed_code: NotRequired[ParsedCode]
    static_findings: NotRequired[list[CodeFinding]]
    retrieved_principles: NotRequired[list[CleanCodePrinciple]]
    findings: NotRequired[list[CodeFinding]]
    questions: NotRequired[list[InterviewQuestion]]
    mode: NotRequired[ReviewMode]
    confidence: NotRequired[float]
    model_name: NotRequired[str | None]
    input_tokens: NotRequired[int | None]
    output_tokens: NotRequired[int | None]
    attempt_count: NotRequired[int]
    validation_failure_count: NotRequired[int]
    retrieval_provenance: NotRequired[StageProvenance]
    review_provenance: NotRequired[StageProvenance]
    question_provenance: NotRequired[StageProvenance]


def parse_code(state: ReviewGraphState) -> dict[str, ParsedCode]:
    """Parse untrusted source as data and attach line-aware structure."""

    request = state["request"]
    return {"parsed_code": parse_python_code(request.code)}


def static_review(state: ReviewGraphState) -> dict[str, list[CodeFinding]]:
    """Run deterministic checks that remain available without an API key."""

    return {
        "static_findings": run_static_review(
            state["request"], parsed_code=state["parsed_code"]
        )
    }


async def retrieve_principles(
    state: ReviewGraphState,
    *,
    retriever: KnowledgeRetriever,
) -> dict[str, object]:
    """Retrieve grounding material for the current findings and role."""

    request = state["request"]
    findings = state["static_findings"]
    retrieval_query = build_retrieval_query(request, findings)
    started_at = perf_counter()
    try:
        principles = await retriever.retrieve(
            retrieval_query.text,
            categories=(
                set(retrieval_query.categories)
                if retrieval_query.categories is not None
                else None
            ),
            limit=retrieval_query.limit,
        )
        provenance = StageProvenance(
            stage="retrieval",
            status="succeeded",
            origin="retrieved_citation",
            latency_ms=(perf_counter() - started_at) * 1_000,
        )
    except Exception:
        # Retrieval adapters own their availability fallback. Reaching this branch
        # means both the configured path and its fallback failed.
        principles = []
        provenance = StageProvenance(
            stage="retrieval",
            status="failed",
            origin="retrieved_citation",
            latency_ms=(perf_counter() - started_at) * 1_000,
            failure_category="retrieval_failed",
        )
    return {
        "retrieved_principles": principles,
        "retrieval_provenance": provenance,
    }


async def synthesize_review(
    state: ReviewGraphState, *, model_router: ModelRouter
) -> dict[str, object]:
    """Run structured model synthesis through the configured AI provider."""

    citations_by_category: dict[str, list[Citation]] = {}
    for principle in state["retrieved_principles"]:
        citations_by_category.setdefault(principle.category, []).append(
            principle.citation
        )

    grounded_findings = []
    for finding in state["static_findings"]:
        if finding.citations:
            grounded_findings.append(finding)
            continue
        grounded_findings.append(
            finding.model_copy(
                update={
                    "citations": citations_by_category.get(finding.category, [])[:1]
                }
            )
        )

    result = await model_router.review(
        ReviewContext(
            request=state["request"],
            parsed_code=state["parsed_code"],
            static_findings=grounded_findings,
            principles=state["retrieved_principles"],
        )
    )
    findings = [
        finding.model_copy(
            update={
                "origin": (
                    "ai_generated"
                    if result.mode == "model"
                    else "deterministic_static"
                )
            }
        )
        for finding in result.findings
    ]
    return {
        "findings": findings,
        "mode": result.mode,
        "confidence": result.confidence,
        "model_name": result.model_name,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "attempt_count": result.attempt_count,
        "validation_failure_count": result.validation_failure_count,
        "review_provenance": StageProvenance(
            stage="review_synthesis",
            status="succeeded" if result.mode == "model" else "fallback",
            origin=(
                "ai_generated"
                if result.mode == "model"
                else "deterministic_static"
            ),
            model_name=result.model_name,
            prompt_version=result.prompt_version,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=result.latency_ms,
            estimated_cost_usd=result.estimated_cost_usd,
            attempt_count=result.attempt_count,
            validation_failure_count=result.validation_failure_count,
            failure_category=result.failure_category,
        ),
    }


def validate_findings(state: ReviewGraphState) -> dict[str, list[CodeFinding]]:
    """Revalidate graph output and reject impossible source locations."""

    line_count = max(1, len(state["request"].code.splitlines()))
    validated = []
    for finding in state["findings"]:
        finding = CodeFinding.model_validate(finding.model_dump())
        if finding.line_start is not None and finding.line_start > line_count:
            raise ValueError("finding line_start exceeds submitted source")
        if finding.line_end is not None and finding.line_end > line_count:
            raise ValueError("finding line_end exceeds submitted source")
        if (
            finding.line_start is not None
            and finding.line_end is not None
            and finding.line_end < finding.line_start
        ):
            raise ValueError("finding line_end precedes line_start")
        validated.append(finding)
    return {"findings": validated}


async def generate_questions(
    state: ReviewGraphState,
    *,
    model_router: ModelRouter,
) -> dict[str, object]:
    """Generate grounded questions with an honestly labeled template fallback."""

    role = state["request"].role_context
    findings = state["findings"][:3]
    template_questions = [
        InterviewQuestion(
            id=f"question-{index:03d}",
            finding_id=finding.id,
            question=(
                f"For a {role} interview, how would you improve this issue: "
                f"{finding.message.lower()}? Explain the tradeoffs in your approach."
            ),
            intent=(
                f"Assess whether the candidate can reason about {finding.category} "
                "and turn review feedback into a concrete engineering decision."
            ),
            difficulty=_question_difficulty(finding),
            citations=finding.citations,
        )
        for index, finding in enumerate(findings, start=1)
    ]
    if not findings:
        return {
            "questions": [],
            "question_provenance": StageProvenance(
                stage="question_generation",
                status="skipped",
                origin="template_generated",
            ),
        }
    result = await model_router.generate_questions(
        QuestionContext(
            role_context=role,
            findings=findings,
            principles=state["retrieved_principles"][:8],
        ),
        template_questions=template_questions,
    )
    ai_generated = all(
        question.origin == "ai_generated" for question in result.questions
    )
    return {
        "questions": result.questions,
        "question_provenance": StageProvenance(
            stage="question_generation",
            status="succeeded" if ai_generated else "fallback",
            origin="ai_generated" if ai_generated else "template_generated",
            model_name=result.model_name,
            prompt_version=result.prompt_version,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=result.latency_ms,
            estimated_cost_usd=result.estimated_cost_usd,
            attempt_count=result.attempt_count,
            validation_failure_count=result.validation_failure_count,
            failure_category=result.failure_category,
        ),
    }


def _question_difficulty(
    finding: CodeFinding,
) -> Literal["easy", "medium", "hard"]:
    if finding.severity == "high":
        return "hard"
    if finding.severity == "medium":
        return "medium"
    return "easy"


def build_review_graph(
    model_router: ModelRouter | None = None,
    retriever: KnowledgeRetriever | None = None,
    observability: Observability | None = None,
) -> CompiledStateGraph:
    """Compile the linear review workflow once at import time."""

    router = model_router or ModelRouter.from_env()
    knowledge_retriever = retriever or knowledge_retriever_from_env()
    observer = observability or OBSERVABILITY

    def parse_code_node(state: ReviewGraphState) -> dict[str, ParsedCode]:
        request = state["request"]
        with observer.span(
            "review.parse_code",
            input={
                "language": request.language,
                "line_count": len(request.code.splitlines()),
            },
        ) as span:
            result = parse_code(state)
            span.update(
                output={
                    "chunk_count": len(result["parsed_code"].chunks),
                    "has_syntax_error": result["parsed_code"].has_syntax_error,
                },
                metadata={"stage_status": "succeeded"},
                level="DEFAULT",
                status_message="succeeded",
            )
            return result

    def static_review_node(
        state: ReviewGraphState,
    ) -> dict[str, list[CodeFinding]]:
        with observer.span("review.static_review", as_type="tool") as span:
            result = static_review(state)
            span.update(
                output={
                    "finding_categories": [
                        finding.category for finding in result["static_findings"]
                    ]
                },
                metadata={"stage_status": "succeeded"},
                level="DEFAULT",
                status_message="succeeded",
            )
            return result

    async def retrieve_principles_node(
        state: ReviewGraphState,
    ) -> dict[str, object]:
        with observer.span("review.retrieve_principles", as_type="retriever") as span:
            result = await retrieve_principles(
                state,
                retriever=knowledge_retriever,
            )
            principles = cast(
                list[CleanCodePrinciple], result["retrieved_principles"]
            )
            provenance = cast(StageProvenance, result["retrieval_provenance"])
            update_span_from_provenance(
                span,
                provenance,
                output={
                    "knowledge_source_ids": [
                        principle.id for principle in principles
                    ]
                }
            )
            return result

    async def synthesize_review_node(
        state: ReviewGraphState,
    ) -> dict[str, object]:
        with observer.span(
            "review.synthesize",
            as_type="generation",
        ) as span:
            result = await synthesize_review(state, model_router=router)
            findings = result["findings"]
            assert isinstance(findings, list)
            provenance = cast(StageProvenance, result["review_provenance"])
            update_span_from_provenance(
                span,
                provenance,
                output={
                    "mode": result["mode"],
                    "finding_count": len(findings),
                }
            )
            if provenance.status == "fallback":
                with observer.span(
                    "review.fallback",
                    as_type="guardrail",
                ) as fallback_span:
                    fallback_span.update(
                        output={"mode": result["mode"]},
                        metadata={
                            "failure_category": provenance.failure_category,
                            "stage_status": "fallback",
                        },
                        level="WARNING",
                        status_message=provenance.failure_category,
                    )
            return result

    def validate_findings_node(
        state: ReviewGraphState,
    ) -> dict[str, list[CodeFinding]]:
        with observer.span("review.validate_findings", as_type="guardrail") as span:
            result = validate_findings(state)
            span.update(
                output={"validated_finding_count": len(result["findings"])},
                metadata={"stage_status": "succeeded"},
                level="DEFAULT",
                status_message="succeeded",
            )
            return result

    async def generate_questions_node(
        state: ReviewGraphState,
    ) -> dict[str, object]:
        with observer.span(
            "review.generate_questions",
            as_type="generation",
        ) as span:
            result = await generate_questions(state, model_router=router)
            questions = cast(list[InterviewQuestion], result["questions"])
            provenance = cast(StageProvenance, result["question_provenance"])
            update_span_from_provenance(
                span,
                provenance,
                output={
                    "question_count": len(questions),
                    "origin": provenance.origin,
                }
            )
            if provenance.status == "fallback":
                with observer.span(
                    "questions.fallback",
                    as_type="guardrail",
                ) as fallback_span:
                    fallback_span.update(
                        output={"question_count": len(questions)},
                        metadata={
                            "failure_category": provenance.failure_category,
                            "stage_status": "fallback",
                        },
                        level="WARNING",
                        status_message=provenance.failure_category,
                    )
            return result

    builder = StateGraph(ReviewGraphState)
    builder.add_node("parse_code", parse_code_node)
    builder.add_node("static_review", static_review_node)
    builder.add_node("retrieve_principles", retrieve_principles_node)
    builder.add_node("synthesize_review", synthesize_review_node)
    builder.add_node("validate_findings", validate_findings_node)
    builder.add_node("generate_questions", generate_questions_node)
    builder.add_edge(START, "parse_code")
    builder.add_edge("parse_code", "static_review")
    builder.add_edge("static_review", "retrieve_principles")
    builder.add_edge("retrieve_principles", "synthesize_review")
    builder.add_edge("synthesize_review", "validate_findings")
    builder.add_edge("validate_findings", "generate_questions")
    builder.add_edge("generate_questions", END)
    return builder.compile()


REVIEW_GRAPH = build_review_graph()
