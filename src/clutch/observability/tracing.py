"""Explicit Langfuse observations that never receive raw code, prompts, or answers."""

from __future__ import annotations

import os
import re
from contextlib import AbstractContextManager
from types import TracebackType
from typing import Any, Literal, Protocol

from dotenv import load_dotenv
from langfuse import Langfuse

ObservationType = Literal[
    "agent",
    "embedding",
    "generation",
    "guardrail",
    "retriever",
    "span",
    "tool",
]
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
            metadata=redact_sensitive_data(metadata),
        )
        self._observation: Any | None = None

    def __enter__(self) -> ObservationSpan:
        self._observation = self._context.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        return self._context.__exit__(exc_type, exc_value, traceback)

    def update(
        self,
        *,
        output: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if self._observation is not None:
            self._observation.update(
                output=redact_sensitive_data(output),
                metadata=redact_sensitive_data(metadata),
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
        return None

    def update(
        self,
        *,
        output: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._record["output"] = redact_sensitive_data(output)
        if metadata:
            current = self._record.setdefault("metadata", {})
            current.update(redact_sensitive_data(metadata))


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
                "metadata": redact_sensitive_data(metadata),
            },
        )


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
