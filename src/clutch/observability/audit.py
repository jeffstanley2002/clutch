"""Privacy-safe structural audit for Langfuse observation exports."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from clutch.observability.tracing import REDACTION_POLICY

AuditWorkflow = Literal["review", "interview_turn", "final_feedback"]

_REQUIRED_NAMES: dict[AuditWorkflow, frozenset[str]] = {
    "review": frozenset(
        {
            "review.request",
            "review.parse_code",
            "review.static_review",
            "review.retrieve_principles",
            "review.synthesize",
            "review.validate_findings",
            "review.generate_questions",
            "review.persistence",
        }
    ),
    "interview_turn": frozenset(
        {
            "interview.turn",
            "interview.retrieve_grounding",
            "interview.assess_answer",
            "interview.persistence",
        }
    ),
    "final_feedback": frozenset({"interview.final_aggregation"}),
}
_GENERATION_NAMES = frozenset(
    {"review.synthesize", "review.generate_questions", "interview.assess_answer"}
)
_SENSITIVE_KEYS = frozenset(
    {"answer", "api_key", "code", "content", "password", "prompt", "secret", "token"}
)


class TraceAuditReport(BaseModel):
    """Safe audit result containing structure and diagnostics, never trace IO."""

    trace_id: str = Field(..., min_length=1)
    workflow: AuditWorkflow
    observation_count: int = Field(..., ge=1)
    observed_names: list[str]
    native_generation_names: list[str]
    fallback_categories: list[str]
    redaction_evidence_present: bool
    passed: bool
    failures: list[str] = Field(default_factory=list)
    evidence: list[TraceObservationEvidence] = Field(default_factory=list)
    api_sources: list[str] = Field(default_factory=list)


class TraceObservationEvidence(BaseModel):
    """Non-sensitive fields used to explain an audit result."""

    name: str
    observation_type: str | None = None
    level: str | None = None
    status_message: str | None = None
    latency: float | None = None
    model: str | None = None
    version: str | None = None
    usage_present: bool
    cost_present: bool
    metadata_keys: list[str] = Field(default_factory=list)


def audit_trace_observations(
    observations: Sequence[Mapping[str, Any]],
    *,
    trace_id: str,
    workflow: AuditWorkflow,
    expect_fallback: bool = False,
    api_sources: Sequence[str] = ("provided",),
) -> TraceAuditReport:
    """Fail closed when required spans or native diagnostics are absent."""

    failures: list[str] = []
    names = {
        str(observation.get("name"))
        for observation in observations
        if observation.get("name")
    }
    missing = _REQUIRED_NAMES[workflow] - names
    if missing:
        failures.append("missing required observations: " + ", ".join(sorted(missing)))

    native_generations: list[str] = []
    fallback_categories: list[str] = []
    redaction_evidence_present = True
    for observation in observations:
        name = str(observation.get("name") or "unnamed")
        metadata = observation.get("metadata")
        if not isinstance(metadata, Mapping) or metadata.get(
            "redaction_policy"
        ) != REDACTION_POLICY:
            redaction_evidence_present = False
            failures.append(f"{name} lacks redaction evidence")
        if _contains_sensitive_key(observation.get("input")) or _contains_sensitive_key(
            observation.get("output")
        ):
            failures.append(f"{name} exposes a prohibited IO key")
        latency = _native_latency(observation)
        if name in _REQUIRED_NAMES[workflow] and not isinstance(
            latency, (int, float)
        ):
            failures.append(f"{name} lacks native latency")

        level = _enum_value(observation.get("level"))
        if name in _REQUIRED_NAMES[workflow] and level not in {
            "DEBUG",
            "DEFAULT",
            "WARNING",
            "ERROR",
        }:
            failures.append(f"{name} lacks native level")
        stage_status = metadata.get("stage_status") if isinstance(metadata, Mapping) else None
        if name in _REQUIRED_NAMES[workflow] and stage_status not in {
            "succeeded",
            "skipped",
            "fallback",
            "failed",
        }:
            failures.append(f"{name} lacks typed stage status")
        is_fallback = level in {"WARNING", "ERROR"} or stage_status in {
            "fallback",
            "failed",
        }
        if is_fallback:
            category = metadata.get("failure_category") if isinstance(metadata, Mapping) else None
            if not isinstance(category, str) or not category:
                failures.append(f"{name} lacks a safe failure category")
            else:
                fallback_categories.append(category)

        if name in _GENERATION_NAMES and stage_status == "succeeded":
            generation_failures = _audit_native_generation(observation, name=name)
            if generation_failures:
                failures.extend(generation_failures)
            else:
                native_generations.append(name)

    if expect_fallback and not fallback_categories:
        failures.append("expected a fallback observation but none was recorded")
    if not expect_fallback:
        required_native_generations = _GENERATION_NAMES & _REQUIRED_NAMES[workflow]
        missing_native_generations = required_native_generations - set(
            native_generations
        )
        if missing_native_generations:
            failures.append(
                "missing complete native generations: "
                + ", ".join(sorted(missing_native_generations))
            )
    if not observations:
        failures.append("trace has no observations")
        redaction_evidence_present = False
    evidence = [
        TraceObservationEvidence(
            name=str(observation.get("name") or "unnamed"),
            observation_type=(
                str(observation["type"]) if observation.get("type") else None
            ),
            level=(
                _enum_value(observation.get("level"))
                if observation.get("level") is not None
                else None
            ),
            status_message=(
                str(observation["status_message"])
                if observation.get("status_message")
                else None
            ),
            latency=(
                native_latency
                if (native_latency := _native_latency(observation)) is not None
                else None
            ),
            model=(
                str(observation["provided_model_name"])
                if observation.get("provided_model_name")
                else None
            ),
            version=(
                str(observation["version"])
                if observation.get("version")
                else None
            ),
            usage_present=isinstance(observation.get("usage_details"), Mapping),
            cost_present=_native_cost_present(observation),
            metadata_keys=(
                sorted(str(key) for key in metadata_value)
                if isinstance((metadata_value := observation.get("metadata")), Mapping)
                else []
            ),
        )
        for observation in sorted(
            observations,
            key=lambda item: str(item.get("name") or ""),
        )
    ]
    return TraceAuditReport(
        trace_id=trace_id,
        workflow=workflow,
        observation_count=len(observations),
        observed_names=sorted(names),
        native_generation_names=sorted(set(native_generations)),
        fallback_categories=sorted(set(fallback_categories)),
        redaction_evidence_present=redaction_evidence_present,
        passed=not failures,
        failures=failures,
        evidence=evidence,
        api_sources=list(api_sources),
    )


def _audit_native_generation(
    observation: Mapping[str, Any],
    *,
    name: str,
) -> list[str]:
    failures: list[str] = []
    if not observation.get("provided_model_name"):
        failures.append(f"{name} lacks native model")
    if not observation.get("version"):
        failures.append(f"{name} lacks native prompt version")
    usage = observation.get("usage_details")
    if not isinstance(usage, Mapping) or not {
        "input",
        "output",
        "total",
    } <= set(usage):
        failures.append(f"{name} lacks native token usage")
    if not _native_cost_present(observation):
        failures.append(f"{name} lacks native cost")
    return failures


def _native_cost_present(observation: Mapping[str, Any]) -> bool:
    cost = observation.get("cost_details")
    if isinstance(cost, Mapping) and isinstance(cost.get("total"), (int, float)):
        return True
    total_cost = observation.get("total_cost")
    return (
        isinstance(total_cost, (int, float))
        and not isinstance(total_cost, bool)
        and total_cost >= 0
    )


def _contains_sensitive_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            str(key).lower() in _SENSITIVE_KEYS or _contains_sensitive_key(nested)
            for key, nested in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_sensitive_key(item) for item in value)
    return False


def _enum_value(value: Any) -> str:
    raw = getattr(value, "value", value)
    return str(raw).upper() if raw is not None else ""


def _native_latency(observation: Mapping[str, Any]) -> float | None:
    latency = observation.get("latency")
    if isinstance(latency, (int, float)):
        return float(latency)
    start = observation.get("start_time")
    end = observation.get("end_time")
    if isinstance(start, str) and isinstance(end, str):
        try:
            start = datetime.fromisoformat(start.replace("Z", "+00:00"))
            end = datetime.fromisoformat(end.replace("Z", "+00:00"))
        except ValueError:
            return None
    if isinstance(start, datetime) and isinstance(end, datetime):
        return max(0.0, (end - start).total_seconds())
    return None
