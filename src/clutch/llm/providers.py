"""Structured review providers for AI-backed review synthesis."""

import logging
import os
from time import perf_counter
from typing import Annotated, Any, Literal, Protocol

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel, Field, ValidationError, model_validator

from clutch.knowledge_base import CleanCodePrinciple
from clutch.llm.spend import (
    ModelBudgetExceeded,
    ModelBudgetUnavailable,
    SpendGuard,
    completion_cost_usd,
    conservative_token_estimate,
    spend_guard_from_env,
)
from clutch.prompts.interview_assessment import (
    PROMPT_VERSION as INTERVIEW_ASSESSMENT_PROMPT_VERSION,
)
from clutch.prompts.interview_assessment import build_interview_assessment_prompt
from clutch.prompts.questions import PROMPT_VERSION as QUESTIONS_PROMPT_VERSION
from clutch.prompts.questions import build_questions_prompt
from clutch.prompts.review import PROMPT_VERSION, build_review_prompt
from clutch.schemas import (
    Citation,
    CodeFinding,
    InterviewAssessment,
    InterviewQuestion,
    ParsedCode,
    ReviewMode,
    ReviewRequest,
    SafeFailureCategory,
)

DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"
MAX_MODEL_ATTEMPTS = 2
MAX_REVIEW_OUTPUT_TOKENS = 4_000
MAX_QUESTION_OUTPUT_TOKENS = 1_600
MAX_INTERVIEW_ASSESSMENT_OUTPUT_TOKENS = 1_200
logger = logging.getLogger(__name__)


class ModelReviewOutput(BaseModel):
    """Strict structured payload requested from a review model."""

    findings: list[CodeFinding] = Field(max_length=12)
    confidence: float = Field(..., ge=0.0, le=1.0)


class ModelInterviewQuestion(BaseModel):
    """Provider payload before trusted finding and citation canonicalization."""

    finding_id: str = Field(..., min_length=1)
    question: str = Field(..., min_length=1)
    intent: str = Field(..., min_length=1)
    difficulty: Literal["easy", "medium", "hard"]
    citation_ids: list[str] = Field(..., min_length=1, max_length=3)


class ModelQuestionOutput(BaseModel):
    """Strict bounded question payload requested from the model."""

    questions: list[ModelInterviewQuestion] = Field(min_length=1, max_length=3)


class ModelInterviewAssessment(BaseModel):
    """Provider payload before trusted citation canonicalization."""

    score: int = Field(..., ge=1, le=5)
    strengths: list[Annotated[str, Field(min_length=1)]] = Field(
        default_factory=list,
        max_length=4,
    )
    gaps: list[Annotated[str, Field(min_length=1)]] = Field(
        default_factory=list,
        max_length=4,
    )
    feedback: str = Field(..., min_length=1)
    citation_ids: list[str] = Field(..., min_length=1, max_length=3)


class ReviewContext(BaseModel):
    """Typed, request-scoped model context that is never persisted."""

    request: ReviewRequest
    parsed_code: ParsedCode
    static_findings: list[CodeFinding]
    principles: list[CleanCodePrinciple]


class QuestionContext(BaseModel):
    """Source-free, request-scoped context for question generation."""

    role_context: str = Field(..., min_length=1, max_length=120)
    findings: list[CodeFinding] = Field(..., min_length=1, max_length=3)
    principles: list[CleanCodePrinciple] = Field(default_factory=list, max_length=8)


class InterviewAssessmentContext(BaseModel):
    """Request-scoped interview context; raw answers never leave this boundary."""

    role_context: str = Field(..., min_length=1, max_length=120)
    question: InterviewQuestion
    answer: str = Field(..., min_length=1, max_length=10_000)
    answer_signal_summary: str = Field(..., min_length=1, max_length=500)
    principles: list[CleanCodePrinciple] = Field(..., min_length=1, max_length=3)


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
    prompt_version: str | None = None
    latency_ms: float = Field(default=0.0, ge=0.0)
    estimated_cost_usd: float = Field(default=0.0, ge=0.0)
    failure_category: SafeFailureCategory | None = None

    @model_validator(mode="after")
    def validate_diagnostic_counts(self) -> "ProviderReview":
        if self.validation_failure_count > self.attempt_count:
            raise ValueError("validation failures cannot exceed provider attempts")
        return self


class ProviderQuestions(BaseModel):
    """Provider-neutral question output plus privacy-safe diagnostics."""

    questions: list[InterviewQuestion] = Field(max_length=3)
    model_name: str | None = None
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    attempt_count: int = Field(default=0, ge=0, le=MAX_MODEL_ATTEMPTS)
    validation_failure_count: int = Field(
        default=0,
        ge=0,
        le=MAX_MODEL_ATTEMPTS,
    )
    prompt_version: str | None = None
    latency_ms: float = Field(default=0.0, ge=0.0)
    estimated_cost_usd: float = Field(default=0.0, ge=0.0)
    failure_category: SafeFailureCategory | None = None

    @model_validator(mode="after")
    def validate_diagnostic_counts(self) -> "ProviderQuestions":
        if self.validation_failure_count > self.attempt_count:
            raise ValueError("validation failures cannot exceed provider attempts")
        return self


class ProviderAssessment(BaseModel):
    """Provider-neutral assessment plus privacy-safe model diagnostics."""

    assessment: InterviewAssessment
    model_name: str | None = None
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    attempt_count: int = Field(default=0, ge=0, le=MAX_MODEL_ATTEMPTS)
    validation_failure_count: int = Field(
        default=0,
        ge=0,
        le=MAX_MODEL_ATTEMPTS,
    )
    prompt_version: str | None = None
    latency_ms: float = Field(default=0.0, ge=0.0)
    estimated_cost_usd: float = Field(default=0.0, ge=0.0)
    failure_category: SafeFailureCategory | None = None

    @model_validator(mode="after")
    def validate_diagnostic_counts(self) -> "ProviderAssessment":
        if self.validation_failure_count > self.attempt_count:
            raise ValueError("validation failures cannot exceed provider attempts")
        return self


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
        failure_category: SafeFailureCategory,
        attempt_count: int,
        validation_failure_count: int,
    ) -> None:
        super().__init__("review provider failed after bounded attempts")
        self.failure_reason = failure_reason
        self.failure_category = failure_category
        self.attempt_count = attempt_count
        self.validation_failure_count = validation_failure_count


class ReviewModelUnavailable(RuntimeError):
    """Raised when model-required review cannot produce validated output."""

    def __init__(
        self,
        *,
        failure_reason: str,
        failure_category: SafeFailureCategory = "fallback_failed",
        attempt_count: int = 0,
        validation_failure_count: int = 0,
    ) -> None:
        super().__init__("model review is required but unavailable")
        self.failure_reason = failure_reason
        self.failure_category = failure_category
        self.attempt_count = attempt_count
        self.validation_failure_count = validation_failure_count


class FallbackStaticProvider:
    """Return explicitly labeled deterministic or retrieval-only output."""

    async def review(self, context: ReviewContext) -> ProviderReview:
        findings = [
            finding.model_copy(update={"origin": "deterministic_static"})
            for finding in context.static_findings
        ]
        return ProviderReview(
            findings=findings,
            confidence=0.7 if findings else 0.3,
            mode="static_fallback" if findings else "retrieval_only",
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
        started_at = perf_counter()
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
                findings = _normalize_grounding(output, context=context)
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
                    findings=[
                        finding.model_copy(update={"origin": "ai_generated"})
                        for finding in findings
                    ],
                    confidence=output.confidence,
                    mode="model",
                    model_name=self._model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    attempt_count=attempt_count,
                    validation_failure_count=validation_failure_count,
                    prompt_version=PROMPT_VERSION,
                    latency_ms=(perf_counter() - started_at) * 1_000,
                    estimated_cost_usd=(
                        completion_cost_usd(
                            self._model,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                        )
                        if isinstance(input_tokens, int)
                        and isinstance(output_tokens, int)
                        else estimated_cost
                    ),
                )
            except (ValidationError, ValueError) as exc:
                validation_failure_count += 1
                last_error = exc
                _log_provider_failure(
                    model=self._model,
                    attempt_count=attempt_count,
                    validation_failure_count=validation_failure_count,
                    exc=exc,
                )
            except Exception as exc:
                last_error = exc
                _log_provider_failure(
                    model=self._model,
                    attempt_count=attempt_count,
                    validation_failure_count=validation_failure_count,
                    exc=exc,
                )

        assert last_error is not None
        raise ReviewProviderFailure(
            failure_reason=type(last_error).__name__,
            failure_category=_failure_category(last_error),
            attempt_count=attempt_count,
            validation_failure_count=validation_failure_count,
        ) from last_error

    async def generate_questions(
        self,
        context: QuestionContext,
    ) -> ProviderQuestions:
        """Generate at most three questions grounded in supplied IDs only."""

        started_at = perf_counter()
        prompt = build_questions_prompt(
            role_context=context.role_context,
            findings=context.findings,
            principles=context.principles,
        )
        estimated_cost = completion_cost_usd(
            self._model,
            input_tokens=conservative_token_estimate(f"{prompt.system}\n{prompt.user}"),
            output_tokens=MAX_QUESTION_OUTPUT_TOKENS,
        )
        attempt_count = 0
        validation_failure_count = 0
        last_error: Exception | None = None
        for _ in range(MAX_MODEL_ATTEMPTS):
            reservation = await self._spend_guard.reserve(estimated_cost)
            attempt_count += 1
            try:
                response = await self._client.responses.parse(
                    model=self._model,
                    instructions=prompt.system,
                    input=prompt.user,
                    text_format=ModelQuestionOutput,
                    max_output_tokens=MAX_QUESTION_OUTPUT_TOKENS,
                    store=False,
                )
                output = ModelQuestionOutput.model_validate(response.output_parsed)
                questions = _normalize_questions(output, context=context)
                usage = getattr(response, "usage", None)
                input_tokens = getattr(usage, "input_tokens", None)
                output_tokens = getattr(usage, "output_tokens", None)
                actual_cost = estimated_cost
                if isinstance(input_tokens, int) and isinstance(output_tokens, int):
                    actual_cost = completion_cost_usd(
                        self._model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                    )
                    try:
                        await self._spend_guard.reconcile(reservation, actual_cost)
                    except ModelBudgetUnavailable:
                        pass
                return ProviderQuestions(
                    questions=questions,
                    model_name=self._model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    attempt_count=attempt_count,
                    validation_failure_count=validation_failure_count,
                    prompt_version=QUESTIONS_PROMPT_VERSION,
                    latency_ms=(perf_counter() - started_at) * 1_000,
                    estimated_cost_usd=actual_cost,
                )
            except (ValidationError, ValueError) as exc:
                validation_failure_count += 1
                last_error = exc
                _log_provider_failure(
                    model=self._model,
                    attempt_count=attempt_count,
                    validation_failure_count=validation_failure_count,
                    exc=exc,
                    stage="question_generation",
                )
            except Exception as exc:
                last_error = exc
                _log_provider_failure(
                    model=self._model,
                    attempt_count=attempt_count,
                    validation_failure_count=validation_failure_count,
                    exc=exc,
                    stage="question_generation",
                )
        assert last_error is not None
        raise ReviewProviderFailure(
            failure_reason=type(last_error).__name__,
            failure_category=_failure_category(last_error),
            attempt_count=attempt_count,
            validation_failure_count=validation_failure_count,
        ) from last_error

    async def assess_interview(
        self,
        context: InterviewAssessmentContext,
    ) -> ProviderAssessment:
        """Assess one untrusted answer with grounded structured output."""

        started_at = perf_counter()
        prompt = build_interview_assessment_prompt(
            role_context=context.role_context,
            question=context.question,
            answer=context.answer,
            answer_signal_summary=context.answer_signal_summary,
            principles=context.principles,
        )
        estimated_cost = completion_cost_usd(
            self._model,
            input_tokens=conservative_token_estimate(f"{prompt.system}\n{prompt.user}"),
            output_tokens=MAX_INTERVIEW_ASSESSMENT_OUTPUT_TOKENS,
        )
        attempt_count = 0
        validation_failure_count = 0
        last_error: Exception | None = None
        for _ in range(MAX_MODEL_ATTEMPTS):
            reservation = await self._spend_guard.reserve(estimated_cost)
            attempt_count += 1
            try:
                response = await self._client.responses.parse(
                    model=self._model,
                    instructions=prompt.system,
                    input=prompt.user,
                    text_format=ModelInterviewAssessment,
                    max_output_tokens=MAX_INTERVIEW_ASSESSMENT_OUTPUT_TOKENS,
                    store=False,
                )
                output = ModelInterviewAssessment.model_validate(
                    response.output_parsed
                )
                assessment = _normalize_interview_assessment(
                    output,
                    context=context,
                )
                usage = getattr(response, "usage", None)
                input_tokens = getattr(usage, "input_tokens", None)
                output_tokens = getattr(usage, "output_tokens", None)
                actual_cost = estimated_cost
                if isinstance(input_tokens, int) and isinstance(output_tokens, int):
                    actual_cost = completion_cost_usd(
                        self._model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                    )
                    try:
                        await self._spend_guard.reconcile(reservation, actual_cost)
                    except ModelBudgetUnavailable:
                        pass
                return ProviderAssessment(
                    assessment=assessment,
                    model_name=self._model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    attempt_count=attempt_count,
                    validation_failure_count=validation_failure_count,
                    prompt_version=INTERVIEW_ASSESSMENT_PROMPT_VERSION,
                    latency_ms=(perf_counter() - started_at) * 1_000,
                    estimated_cost_usd=actual_cost,
                )
            except (ValidationError, ValueError) as exc:
                validation_failure_count += 1
                last_error = exc
                _log_provider_failure(
                    model=self._model,
                    attempt_count=attempt_count,
                    validation_failure_count=validation_failure_count,
                    exc=exc,
                    stage="interview_assessment",
                )
            except Exception as exc:
                last_error = exc
                _log_provider_failure(
                    model=self._model,
                    attempt_count=attempt_count,
                    validation_failure_count=validation_failure_count,
                    exc=exc,
                    stage="interview_assessment",
                )
        assert last_error is not None
        raise ReviewProviderFailure(
            failure_reason=type(last_error).__name__,
            failure_category=_failure_category(last_error),
            attempt_count=attempt_count,
            validation_failure_count=validation_failure_count,
        ) from last_error


class ModelRouter:
    """Prefer configured model review and expose an honest static fallback."""

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
        failure_category: SafeFailureCategory | None = None
        attempt_count = 0
        validation_failure_count = 0
        if self._primary is None:
            failure_category = "model_not_configured"
        else:
            try:
                return await self._primary.review(context)
            except ReviewProviderFailure as exc:
                failure_category = exc.failure_category
                attempt_count = exc.attempt_count
                validation_failure_count = exc.validation_failure_count
            except Exception as exc:
                # Only a safe class/category crosses the observability boundary.
                failure_category = _failure_category(exc)

        try:
            fallback = await self._fallback.review(context)
        except Exception as exc:
            raise ReviewModelUnavailable(
                failure_reason="fallback_failed",
                failure_category="fallback_failed",
                attempt_count=attempt_count,
                validation_failure_count=validation_failure_count,
            ) from exc
        return fallback.model_copy(
            update={
                "failure_category": failure_category,
                "attempt_count": attempt_count,
                "validation_failure_count": validation_failure_count,
            }
        )

    async def generate_questions(
        self,
        context: QuestionContext,
        *,
        template_questions: list[InterviewQuestion],
    ) -> ProviderQuestions:
        """Prefer model questions and return an explicitly labeled template fallback."""

        failure_category: SafeFailureCategory | None = None
        attempt_count = 0
        validation_failure_count = 0
        question_method = (
            getattr(self._primary, "generate_questions", None)
            if self._primary is not None
            else None
        )
        if not callable(question_method):
            failure_category = "model_not_configured"
        else:
            try:
                result = await question_method(context)
                return ProviderQuestions.model_validate(result)
            except ReviewProviderFailure as exc:
                failure_category = exc.failure_category
                attempt_count = exc.attempt_count
                validation_failure_count = exc.validation_failure_count
            except Exception as exc:
                failure_category = _failure_category(exc)
        return ProviderQuestions(
            questions=[
                question.model_copy(update={"origin": "template_generated"})
                for question in template_questions[:3]
            ],
            attempt_count=attempt_count,
            validation_failure_count=validation_failure_count,
            failure_category=failure_category,
        )

    async def assess_interview(
        self,
        context: InterviewAssessmentContext,
        *,
        deterministic_fallback: InterviewAssessment,
    ) -> ProviderAssessment:
        """Prefer AI assessment and return an explicitly labeled rule fallback."""

        failure_category: SafeFailureCategory | None = None
        attempt_count = 0
        validation_failure_count = 0
        assessment_method = (
            getattr(self._primary, "assess_interview", None)
            if self._primary is not None
            else None
        )
        if not callable(assessment_method):
            failure_category = "model_not_configured"
        else:
            try:
                result = await assessment_method(context)
                return ProviderAssessment.model_validate(result)
            except ReviewProviderFailure as exc:
                failure_category = exc.failure_category
                attempt_count = exc.attempt_count
                validation_failure_count = exc.validation_failure_count
            except Exception as exc:
                failure_category = _failure_category(exc)
        return ProviderAssessment(
            assessment=deterministic_fallback.model_copy(
                update={"origin": "deterministic_static"}
            ),
            attempt_count=attempt_count,
            validation_failure_count=validation_failure_count,
            failure_category=failure_category,
        )


def _normalize_grounding(
    output: ModelReviewOutput,
    *,
    context: ReviewContext,
) -> list[CodeFinding]:
    """Reject invented grounding and canonicalize trusted citation metadata."""

    allowed_citations = {
        principle.citation.source_id: principle.citation
        for principle in context.principles
    }
    line_count = max(1, len(context.request.code.splitlines()))
    normalized_findings: list[CodeFinding] = []

    for finding in output.findings:
        if not finding.citations:
            raise ValueError("model finding is missing a citation")
        if any(
            citation.source_id not in allowed_citations
            for citation in finding.citations
        ):
            raise ValueError("model finding contains an ungrounded citation")
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
        normalized_findings.append(
            finding.model_copy(
                update={
                    "citations": [
                        allowed_citations[citation.source_id]
                        for citation in finding.citations
                    ]
                }
            )
        )
    return normalized_findings


def _normalize_questions(
    output: ModelQuestionOutput,
    *,
    context: QuestionContext,
) -> list[InterviewQuestion]:
    """Canonicalize every model-supplied ID to trusted application objects."""

    findings_by_id = {finding.id: finding for finding in context.findings}
    citations_by_id: dict[str, Citation] = {
        principle.citation.source_id: principle.citation
        for principle in context.principles
    }
    for finding in context.findings:
        citations_by_id.update(
            {citation.source_id: citation for citation in finding.citations}
        )
    normalized: list[InterviewQuestion] = []
    seen_findings: set[str] = set()
    for index, question in enumerate(output.questions[:3], start=1):
        if question.finding_id not in findings_by_id:
            raise ValueError("model question contains an unknown finding ID")
        if question.finding_id in seen_findings:
            raise ValueError("model questions must reference distinct findings")
        if any(source_id not in citations_by_id for source_id in question.citation_ids):
            raise ValueError("model question contains an ungrounded citation")
        seen_findings.add(question.finding_id)
        normalized.append(
            InterviewQuestion(
                id=f"question-{index:03d}",
                finding_id=question.finding_id,
                question=question.question,
                intent=question.intent,
                difficulty=question.difficulty,
                citations=[
                    citations_by_id[source_id]
                    for source_id in dict.fromkeys(question.citation_ids)
                ],
                origin="ai_generated",
            )
        )
    return normalized


def _normalize_interview_assessment(
    output: ModelInterviewAssessment,
    *,
    context: InterviewAssessmentContext,
) -> InterviewAssessment:
    """Canonicalize assessment citations to the retrieved public corpus."""

    citations_by_id = {
        principle.citation.source_id: principle.citation
        for principle in context.principles
    }
    if any(source_id not in citations_by_id for source_id in output.citation_ids):
        raise ValueError("model assessment contains an ungrounded citation")
    return InterviewAssessment(
        score=output.score,
        strengths=list(dict.fromkeys(output.strengths)),
        gaps=list(dict.fromkeys(output.gaps)),
        feedback=output.feedback,
        citations=[
            citations_by_id[source_id]
            for source_id in dict.fromkeys(output.citation_ids)
        ],
        origin="ai_generated",
    )


def _log_provider_failure(
    *,
    model: str,
    attempt_count: int,
    validation_failure_count: int,
    exc: Exception,
    stage: str = "review_synthesis",
) -> None:
    """Log bounded provider diagnostics without source, prompt, or payload data."""

    logger.warning(
        "model provider attempt failed",
        extra={
            "stage": stage,
            "model": model,
            "attempt_count": attempt_count,
            "validation_failure_count": validation_failure_count,
            "failure_reason": type(exc).__name__,
            "safe_failure_detail": _safe_failure_detail(exc),
        },
    )


def _safe_failure_detail(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        return "schema_validation_failed"
    if isinstance(exc, ValueError):
        message = str(exc)
        safe_messages = {
            "model finding is missing a citation",
            "model finding contains an ungrounded citation",
            "model finding line_start exceeds source",
            "model finding line_end exceeds source",
            "model finding line range is reversed",
        }
        if message in safe_messages:
            return message
    return "see_failure_reason"


def _failure_category(exc: Exception) -> SafeFailureCategory:
    if isinstance(exc, (ModelBudgetExceeded, ModelBudgetUnavailable)):
        return "budget_rejected"
    if isinstance(exc, ValidationError):
        return "schema_validation_failed"
    if isinstance(exc, ValueError):
        return "grounding_validation_failed"
    return "provider_error"
