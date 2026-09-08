"""LangGraph spine for the pasted-code review workflow."""

import os
from typing import Literal, NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from clutch.knowledge_base import CleanCodePrinciple
from clutch.llm import ModelRouter, ReviewContext
from clutch.observability import OBSERVABILITY, Observability
from clutch.parsing import parse_python_code
from clutch.rag import (
    KnowledgeRetriever,
    extract_code_retrieval_terms,
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
    fallback_reason: NotRequired[str | None]


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
) -> dict[str, list[CleanCodePrinciple]]:
    """Retrieve grounding material for the current findings and role."""

    request = state["request"]
    findings = state["static_findings"]
    if findings:
        query = " ".join(
            [
                request.role_context,
                "rubric question interview",
                *(finding.message for finding in findings),
                *(finding.category for finding in findings),
            ]
        )
    else:
        code_terms = extract_code_retrieval_terms(request.code)
        query = " ".join(
            [
                request.role_context,
                "rubric",
                "maintainability readability correctness testing design security",
                *code_terms,
            ]
        )
    principles = await retriever.retrieve(
        query,
        categories={finding.category for finding in findings} or None,
        limit=max(3, sum(len(finding.citations) for finding in findings)),
    )
    return {"retrieved_principles": principles}


async def synthesize_review(
    state: ReviewGraphState, *, model_router: ModelRouter
) -> dict[str, object]:
    """Run structured model synthesis or the deterministic fallback."""

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
                update={"citations": citations_by_category.get(finding.category, [])}
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
    return {
        "findings": result.findings,
        "mode": result.mode,
        "confidence": result.confidence,
        "model_name": result.model_name,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "fallback_reason": result.fallback_reason,
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


def generate_questions(
    state: ReviewGraphState,
) -> dict[str, list[InterviewQuestion]]:
    """Turn the most useful findings into deterministic interview prompts."""

    role = state["request"].role_context
    questions = [
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
        for index, finding in enumerate(state["findings"][:3], start=1)
    ]
    return {"questions": questions}


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
                }
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
                }
            )
            return result

    async def retrieve_principles_node(
        state: ReviewGraphState,
    ) -> dict[str, list[CleanCodePrinciple]]:
        with observer.span("review.retrieve_principles", as_type="retriever") as span:
            result = await retrieve_principles(
                state,
                retriever=knowledge_retriever,
            )
            span.update(
                output={
                    "knowledge_source_ids": [
                        principle.id for principle in result["retrieved_principles"]
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
            metadata={"configured_model": os.getenv("OPENAI_MODEL", "gpt-5.4-mini")},
        ) as span:
            result = await synthesize_review(state, model_router=router)
            findings = result["findings"]
            assert isinstance(findings, list)
            span.update(
                output={
                    "mode": result["mode"],
                    "finding_count": len(findings),
                    "model_name": result["model_name"],
                    "input_tokens": result["input_tokens"],
                    "output_tokens": result["output_tokens"],
                    "fallback_reason": result["fallback_reason"],
                }
            )
            return result

    def validate_findings_node(
        state: ReviewGraphState,
    ) -> dict[str, list[CodeFinding]]:
        with observer.span("review.validate_findings", as_type="guardrail") as span:
            result = validate_findings(state)
            span.update(output={"validated_finding_count": len(result["findings"])})
            return result

    def generate_questions_node(
        state: ReviewGraphState,
    ) -> dict[str, list[InterviewQuestion]]:
        with observer.span("review.generate_questions", as_type="tool") as span:
            result = generate_questions(state)
            span.update(output={"question_count": len(result["questions"])})
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
