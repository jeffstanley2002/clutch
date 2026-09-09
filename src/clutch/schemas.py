"""Shared Pydantic contracts for API, tool, and future model boundaries."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

SupportedLanguage = Literal["python"]
ReviewMode = Literal["model", "static_fallback", "retrieval_only"]
OutputOrigin = Literal[
    "ai_generated",
    "deterministic_static",
    "template_generated",
    "retrieved_citation",
]
StageName = Literal[
    "retrieval",
    "review_synthesis",
    "question_generation",
    "interview_retrieval",
    "interview_assessment",
    "final_aggregation",
]
StageStatus = Literal["succeeded", "fallback", "failed", "skipped"]
SafeFailureCategory = Literal[
    "model_not_configured",
    "budget_rejected",
    "provider_error",
    "schema_validation_failed",
    "grounding_validation_failed",
    "retrieval_failed",
    "fallback_failed",
    "persistence_failed",
    "unknown",
]
SymbolKind = Literal["module", "class", "function"]
FindingSeverity = Literal["low", "medium", "high"]
FindingCategory = Literal[
    "maintainability",
    "readability",
    "correctness",
    "testing",
    "design",
    "security",
]
InterviewStatus = Literal["active", "completed"]
OPAQUE_ID_PATTERN = r"^[A-Za-z0-9_-]+$"


class Citation(BaseModel):
    """A source reference that grounds review feedback."""

    source_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    url: str | None = None
    origin: OutputOrigin = "retrieved_citation"


class StageProvenance(BaseModel):
    """Privacy-safe runtime evidence for one review or interview stage."""

    stage: StageName
    status: StageStatus
    origin: OutputOrigin
    model_name: str | None = None
    prompt_version: str | None = None
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    latency_ms: float = Field(default=0.0, ge=0.0)
    estimated_cost_usd: float = Field(default=0.0, ge=0.0)
    attempt_count: int = Field(default=0, ge=0)
    validation_failure_count: int = Field(default=0, ge=0)
    failure_category: SafeFailureCategory | None = None

    @model_validator(mode="after")
    def validate_failure_state(self) -> "StageProvenance":
        if self.validation_failure_count > self.attempt_count:
            raise ValueError("validation failures cannot exceed stage attempts")
        if self.status in {"fallback", "failed"} and self.failure_category is None:
            raise ValueError("fallback and failed stages require a failure category")
        return self


class ReviewRequest(BaseModel):
    """Request for the first pasted-code review workflow."""

    code: str = Field(..., min_length=1, max_length=50_000)
    language: SupportedLanguage = "python"
    role_context: str = Field(default="backend intern", max_length=120)
    session_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        pattern=OPAQUE_ID_PATTERN,
    )

    @field_validator("code")
    @classmethod
    def code_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("code must contain non-whitespace characters")
        return value

    @field_validator("role_context")
    @classmethod
    def normalize_role_context(cls, value: str) -> str:
        normalized = value.strip()
        return normalized or "backend intern"


class CodeFinding(BaseModel):
    """A structured code review finding."""

    id: str = Field(..., min_length=1)
    severity: FindingSeverity
    category: FindingCategory
    message: str = Field(..., min_length=1)
    evidence: str = Field(..., min_length=1)
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    explanation: str = Field(..., min_length=1)
    suggestion: str = Field(..., min_length=1)
    citations: list[Citation] = Field(default_factory=list)
    origin: OutputOrigin = "deterministic_static"


class CodeChunk(BaseModel):
    """A structure-aware source chunk produced by the parser."""

    file_path: str = Field(..., min_length=1)
    language: SupportedLanguage
    symbol_name: str = Field(..., min_length=1)
    symbol_kind: SymbolKind
    line_start: int = Field(..., ge=1)
    line_end: int = Field(..., ge=1)
    source_text: str = Field(..., min_length=1)


class ParsedCode(BaseModel):
    """Parser output used by review, retrieval, and future agent context."""

    language: SupportedLanguage
    file_path: str = Field(..., min_length=1)
    chunks: list[CodeChunk] = Field(default_factory=list)
    has_syntax_error: bool = False


class InterviewQuestion(BaseModel):
    """A structured interviewer-style follow-up question."""

    id: str = Field(..., min_length=1)
    finding_id: str | None = None
    question: str = Field(..., min_length=1)
    intent: str = Field(..., min_length=1)
    difficulty: Literal["easy", "medium", "hard"]
    citations: list[Citation] = Field(default_factory=list)
    origin: OutputOrigin = "template_generated"


class InterviewAssessment(BaseModel):
    """Structured feedback for one submitted interview answer."""

    score: int = Field(..., ge=1, le=5)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    feedback: str = Field(..., min_length=1)
    citations: list[Citation] = Field(default_factory=list)
    origin: OutputOrigin = "deterministic_static"
    provenance: StageProvenance | None = None


class InterviewTurnRequest(BaseModel):
    """Start an interview or answer the current question."""

    interview_session_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        pattern=OPAQUE_ID_PATTERN,
    )
    review_session_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        pattern=OPAQUE_ID_PATTERN,
    )
    profile_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        pattern=OPAQUE_ID_PATTERN,
    )
    role_context: str = Field(default="backend intern", max_length=120)
    questions: list[InterviewQuestion] = Field(default_factory=list, max_length=5)
    answer: str | None = Field(default=None, max_length=10_000)

    @model_validator(mode="after")
    def validate_turn_shape(self) -> "InterviewTurnRequest":
        if self.interview_session_id is None and not self.questions:
            raise ValueError("questions are required to start an interview")
        if self.interview_session_id is not None and not (self.answer or "").strip():
            raise ValueError("answer is required for an existing interview")
        return self


class InterviewTurnResponse(BaseModel):
    """Current interview state and optional assessment of the prior answer."""

    interview_session_id: str
    status: InterviewStatus
    turn_number: int = Field(..., ge=1)
    question: InterviewQuestion | None = None
    assessment: InterviewAssessment | None = None
    completed: bool


class ReviewResponse(BaseModel):
    """Complete result of the review graph exposed by the API."""

    findings: list[CodeFinding] = Field(default_factory=list)
    questions: list[InterviewQuestion] = Field(default_factory=list)
    mode: ReviewMode
    confidence: float = Field(..., ge=0.0, le=1.0)
    citations_used: list[Citation] = Field(default_factory=list)
    provenance: list[StageProvenance] = Field(default_factory=list)
    request_id: str = Field(..., min_length=1)
    latency_ms: float = Field(..., ge=0.0)


class GitHubReviewRequest(BaseModel):
    """Request for a bounded read-only GitHub repository or PR review."""

    source_url: str = Field(..., min_length=1, max_length=500)
    ref: str | None = Field(default=None, min_length=1, max_length=200)
    role_context: str = Field(default="backend intern", max_length=120)
    session_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        pattern=OPAQUE_ID_PATTERN,
    )

    @field_validator("source_url", "role_context")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must contain non-whitespace characters")
        return normalized


class GitHubIngestionSummary(BaseModel):
    """Safe metadata describing what entered the active review request."""

    source_type: Literal["repository", "pull_request"]
    owner: str
    repository: str
    ref: str | None = None
    pull_number: int | None = Field(default=None, ge=1)
    files_included: list[str] = Field(default_factory=list)
    skipped_file_count: int = Field(default=0, ge=0)
    total_bytes: int = Field(default=0, ge=0)
    truncated: bool = False


class GitHubReviewResponse(BaseModel):
    """GitHub ingestion metadata plus the normal structured review result."""

    ingestion: GitHubIngestionSummary
    review: ReviewResponse


class SupportingFinding(BaseModel):
    """Privacy-safe review evidence included in a feedback report."""

    id: str = Field(..., min_length=1)
    severity: FindingSeverity
    category: FindingCategory
    message: str = Field(..., min_length=1)
    explanation: str = Field(..., min_length=1)
    suggestion: str = Field(..., min_length=1)
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    citation_ids: list[str] = Field(default_factory=list)


class FeedbackReport(BaseModel):
    """Structured final report for a completed interview session."""

    session_id: str
    strengths: list[str] = Field(default_factory=list)
    recurring_issues: list[str] = Field(default_factory=list)
    recommended_tasks: list[str] = Field(default_factory=list)
    interview_readiness_summary: str
    supporting_findings: list[SupportingFinding] = Field(default_factory=list)
    origin: OutputOrigin = "deterministic_static"
    aggregation_label: str = "Rule-based report aggregation from assessed turns."


class ProgressSnapshot(BaseModel):
    """Derived cross-session progress summary."""

    user_id: str
    time_window: str
    improved_areas: list[str] = Field(default_factory=list)
    persistent_issues: list[str] = Field(default_factory=list)
    next_practice_tasks: list[str] = Field(default_factory=list)
    evidence_sessions: list[str] = Field(default_factory=list)
