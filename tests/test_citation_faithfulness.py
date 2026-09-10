from clutch.evals.config import FIXTURE_ROOT
from clutch.evals.fixtures import load_cases
from clutch.evals.models import GoldenReviewCase
from clutch.evals.review_metrics import evaluate_review_output
from clutch.knowledge_base.clean_code import SEED_CLEAN_CODE_PRINCIPLES
from clutch.parsing import parse_python_code
from clutch.review.static import run_static_review
from clutch.schemas import InterviewQuestion, ReviewRequest


def _bare_except_case() -> GoldenReviewCase:
    return next(
        case
        for case in load_cases(
            FIXTURE_ROOT / "golden_reviews.json",
            GoldenReviewCase,
        )
        if case.id == "bare-except"
    )


def _grounded_output():
    case = _bare_except_case()
    request = ReviewRequest(code=case.code, role_context=case.role_context)
    finding = run_static_review(
        request,
        parsed_code=parse_python_code(case.code),
    )[0]
    corpus_by_id = {
        principle.id: principle for principle in SEED_CLEAN_CODE_PRINCIPLES
    }
    retrieved = [
        corpus_by_id[source_id]
        for source_id in case.retrieval_judgments
        if source_id in corpus_by_id
    ]
    citation = corpus_by_id[case.expected_findings[0].citation_ids[0]].citation
    finding = finding.model_copy(update={"citations": [citation]})
    question = InterviewQuestion(
        id="question-1",
        finding_id=finding.id,
        question="How would you replace this bare except?",
        intent="Assess correctness reasoning.",
        difficulty="hard",
        citations=[citation],
    )
    return case, finding, question, retrieved


def test_citation_validity_and_support_are_measured_separately() -> None:
    case, finding, question, retrieved = _grounded_output()

    valid = evaluate_review_output(
        case,
        findings=[finding],
        retrieved=retrieved,
        questions=[question],
        line_count=len(case.code.splitlines()),
        latency_ms=1.0,
    )
    unsupported = evaluate_review_output(
        case,
        findings=[
            finding.model_copy(
                update={"explanation": "This exception exists at the boundary."}
            )
        ],
        retrieved=retrieved,
        questions=[question],
        line_count=len(case.code.splitlines()),
        latency_ms=1.0,
    )

    assert valid.citation_valid is True
    assert valid.citation_supported is True
    assert unsupported.citation_valid is True
    assert unsupported.citation_supported is False


def test_unreturned_or_irrelevant_additional_citation_is_rejected() -> None:
    case, finding, question, retrieved = _grounded_output()
    additional = next(
        principle.citation
        for principle in SEED_CLEAN_CODE_PRINCIPLES
        if principle.id == "seed.clean_code.parameterized_queries"
    )

    result = evaluate_review_output(
        case,
        findings=[
            finding.model_copy(
                update={"citations": [*finding.citations, additional]}
            )
        ],
        retrieved=retrieved,
        questions=[question],
        line_count=len(case.code.splitlines()),
        latency_ms=1.0,
    )

    assert result.citation_valid is False
    assert result.citation_supported is False


def test_finding_match_requires_expected_line_and_evidence_identity() -> None:
    case, finding, question, retrieved = _grounded_output()

    result = evaluate_review_output(
        case,
        findings=[finding.model_copy(update={"line_start": 3, "line_end": 3})],
        retrieved=retrieved,
        questions=[question],
        line_count=len(case.code.splitlines()),
        latency_ms=1.0,
    )

    assert result.true_positives == 0
    assert result.false_negatives == 1
