"""Application service for review orchestration and response metadata."""

from collections.abc import Sequence
from hashlib import sha256
from time import perf_counter
from uuid import uuid4

from langgraph.graph.state import CompiledStateGraph

from clutch.agent import REVIEW_GRAPH
from clutch.observability import OBSERVABILITY, Observability
from clutch.persistence import (
    ReviewRecorder,
    build_review_persistence_record,
    review_recorder_from_env,
)
from clutch.schemas import Citation, CodeFinding, ReviewRequest, ReviewResponse


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
                citations_used=_unique_citations(findings),
                request_id=str(uuid4()),
                latency_ms=(perf_counter() - started_at) * 1_000,
            )
            await self._recorder.record_review(
                build_review_persistence_record(request, response)
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
                    "model_name": state.get("model_name"),
                    "input_tokens": state.get("input_tokens"),
                    "output_tokens": state.get("output_tokens"),
                    "fallback_reason": state.get("fallback_reason"),
                }
            )
            return response


def _unique_citations(findings: Sequence[CodeFinding]) -> list[Citation]:
    citations: dict[str, Citation] = {}
    for finding in findings:
        for citation in finding.citations:
            citations.setdefault(citation.source_id, citation)
    return list(citations.values())


review_service = ReviewService()
