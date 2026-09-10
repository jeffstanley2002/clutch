"""Explicit Langfuse observations that never receive raw code, prompts, or answers."""

from __future__ import annotations

import os
import re
from contextlib import AbstractContextManager
from types import TracebackType
from typing import Any, Literal, Protocol, cast

from dotenv import load_dotenv
from langfuse import Langfuse

from clutch.llm.spend import completion_cost_usd
from clutch.schemas import StageProvenance

ObservationType = Literal[
    "agent",
    "embedding",
    "generation",
    "guardrail",
    "retriever",
    "span",
    "tool",
]
ObservationLevel = Literal["DEBUG", "DEFAULT", "WARNING", "ERROR"]
REDACTION_POLICY = "hashes_counts_ids_only.v1"
_REDACTED_KEYS = frozenset(
    {
        "answer",
        "api_key",
        "code",
        "content",
        "password",
        "prompt",
        "raw_code",
        "secret",
        "source",
        "token",
    }
)
_BEARER_RE = re.compile(r"(?i)bearer\s+[A-Za-z0-9._~-]+")


class ObservationSpan(Protocol):
    def update(
        self,
        *,
        output: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        model: str | None = None,
        version: str | None = None,
        usage_details: dict[str, int] | None = None,
        cost_details: dict[str, float] | None = None,
        level: ObservationLevel | None = None,
        status_message: str | None = None,
    ) -> None: ...


class Observability(Protocol):
    def span(
        self,
        name: str,
        *,
        as_type: ObservationType = "span",
        input: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AbstractContextManager[ObservationSpan]: ...


class _NullSpan(AbstractContextManager[ObservationSpan]):
    def __enter__(self) -> ObservationSpan:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def update(
        self,
        *,
        output: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        model: str | None = None,
        version: str | None = None,
        usage_details: dict[str, int] | None = None,
        cost_details: dict[str, float] | None = None,
        level: ObservationLevel | None = None,
        status_message: str | None = None,
    ) -> None:
        return None


class NullObservability:
    def span(
        self,
        name: str,
        *,
        as_type: ObservationType = "span",
        input: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AbstractContextManager[ObservationSpan]:
        return _NullSpan()


class _LangfuseSpan(AbstractContextManager[ObservationSpan]):
    def __init__(
        self,
        client: Langfuse,
        name: str,
        *,
        as_type: ObservationType,
        input: dict[str, Any] | None,
        metadata: dict[str, Any] | None,
    ) -> None:
        self._context = client.start_as_current_observation(
            name=name,
            as_type=as_type,
            input=redact_sensitive_data(input),
            metadata=_with_redaction_evidence(metadata),
        )
        self._observation: Any | None = None
        self._failure_recorded = False

    def __enter__(self) -> ObservationSpan:
        self._observation = self._context.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        if (
            exc_type is not None
            and self._observation is not None
            and not self._failure_recorded
        ):
            self._observation.update(
                level="ERROR",
                status_message="unknown",
                metadata=_with_redaction_evidence(
                    {"failure_category": "unknown"}
                ),
            )
        return self._context.__exit__(exc_type, exc_value, traceback)

    def update(
        self,
        *,
        output: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        model: str | None = None,
        version: str | None = None,
        usage_details: dict[str, int] | None = None,
        cost_details: dict[str, float] | None = None,
        level: ObservationLevel | None = None,
        status_message: str | None = None,
    ) -> None:
        if self._observation is not None:
            self._failure_recorded = level == "ERROR" or bool(
                metadata and metadata.get("failure_category")
            )
            self._observation.update(
                output=redact_sensitive_data(output),
                metadata=_with_redaction_evidence(metadata),
                model=model,
                version=version,
                usage_details=usage_details,
                # Cost is emitted below through Langfuse's documented standard
                # OTEL mapping. Sending both attributes makes the SDK-specific
                # value take precedence in regions affected by its projection bug.
                cost_details=None,
                level=level,
                status_message=status_message,
            )
            if cost_details and isinstance(cost_details.get("total"), (int, float)):
                # Langfuse maps this standard OTEL field to native cost_details.
                otel_span = getattr(self._observation, "_otel_span", None)
                if otel_span is not None:
                    otel_span.set_attribute(
                        "gen_ai.usage.cost",
                        cost_details["total"],
                    )


class LangfuseObservability:
    def __init__(self, client: Langfuse) -> None:
        self._client = client

    def span(
        self,
        name: str,
        *,
        as_type: ObservationType = "span",
        input: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AbstractContextManager[ObservationSpan]:
        return _LangfuseSpan(
            self._client,
            name,
            as_type=as_type,
            input=input,
            metadata=metadata,
        )

    def shutdown(self) -> None:
        self._client.shutdown()

    def flush(self) -> None:
        self._client.flush()


class _RecordedSpan(AbstractContextManager[ObservationSpan]):
    def __init__(
        self,
        records: list[dict[str, Any]],
        record: dict[str, Any],
    ) -> None:
        self._records = records
        self._record = record

    def __enter__(self) -> ObservationSpan:
        self._records.append(self._record)
        return self

    def __exit__(self, *args: object) -> None:
        exc_type = args[0] if args else None
        metadata = self._record.setdefault("metadata", {})
        if exc_type is not None and not metadata.get("failure_category"):
            self._record.update(
                {
                    "level": "ERROR",
                    "status_message": "unknown",
                }
            )
            metadata["failure_category"] = "unknown"
        return None

    def update(
        self,
        *,
        output: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        model: str | None = None,
        version: str | None = None,
        usage_details: dict[str, int] | None = None,
        cost_details: dict[str, float] | None = None,
        level: ObservationLevel | None = None,
        status_message: str | None = None,
    ) -> None:
        self._record["output"] = redact_sensitive_data(output)
        if metadata:
            current = self._record.setdefault("metadata", {})
            current.update(redact_sensitive_data(metadata))
        for key, value in (
            ("model", model),
            ("version", version),
            ("usage_details", usage_details),
            ("cost_details", cost_details),
            ("level", level),
            ("status_message", status_message),
        ):
            if value is not None:
                self._record[key] = value


class InMemoryObservability:
    """Test observer that proves only the intended redacted fields are recorded."""

    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def span(
        self,
        name: str,
        *,
        as_type: ObservationType = "span",
        input: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AbstractContextManager[ObservationSpan]:
        return _RecordedSpan(
            self.records,
            {
                "name": name,
                "as_type": as_type,
                "input": redact_sensitive_data(input),
                "metadata": _with_redaction_evidence(metadata),
            },
        )


def update_span_from_provenance(
    span: ObservationSpan,
    provenance: StageProvenance,
    *,
    output: dict[str, Any] | None = None,
) -> None:
    """Populate native Langfuse fields from one privacy-safe stage record."""

    usage_details = None
    if provenance.input_tokens is not None or provenance.output_tokens is not None:
        input_tokens = provenance.input_tokens or 0
        output_tokens = provenance.output_tokens or 0
        usage_details = {
            "input": input_tokens,
            "output": output_tokens,
            "total": input_tokens + output_tokens,
        }
    level = cast(
        ObservationLevel,
        {
            "succeeded": "DEFAULT",
            "skipped": "DEFAULT",
            "fallback": "WARNING",
            "failed": "ERROR",
        }[provenance.status],
    )
    span.update(
        output=output,
        metadata={
            "stage": provenance.stage,
            "stage_status": provenance.status,
            "origin": provenance.origin,
            "latency_ms": provenance.latency_ms,
            "attempt_count": provenance.attempt_count,
            "validation_failure_count": provenance.validation_failure_count,
            "failure_category": provenance.failure_category,
        },
        model=provenance.model_name,
        version=provenance.prompt_version,
        usage_details=usage_details,
        cost_details=_native_cost_details(provenance),
        level=level,
        status_message=provenance.failure_category or provenance.status,
    )


def _native_cost_details(provenance: StageProvenance) -> dict[str, float] | None:
    if provenance.model_name is None:
        return None
    details = {"total": provenance.estimated_cost_usd}
    if provenance.input_tokens is None or provenance.output_tokens is None:
        return details
    try:
        details.update(
            {
                "input": completion_cost_usd(
                    provenance.model_name,
                    input_tokens=provenance.input_tokens,
                    output_tokens=0,
                ),
                "output": completion_cost_usd(
                    provenance.model_name,
                    input_tokens=0,
                    output_tokens=provenance.output_tokens,
                ),
            }
        )
    except ValueError:
        # Unknown custom models still retain the provider's total estimate.
        pass
    return details


def _with_redaction_evidence(
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    safe = redact_sensitive_data(metadata or {})
    assert isinstance(safe, dict)
    return {**safe, "redaction_policy": REDACTION_POLICY}


def observability_from_env() -> Observability:
    load_dotenv()
    enabled = os.getenv("LANGFUSE_TRACING_ENABLED", "false").lower() == "true"
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
    if not enabled or not public_key or not secret_key:
        return NullObservability()
    return LangfuseObservability(
        Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            base_url=os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com"),
            sample_rate=_sample_rate_from_env(),
            mask=redact_sensitive_data,
        )
    )


def _sample_rate_from_env() -> float:
    try:
        sample_rate = float(os.getenv("LANGFUSE_SAMPLE_RATE", "1.0"))
    except ValueError as exc:
        raise ValueError("LANGFUSE_SAMPLE_RATE must be a number") from exc
    if not 0.0 <= sample_rate <= 1.0:
        raise ValueError("LANGFUSE_SAMPLE_RATE must be between zero and one")
    return sample_rate


def close_observability() -> None:
    """Flush pending Langfuse spans during graceful application shutdown."""

    if isinstance(OBSERVABILITY, LangfuseObservability):
        OBSERVABILITY.shutdown()


def flush_observability() -> None:
    """Flush pending Langfuse spans after demo-critical request boundaries."""

    if isinstance(OBSERVABILITY, LangfuseObservability):
        OBSERVABILITY.flush()


def redact_sensitive_data(data: Any, **_: Any) -> Any:
    if isinstance(data, dict):
        return {
            key: (
                "[REDACTED]"
                if key.lower() in _REDACTED_KEYS
                else redact_sensitive_data(value)
            )
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [redact_sensitive_data(value) for value in data]
    if isinstance(data, tuple):
        return tuple(redact_sensitive_data(value) for value in data)
    if isinstance(data, str):
        return _BEARER_RE.sub("Bearer [REDACTED]", data)
    return data


OBSERVABILITY = observability_from_env()
