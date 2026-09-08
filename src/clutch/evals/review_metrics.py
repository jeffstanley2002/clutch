"""Shared scoring for deterministic and credentialed review evaluations."""

from clutch.evals.metrics import ndcg_at_k
from clutch.evals.models import EvalCaseResult, ReviewExpectations
from clutch.knowledge_base import CleanCodePrinciple
from clutch.knowledge_base.clean_code import SEED_CLEAN_CODE_PRINCIPLES
from clutch.schemas import CodeFinding, InterviewQuestion


def evaluate_review_output(
    case: ReviewExpectations,
    *,
    findings: list[CodeFinding],
    retrieved: list[CleanCodePrinciple],
    questions: list[InterviewQuestion],
    line_count: int,
    latency_ms: float,
) -> EvalCaseResult:
    """Score one typed review result without retaining its submitted source."""

    matches = match_expected_findings(case, findings)
    retrieved_ids = [principle.citation.source_id for principle in retrieved]
    retrieval_grades = [
        case.retrieval_judgments.get(source_id, 0) for source_id in retrieved_ids
    ]
    relevant_total = sum(grade >= 2 for grade in case.retrieval_judgments.values())
    relevant_ranks = [
        index for index, grade in enumerate(retrieval_grades, start=1) if grade >= 2
    ]
    known_citations = {
        principle.citation.source_id for principle in SEED_CLEAN_CODE_PRINCIPLES
    }
    observed_citations = {
        citation.source_id for finding in findings for citation in finding.citations
    }
    matched_citations_are_faithful = all(
        set(case.expected_findings[expected_index].citation_ids)
        <= {citation.source_id for citation in findings[finding_index].citations}
        for expected_index, finding_index in matches.items()
    )
    hallucinated_lines = sum(
        1
        for finding in findings
        if (finding.line_start is not None and finding.line_start > line_count)
        or (finding.line_end is not None and finding.line_end > line_count)
    )
    question_text = " ".join(
        f"{question.question} {question.intent}" for question in questions
    ).lower()
    finding_ids = {finding.id for finding in findings}
    expected_question_count = min(3, len(case.expected_findings))
    if case.kind == "clean":
        question_relevant = not questions
    else:
        question_relevant = (
            len(questions) == expected_question_count
            and all(question.finding_id in finding_ids for question in questions)
            and all(
                keyword.lower() in question_text for keyword in case.question_keywords
            )
            and all(
                case.role_context.lower() in question.question.lower()
                for question in questions
            )
        )

    return EvalCaseResult(
        case_id=case.id,
        kind=case.kind,
        expected_findings=len(case.expected_findings),
        predicted_findings=len(findings),
        true_positives=len(matches),
        false_positives=max(0, len(findings) - len(matches)),
        false_negatives=len(case.expected_findings) - len(matches),
        severity_matches=sum(
            findings[finding_index].severity
            == case.expected_findings[expected_index].severity
            for expected_index, finding_index in matches.items()
        ),
        retrieval_evaluated=relevant_total > 0,
        retrieval_relevant=sum(grade >= 2 for grade in retrieval_grades),
        retrieval_relevant_total=relevant_total,
        retrieved_ids=retrieved_ids,
        retrieval_returned=len(retrieved_ids),
        retrieval_judged=sum(
            source_id in case.retrieval_judgments for source_id in retrieved_ids
        ),
        retrieval_irrelevant=sum(grade == 0 for grade in retrieval_grades),
        retrieval_reciprocal_rank=(
            1.0 / min(relevant_ranks) if relevant_ranks else 0.0
        ),
        retrieval_ndcg=ndcg_at_k(
            retrieval_grades,
            list(case.retrieval_judgments.values()),
            k=3,
        ),
        citation_faithful=(
            len(matches) == len(case.expected_findings)
            and observed_citations <= known_citations
            and matched_citations_are_faithful
        ),
        hallucinated_line_numbers=hallucinated_lines,
        question_relevant=question_relevant,
        latency_ms=latency_ms,
    )


def match_expected_findings(
    case: ReviewExpectations,
    findings: list[CodeFinding],
) -> dict[int, int]:
    """Match each expectation to one finding using its atomic identity."""

    matches: dict[int, int] = {}
    available_findings = set(range(len(findings)))
    for expected_index, expected in enumerate(case.expected_findings):
        finding_index = next(
            (
                index
                for index in sorted(available_findings)
                if findings[index].id.startswith(expected.id_prefix)
                and findings[index].category == expected.category
            ),
            None,
        )
        if finding_index is not None:
            matches[expected_index] = finding_index
            available_findings.remove(finding_index)
    return matches
