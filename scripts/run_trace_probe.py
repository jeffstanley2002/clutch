"""Emit one bounded synthetic model-backed review trace for operator auditing."""

from __future__ import annotations

import argparse
import asyncio
import json
import os

from dotenv import load_dotenv


async def _run() -> dict[str, object]:
    from clutch.review.service import review_service
    from clutch.schemas import ReviewRequest

    response = await review_service.review(
        ReviewRequest(
            code=(
                "def collect(event, events=[]):\n"
                "    # TODO replace the temporary path\n"
                "    events.append(event)\n"
                "    return events\n"
            ),
            role_context="backend intern",
            session_id="langfuse-trace-probe",
        )
    )
    return {
        "request_id": response.request_id,
        "mode": response.mode,
        "finding_count": len(response.findings),
        "question_count": len(response.questions),
        "stage_statuses": {
            stage.stage: stage.status for stage in response.provenance
        },
        "model_stages": [
            {
                "stage": stage.stage,
                "model": stage.model_name,
                "prompt_version": stage.prompt_version,
                "input_tokens": stage.input_tokens,
                "output_tokens": stage.output_tokens,
                "estimated_cost_usd": stage.estimated_cost_usd,
            }
            for stage in response.provenance
            if stage.model_name is not None
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fallback",
        action="store_true",
        help="Disable the review model after loading tracing credentials.",
    )
    args = parser.parse_args()
    load_dotenv()
    os.environ["LANGFUSE_TRACING_ENABLED"] = "true"
    os.environ["LANGFUSE_SAMPLE_RATE"] = "1.0"
    if args.fallback:
        os.environ["OPENAI_API_KEY"] = ""
    print(json.dumps(asyncio.run(_run()), sort_keys=True))


if __name__ == "__main__":
    main()
