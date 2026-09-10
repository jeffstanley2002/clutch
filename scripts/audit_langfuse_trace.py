"""Read and audit one recent Langfuse trace without mutating remote state."""

from __future__ import annotations

import argparse
import os
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

from dotenv import load_dotenv
from langfuse import Langfuse

from clutch.observability.audit import AuditWorkflow, audit_trace_observations


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workflow",
        choices=("review", "interview_turn", "final_feedback"),
        default="review",
    )
    parser.add_argument("--trace-id")
    parser.add_argument("--since-minutes", type=int, default=15)
    parser.add_argument("--expect-fallback", action="store_true")
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Print only the audit verdict and failure summary.",
    )
    args = parser.parse_args()
    if args.since_minutes < 1 or args.since_minutes > 1_440:
        raise SystemExit("--since-minutes must be between 1 and 1440")

    load_dotenv()
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
    if not public_key or not secret_key:
        raise SystemExit("Langfuse credentials are not configured")
    client = Langfuse(
        public_key=public_key,
        secret_key=secret_key,
        base_url=os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com"),
    )
    now = datetime.now(UTC)
    start = now - timedelta(minutes=args.since_minutes)
    try:
        trace_id = args.trace_id or _latest_trace_id(
            client,
            workflow=args.workflow,
            start=start,
            end=now,
        )
        response = client.api.observations.get_many(
            trace_id=trace_id,
            from_start_time=start,
            to_start_time=now,
            fields="core,basic,io,metadata,model,usage,metrics",
            limit=100,
        )
        observations = [item.model_dump(mode="json") for item in response.data]
        api_sources = ["observations_v2"]
        if _v2_native_projection_incomplete(observations):
            legacy = client.api.legacy.observations_v1.get_many(
                trace_id=trace_id,
                from_start_time=start,
                to_start_time=now,
                limit=100,
            )
            observations = _merge_legacy_native_fields(
                observations,
                [item.model_dump(mode="json") for item in legacy.data],
            )
            api_sources.append("legacy_v1_projection_fallback")
        report = audit_trace_observations(
            observations,
            trace_id=trace_id,
            workflow=args.workflow,
            expect_fallback=args.expect_fallback,
            api_sources=api_sources,
        )
        print(
            report.model_dump_json(
                indent=None if args.compact else 2,
                exclude={"evidence"} if args.compact else None,
            )
        )
    finally:
        client.shutdown()
    if not report.passed:
        raise SystemExit(1)


def _latest_trace_id(
    client: Langfuse,
    *,
    workflow: AuditWorkflow,
    start: datetime,
    end: datetime,
) -> str:
    root_name = {
        "review": "review.request",
        "interview_turn": "interview.turn",
        "final_feedback": "interview.final_aggregation",
    }[workflow]
    response = client.api.observations.get_many(
        name=root_name,
        is_root_observation=True,
        from_start_time=start,
        to_start_time=end,
        fields="core,basic",
        limit=20,
    )
    candidates = [item for item in response.data if item.trace_id]
    if not candidates:
        raise SystemExit(f"no recent {workflow} trace found")
    latest = max(candidates, key=lambda item: item.start_time)
    assert latest.trace_id is not None
    return latest.trace_id


def _v2_native_projection_incomplete(
    observations: list[dict[str, object]],
) -> bool:
    for observation in observations:
        if observation.get("end_time") is None:
            return True
        metadata = observation.get("metadata")
        if (
            observation.get("type") == "GENERATION"
            and isinstance(metadata, Mapping)
            and metadata.get("stage_status") == "succeeded"
            and (
                not observation.get("provided_model_name")
                or not observation.get("usage_details")
                or not observation.get("cost_details")
            )
        ):
            return True
    return False


def _merge_legacy_native_fields(
    observations: list[dict[str, object]],
    legacy_observations: list[dict[str, object]],
) -> list[dict[str, object]]:
    legacy_by_id = {item.get("id"): item for item in legacy_observations}
    merged: list[dict[str, object]] = []
    for observation in observations:
        combined = dict(observation)
        legacy = legacy_by_id.get(observation.get("id"), {})
        mappings = {
            "provided_model_name": "model",
            "usage_details": "usage_details",
            "cost_details": "cost_details",
            "status_message": "status_message",
            "latency": "latency",
            "version": "version",
            "end_time": "end_time",
            "level": "level",
        }
        for current_key, legacy_key in mappings.items():
            if not combined.get(current_key) and legacy.get(legacy_key) is not None:
                combined[current_key] = legacy[legacy_key]
        legacy_usage = legacy.get("usage")
        if isinstance(legacy_usage, Mapping):
            if not combined.get("usage_details"):
                combined["usage_details"] = {
                    key: legacy_usage[key]
                    for key in ("input", "output", "total")
                    if isinstance(legacy_usage.get(key), int)
                }
            if not combined.get("cost_details"):
                combined["cost_details"] = {
                    target: numeric_value
                    for target, source in (
                        ("input", "input_cost"),
                        ("output", "output_cost"),
                        ("total", "total_cost"),
                    )
                    if (numeric_value := _as_float(legacy_usage.get(source)))
                    is not None
                }
        merged.append(combined)
    return merged


def _as_float(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if not isinstance(value, (int, float, str)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    main()
