import asyncio
from typing import Any

from clutch.agent import REVIEW_GRAPH, build_review_graph
from clutch.knowledge_base import CleanCodePrinciple, retrieve_clean_code_principles
from clutch.llm import ModelRouter
from clutch.schemas import FindingCategory, ReviewRequest


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


def test_review_graph_runs_expected_nodes_and_generates_questions() -> None:
    request = ReviewRequest(
        code="def load():\n    try:\n        return work()\n    except:\n        return None\n",
        role_context="backend intern",
    )

    state = asyncio.run(REVIEW_GRAPH.ainvoke({"request": request}))

    assert state["parsed_code"].chunks[0].symbol_name == "load"
    assert state["findings"][0].id == "finding-bare-except-4"
    assert state["retrieved_principles"]
    assert state["questions"][0].finding_id == state["findings"][0].id
    assert "backend intern" in state["questions"][0].question
    assert state["mode"] == "static_fallback"
    assert state["confidence"] == 0.7
    assert state["fallback_reason"] == "model_not_configured"


def test_positive_retrieval_uses_category_and_not_shared_source_id_tokens() -> None:
    retriever = CapturingRetriever()
    graph = build_review_graph(ModelRouter(primary=None), retriever=retriever)

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
    graph = build_review_graph(ModelRouter(primary=None), retriever=retriever)

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
