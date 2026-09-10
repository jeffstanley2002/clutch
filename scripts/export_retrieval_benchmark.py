"""Export transient retrieval queries for the Neon HTTPS benchmark runner."""

from __future__ import annotations

import asyncio
import json
from time import perf_counter

from clutch.evals.config import DATASET_VERSION
from clutch.evals.retrieval_comparison import _build_benchmark_cases
from clutch.rag import LocalKnowledgeRetriever


async def export_cases() -> dict[str, object]:
    """Build public-fixture queries without writing submitted source to disk."""

    retriever = LocalKnowledgeRetriever()
    cases: list[dict[str, object]] = []
    for benchmark in _build_benchmark_cases():
        started_at = perf_counter()
        local = await retriever.retrieve(
            benchmark.query.text,
            categories=(
                set(benchmark.query.categories)
                if benchmark.query.categories
                else None
            ),
            limit=3,
        )
        latency_ms = (perf_counter() - started_at) * 1_000
        cases.append(
            {
                "case_id": benchmark.expectations.id,
                "categories": sorted(benchmark.query.categories or []),
                "judgments": benchmark.expectations.retrieval_judgments,
                "local_ids": [item.id for item in local],
                "local_latency_ms": latency_ms,
                "query": benchmark.query.text,
            }
        )
    return {"dataset_version": DATASET_VERSION, "cases": cases}


def main() -> None:
    print(json.dumps(asyncio.run(export_cases()), separators=(",", ":")))


if __name__ == "__main__":
    main()
