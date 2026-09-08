"""Structured review providers with a deterministic safety fallback."""

import os
from typing import Any, Protocol

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel, Field, ValidationError

from clutch.knowledge_base import CleanCodePrinciple
from clutch.llm.spend import (
    ModelBudgetUnavailable,
    SpendGuard,
    completion_cost_usd,
    conservative_token_estimate,
    spend_guard_from_env,
)
from clutch.prompts.review import build_review_prompt
from clutch.schemas import (
    CodeFinding,
    ParsedCode,
    ReviewMode,
    ReviewRequest,
)

DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"
MAX_MODEL_ATTEMPTS = 2
MAX_REVIEW_OUTPUT_TOKENS = 4_000


class ModelReviewOutput(BaseModel):
    """Strict structured payload requested from a review model."""

    findings: list[CodeFinding] = Field(max_length=12)
    confidence: float = Field(..., ge=0.0, le=1.0)


class ReviewContext(BaseModel):
    """Typed, request-scoped model context that is never persisted."""

    request: ReviewRequest
    parsed_code: ParsedCode
    static_findings: list[CodeFinding]
    principles: list[CleanCodePrinciple]


class ProviderReview(BaseModel):
    """Provider-neutral synthesis result consumed by LangGraph."""

    findings: list[CodeFinding]
    confidence: float = Field(..., ge=0.0, le=1.0)
    mode: ReviewMode
    model_name: str | None = None
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    attempt_count: int = Field(default=0, ge=0, le=MAX_MODEL_ATTEMPTS)
    validation_failure_count: int = Field(
        default=0,
        ge=0,
        le=MAX_MODEL_ATTEMPTS,
    )
    fallback_reason: str | None = None


class ReviewProvider(Protocol):
    async def review(self, context: ReviewContext) -> ProviderReview:
        """Produce validated findings for one request-scoped context."""


class OpenAIResponsesClient(Protocol):
    responses: Any


class ReviewProviderFailure(RuntimeError):
    """Provider failure carrying only privacy-safe diagnostic counters."""

    def __init__(
        self,
        *,
        failure_reason: str,
        attempt_count: int,
        validation_failure_count: int,
    ) -> None:
        super().__init__("review provider failed after bounded attempts")
        self.failure_reason = failure_reason
        self.attempt_count = attempt_count
        self.validation_failure_count = validation_failure_count


class FallbackStaticProvider:
    """Return deterministic findings when model review is unavailable."""

    async def review(self, context: ReviewContext) -> ProviderReview:
        return ProviderReview(
            findings=context.static_findings,
            confidence=0.7,
            mode="static_fallback",
        )


class OpenAIProvider:
    """Use OpenAI Structured Outputs for deeper review synthesis."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_OPENAI_MODEL,
        client: OpenAIResponsesClient | None = None,
        spend_guard: SpendGuard | None = None,
    ) -> None:
        self._client = client or AsyncOpenAI(api_key=api_key, max_retries=0)
        self._model = model
        self._spend_guard = spend_guard or spend_guard_from_env()

    async def review(self, context: ReviewContext) -> ProviderReview:
        prompt = build_review_prompt(
            request=context.request,
            parsed_code=context.parsed_code,
            static_findings=context.static_findings,
            principles=context.principles,
        )
        last_error: Exception | None = None
        attempt_count = 0
        validation_failure_count = 0
        estimated_cost = completion_cost_usd(
            self._model,
            input_tokens=conservative_token_estimate(f"{prompt.system}\n{prompt.user}"),
            output_tokens=MAX_REVIEW_OUTPUT_TOKENS,
        )

        for _ in range(MAX_MODEL_ATTEMPTS):
            reservation = await self._spend_guard.reserve(estimated_cost)
            attempt_count += 1
            try:
                response = await self._client.responses.parse(
                    model=self._model,
                    instructions=prompt.system,
                    input=prompt.user,
                    text_format=ModelReviewOutput,
                    max_output_tokens=MAX_REVIEW_OUTPUT_TOKENS,
                    store=False,
                )
                output = ModelReviewOutput.model_validate(response.output_parsed)
                _validate_grounding(output, context=context)
                usage = getattr(response, "usage", None)
                input_tokens = getattr(usage, "input_tokens", None)
                output_tokens = getattr(usage, "output_tokens", None)
                if isinstance(input_tokens, int) and isinstance(output_tokens, int):
                    try:
                        await self._spend_guard.reconcile(
                            reservation,
                            completion_cost_usd(
                                self._model,
                                input_tokens=input_tokens,
                                output_tokens=output_tokens,
                            ),
                        )
                    except ModelBudgetUnavailable:
                        # The conservative reservation remains charged when the
                        # shared counter cannot be reconciled after a paid call.
                        pass
                return ProviderReview(
                    findings=output.findings,
                    confidence=output.confidence,
                    mode="model",
                    model_name=self._model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    attempt_count=attempt_count,
                    validation_failure_count=validation_failure_count,
                )
            except (ValidationError, ValueError) as exc:
                validation_failure_count += 1
                last_error = exc
            except Exception as exc:
                last_error = exc

        assert last_error is not None
        raise ReviewProviderFailure(
            failure_reason=type(last_error).__name__,
            attempt_count=attempt_count,
            validation_failure_count=validation_failure_count,
        ) from last_error


class ModelRouter:
    """Select the model path when configured and fail closed to static review."""

    def __init__(
        self,
        *,
        primary: ReviewProvider | None,
        fallback: ReviewProvider | None = None,
    ) -> None:
        self._primary = primary
        self._fallback = fallback or FallbackStaticProvider()

    @classmethod
    def from_env(cls) -> "ModelRouter":
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            return cls(primary=None)

        model = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL).strip()
        return cls(primary=OpenAIProvider(api_key=api_key, model=model))

    async def review(self, context: ReviewContext) -> ProviderReview:
        if self._primary is None:
            fallback = await self._fallback.review(context)
            return fallback.model_copy(
                update={"fallback_reason": "model_not_configured"}
            )
        try:
            return await self._primary.review(context)
        except ReviewProviderFailure as exc:
            fallback = await self._fallback.review(context)
            return fallback.model_copy(
                update={
                    "fallback_reason": exc.failure_reason,
                    "attempt_count": exc.attempt_count,
                    "validation_failure_count": exc.validation_failure_count,
                }
            )
        except Exception as exc:
            # Store only the exception class. The provider payload and request context
            # may contain source and must never cross the observability boundary.
            fallback = await self._fallback.review(context)
            return fallback.model_copy(update={"fallback_reason": type(exc).__name__})


def _validate_grounding(output: ModelReviewOutput, *, context: ReviewContext) -> None:
    """Reject invented citations and impossible line locations."""

    allowed_citations = {
        principle.citation.source_id: principle.citation
        for principle in context.principles
    }
    line_count = max(1, len(context.request.code.splitlines()))

    for finding in output.findings:
        if not finding.citations:
            raise ValueError("model finding is missing a citation")
        if any(
            citation.source_id not in allowed_citations
            for citation in finding.citations
        ):
            raise ValueError("model finding contains an ungrounded citation")
        if any(
            citation != allowed_citations[citation.source_id]
            for citation in finding.citations
        ):
            raise ValueError("model finding altered canonical citation metadata")
        if finding.line_start is not None and finding.line_start > line_count:
            raise ValueError("model finding line_start exceeds source")
        if finding.line_end is not None and finding.line_end > line_count:
            raise ValueError("model finding line_end exceeds source")
        if (
            finding.line_start is not None
            and finding.line_end is not None
            and finding.line_end < finding.line_start
        ):
            raise ValueError("model finding line range is reversed")
