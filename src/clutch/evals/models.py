"""Typed contracts for golden cases and evaluation reports."""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from clutch.persistence.contracts import PersistedFinding
from clutch.schemas import FindingCategory, FindingSeverity, InterviewQuestion

ReviewCaseKind = Literal["focused", "clean", "mixed"]


class ExpectedFinding(BaseModel):
    """One atomic expected finding used for identity and quality checks."""

    id_prefix: str = Field(..., min_length=1)
    category: FindingCategory
    severity: FindingSeverity
    citation_ids: list[str] = Field(min_length=1)


class ReviewExpectations(BaseModel):
    """Expected review behavior shared by pasted and GitHub sources."""

    id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    kind: ReviewCaseKind
    role_context: str = "backend intern"
    expected_findings: list[ExpectedFinding] = Field(default_factory=list)
    question_keywords: list[str] = Field(default_factory=list)
    retrieval_judgments: dict[str, int] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_expected_findings(self) -> "ReviewExpectations":
        if self.kind == "clean" and self.expected_findings:
            raise ValueError("clean cases cannot declare expected findings")
        if self.kind != "clean" and not self.expected_findings:
            raise ValueError("focused and mixed cases require expected findings")
        if any(grade < 0 or grade > 3 for grade in self.retrieval_judgments.values()):
            raise ValueError("retrieval relevance grades must be between 0 and 3")
        required_citations = {
            citation_id
            for finding in self.expected_findings
            for citation_id in finding.citation_ids
        }
        insufficient = {
            citation_id
            for citation_id in required_citations
            if self.retrieval_judgments.get(citation_id, 0) < 2
        }
        if insufficient:
            raise ValueError(
                "required finding citations need relevance grade 2 or 3: "
                + ", ".join(sorted(insufficient))
            )
        return self


class GoldenReviewCase(ReviewExpectations):
    code: str = Field(..., min_length=1)


class GoldenGitHubFile(BaseModel):
    """One request-scoped source file returned by the fixture gateway."""

    path: str = Field(..., min_length=1, max_length=1_000)
    content: str = Field(..., min_length=1, max_length=50_000)


class GoldenGitHubReviewCase(ReviewExpectations):
    """A multi-file repository case evaluated through GitHubReviewService."""

    source_url: str = Field(..., min_length=1, max_length=500)
    ref: str = Field(default="main", min_length=1, max_length=200)
    files: list[GoldenGitHubFile] = Field(min_length=2, max_length=10)
    privacy_sentinel: str = Field(..., min_length=8)

    @model_validator(mode="after")
    def validate_repository_fixture(self) -> "GoldenGitHubReviewCase":
        paths = [file.path for file in self.files]
        if len(paths) != len(set(paths)):
            raise ValueError("GitHub fixture file paths must be unique")
        if sum(path.endswith((".py", ".pyi")) for path in paths) < 2:
            raise ValueError("GitHub fixture must contain at least two Python files")
        if not any(self.privacy_sentinel in file.content for file in self.files):
            raise ValueError("privacy sentinel must appear in at least one file")
        return self


class PromptInjectionCase(BaseModel):
    id: str = Field(..., min_length=1)
    code: str = Field(..., min_length=1)
    prohibited_output_terms: list[str] = Field(min_length=1)


class GoldenInterviewCase(BaseModel):
    """Deterministic interview and final-report expectation."""

    id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    questions: list[InterviewQuestion] = Field(min_length=1, max_length=5)
    answers: list[str] = Field(min_length=1, max_length=5)
    expected_scores: list[int] = Field(min_length=1, max_length=5)
    expected_strengths: list[str] = Field(default_factory=list)
    expected_recurring_issues: list[str] = Field(default_factory=list)
    recommended_task_keywords: list[str] = Field(default_factory=list)
    readiness_keyword: str = Field(..., min_length=1)
    supporting_findings: list[PersistedFinding] = Field(default_factory=list)
    privacy_sentinel: str = Field(..., min_length=8)

    @model_validator(mode="after")
    def validate_turns(self) -> "GoldenInterviewCase":
        if len(self.questions) != len(self.answers):
            raise ValueError("questions and answers must have equal length")
        if len(self.answers) != len(self.expected_scores):
            raise ValueError("answers and expected scores must have equal length")
        if any(score < 1 or score > 5 for score in self.expected_scores):
            raise ValueError("expected scores must be between 1 and 5")
        if not any(self.privacy_sentinel in answer for answer in self.answers):
            raise ValueError("privacy sentinel must appear in at least one answer")
        return self


class EvalCaseResult(BaseModel):
    case_id: str
    source: Literal["pasted_code", "github_repository"] = "pasted_code"
    kind: ReviewCaseKind
    expected_findings: int = Field(..., ge=0)
    predicted_findings: int = Field(..., ge=0)
    true_positives: int = Field(..., ge=0)
    false_positives: int = Field(..., ge=0)
    false_negatives: int = Field(..., ge=0)
    severity_matches: int = Field(..., ge=0)
    retrieval_evaluated: bool
    retrieval_relevant: int = Field(..., ge=0)
    retrieval_relevant_total: int = Field(..., ge=0)
    retrieved_ids: list[str] = Field(default_factory=list)
    retrieval_returned: int = Field(..., ge=0)
    retrieval_judged: int = Field(..., ge=0)
    retrieval_irrelevant: int = Field(..., ge=0)
    retrieval_reciprocal_rank: float = Field(..., ge=0.0, le=1.0)
    retrieval_ndcg: float = Field(..., ge=0.0, le=1.0)
    citation_faithful: bool
    hallucinated_line_numbers: int = Field(..., ge=0)
    question_relevant: bool
    latency_ms: float = Field(..., ge=0.0)
    ingestion_matched: bool | None = None
    source_privacy_preserved: bool | None = None


class InjectionCaseResult(BaseModel):
    case_id: str
    passed: bool
    prohibited_terms_found: list[str] = Field(default_factory=list)
    unknown_citation_ids: list[str] = Field(default_factory=list)


class InterviewCaseResult(BaseModel):
    case_id: str
    turn_count: int = Field(..., ge=1)
    exact_score_matches: int = Field(..., ge=0)
    completed: bool
    expected_strengths_met: bool
    expected_recurring_issues_met: bool
    recommended_tasks_met: bool
    readiness_matched: bool
    supporting_findings_matched: bool
    answer_privacy_preserved: bool


class EvalReport(BaseModel):
    dataset_version: str
    evaluation_mode: Literal["static_fallback"]
    review_case_count: int = Field(..., ge=1)
    github_review_case_count: int = Field(..., ge=1)
    clean_case_count: int = Field(..., ge=1)
    mixed_case_count: int = Field(..., ge=1)
    interview_case_count: int = Field(..., ge=1)
    finding_precision: float = Field(..., ge=0.0, le=1.0)
    finding_recall: float = Field(..., ge=0.0, le=1.0)
    finding_severity_accuracy: float = Field(..., ge=0.0, le=1.0)
    clean_negative_pass_rate: float = Field(..., ge=0.0, le=1.0)
    mixed_case_full_recall: float = Field(..., ge=0.0, le=1.0)
    retrieval_precision_at_3: float = Field(..., ge=0.0, le=1.0)
    retrieval_recall_at_3: float = Field(..., ge=0.0, le=1.0)
    retrieval_mrr: float = Field(..., ge=0.0, le=1.0)
    retrieval_ndcg_at_3: float = Field(..., ge=0.0, le=1.0)
    retrieval_judgment_coverage_at_3: float = Field(..., ge=0.0, le=1.0)
    retrieval_irrelevant_at_3: float = Field(..., ge=0.0, le=1.0)
    citation_faithfulness: float = Field(..., ge=0.0, le=1.0)
    hallucinated_line_number_rate: float = Field(..., ge=0.0, le=1.0)
    question_relevance: float = Field(..., ge=0.0, le=1.0)
    github_ingestion_pass_rate: float = Field(..., ge=0.0, le=1.0)
    github_source_privacy_pass_rate: float = Field(..., ge=0.0, le=1.0)
    interview_score_accuracy: float = Field(..., ge=0.0, le=1.0)
    interview_completion_rate: float = Field(..., ge=0.0, le=1.0)
    feedback_expectation_pass_rate: float = Field(..., ge=0.0, le=1.0)
    answer_privacy_pass_rate: float = Field(..., ge=0.0, le=1.0)
    invalid_structured_output_rate: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )
    prompt_injection_pass_rate: float = Field(..., ge=0.0, le=1.0)
    average_latency_ms: float = Field(..., ge=0.0)
    estimated_cost_usd: float = Field(..., ge=0.0)
    passed: bool
    cases: list[EvalCaseResult]
    injection_cases: list[InjectionCaseResult]
    interview_cases: list[InterviewCaseResult]
