import asyncio
from typing import Any

from clutch.agent import build_review_graph
from clutch.knowledge_base import CleanCodePrinciple, retrieve_clean_code_principles
from clutch.llm import ModelRouter
from clutch.llm.providers import (
    ProviderQuestions,
    ProviderReview,
    QuestionContext,
    ReviewContext,
)
from clutch.schemas import FindingCategory, InterviewQuestion, ReviewRequest


class CapturingRetriever:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def retrieve(
        self,
        query: str,
        *,
        categories: set[FindingCategory] | None = None,
        limit: int = 3,
    ) -> list[CleanCodePrinciple]:
        self.calls.append(
            {"query": query, "categories": categories, "limit": limit}
        )
        return retrieve_clean_code_principles(
            query,
            categories=categories,
            limit=limit,
        )


class StaticTestModelProvider:
    async def review(self, context: ReviewContext) -> ProviderReview:
        return ProviderReview(
            findings=context.static_findings,
            confidence=0.7,
            mode="model",
            model_name="test-model",
            attempt_count=1,
        )


class QuestionGeneratingModelProvider(StaticTestModelProvider):
    async def generate_questions(
        self,
        context: QuestionContext,
    ) -> ProviderQuestions:
        finding = context.findings[0]
        return ProviderQuestions(
            questions=[
                InterviewQuestion(
                    id="question-001",
                    finding_id=finding.id,
                    question="How would you verify this exception boundary?",
                    intent="Assess grounded correctness reasoning.",
                    difficulty="hard",
                    citations=[context.principles[0].citation],
                    origin="ai_generated",
                )
            ],
            model_name="test-model",
            prompt_version="questions.v1",
            input_tokens=40,
            output_tokens=20,
            attempt_count=1,
            latency_ms=4.0,
            estimated_cost_usd=0.001,
        )


def test_review_graph_runs_expected_nodes_and_generates_questions() -> None:
    request = ReviewRequest(
        code="def load():\n    try:\n        return work()\n    except:\n        return None\n",
        role_context="backend intern",
    )

    graph = build_review_graph(ModelRouter(primary=StaticTestModelProvider()))
    state = asyncio.run(graph.ainvoke({"request": request}))

    assert state["parsed_code"].chunks[0].symbol_name == "load"
    assert state["findings"][0].id == "finding-bare-except-4"
    assert state["retrieved_principles"]
    assert state["questions"][0].finding_id == state["findings"][0].id
    assert "backend intern" in state["questions"][0].question
    assert state["mode"] == "model"
    assert state["confidence"] == 0.7


def test_positive_retrieval_uses_category_and_not_shared_source_id_tokens() -> None:
    retriever = CapturingRetriever()
    graph = build_review_graph(
        ModelRouter(primary=StaticTestModelProvider()),
        retriever=retriever,
    )

    asyncio.run(
        graph.ainvoke(
            {
                "request": ReviewRequest(
                    code="def load():\n    try:\n        return work()\n    except:\n        return None\n"
                )
            }
        )
    )

    call = retriever.calls[0]
    assert call["categories"] == {"correctness"}
    assert "rubric question interview" in call["query"]
    assert "seed.clean_code" not in call["query"]


def test_clean_retrieval_uses_bounded_code_terms() -> None:
    retriever = CapturingRetriever()
    graph = build_review_graph(
        ModelRouter(primary=StaticTestModelProvider()),
        retriever=retriever,
    )

    asyncio.run(
        graph.ainvoke(
            {
                "request": ReviewRequest(
                    code=(
                        "def find(cursor, value):\n"
                        "    cursor.execute('SELECT id FROM users WHERE id = %s', "
                        "(value,))\n"
                    )
                )
            }
        )
    )

    call = retriever.calls[0]
    assert call["categories"] is None
    assert "select" in call["query"]
    assert "sql" in call["query"]


def test_review_graph_uses_model_generated_questions_with_stage_diagnostics() -> None:
    graph = build_review_graph(
        ModelRouter(primary=QuestionGeneratingModelProvider())
    )

    state = asyncio.run(
        graph.ainvoke(
            {
                "request": ReviewRequest(
                    code=(
                        "def load():\n"
                        "    try:\n"
                        "        return work()\n"
                        "    except:\n"
                        "        return None\n"
                    )
                )
            }
        )
    )

    assert state["questions"][0].origin == "ai_generated"
    assert state["question_provenance"].status == "succeeded"
    assert state["question_provenance"].prompt_version == "questions.v1"
    assert state["question_provenance"].input_tokens == 40
    assert state["question_provenance"].estimated_cost_usd == 0.001
