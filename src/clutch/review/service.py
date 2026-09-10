"""Application service for review orchestration and response metadata."""

from collections.abc import Sequence
from hashlib import sha256
from time import perf_counter
from uuid import uuid4

from langgraph.graph.state import CompiledStateGraph

from clutch.agent import REVIEW_GRAPH
from clutch.observability import OBSERVABILITY, Observability, flush_observability
from clutch.persistence import (
    ReviewRecorder,
    build_review_persistence_record,
    review_recorder_from_env,
)
from clutch.schemas import (
    Citation,
    CodeFinding,
    ReviewRequest,
    ReviewResponse,
    StageProvenance,
)


class ReviewService:
    """Run the review graph behind a stable API-facing boundary."""

    def __init__(
        self,
        graph: CompiledStateGraph | None = None,
        recorder: ReviewRecorder | None = None,
        observability: Observability | None = None,
    ) -> None:
        self._graph = graph or REVIEW_GRAPH
        self._recorder = recorder or review_recorder_from_env()
        self._observability = observability or OBSERVABILITY

    async def review(self, request: ReviewRequest) -> ReviewResponse:
        started_at = perf_counter()
        with self._observability.span(
            "review.request",
            as_type="agent",
            input={
                "language": request.language,
                "line_count": len(request.code.splitlines()),
                "source_sha256": sha256(request.code.encode("utf-8")).hexdigest(),
                "role_context": request.role_context,
            },
            metadata={"session_id": request.session_id},
        ) as span:
            state = await self._graph.ainvoke({"request": request})
            findings = state["findings"]
            questions = state["questions"]

            response = ReviewResponse(
                findings=findings,
                questions=questions,
                mode=state["mode"],
                confidence=state["confidence"],
                citations_used=_unique_citations(
                    findings,
                    retrieved=state.get("retrieved_principles", []),
                ),
                provenance=_stage_provenance(state),
                request_id=str(uuid4()),
                latency_ms=(perf_counter() - started_at) * 1_000,
            )
            persistence_started = perf_counter()
            with self._observability.span(
                "review.persistence",
                input={"request_id": response.request_id},
            ) as persistence_span:
                try:
                    await self._recorder.record_review(
                        build_review_persistence_record(request, response)
                    )
                except Exception:
                    persistence_span.update(
                        metadata={
                            "stage_status": "failed",
                            "failure_category": "persistence_failed",
                            "latency_ms": (
                                perf_counter() - persistence_started
                            )
                            * 1_000,
                        },
                        level="ERROR",
                        status_message="persistence_failed",
                    )
                    raise
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
            span.update(
                output={
                    "request_id": response.request_id,
                    "mode": response.mode,
                    "finding_categories": [
                        finding.category for finding in response.findings
                    ],
                    "citation_ids": [
                        citation.source_id for citation in response.citations_used
                    ],
                    "question_count": len(response.questions),
                    "latency_ms": response.latency_ms,
                },
                metadata={"stage_status": "succeeded"},
                level="DEFAULT",
                status_message="succeeded",
            )
        flush_observability()
        return response


def _unique_citations(
    findings: Sequence[CodeFinding],
    *,
    retrieved: Sequence[object] = (),
) -> list[Citation]:
    citations: dict[str, Citation] = {}
    for finding in findings:
        for citation in finding.citations:
            citations.setdefault(citation.source_id, citation)
    if not findings:
        for principle in retrieved:
            retrieved_citation = getattr(principle, "citation", None)
            if isinstance(retrieved_citation, Citation):
                citations.setdefault(
                    retrieved_citation.source_id,
                    retrieved_citation,
                )
    return list(citations.values())


def _stage_provenance(state: object) -> list[StageProvenance]:
    if not isinstance(state, dict):
        return []
    return [
        stage
        for key in (
            "retrieval_provenance",
            "review_provenance",
            "question_provenance",
        )
        if isinstance((stage := state.get(key)), StageProvenance)
    ]


review_service = ReviewService()
