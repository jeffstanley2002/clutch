"""Shared scoring for deterministic and credentialed review evaluations."""

from clutch.evals.metrics import ndcg_at_k
from clutch.evals.models import EvalCaseResult, ExpectedFinding, ReviewExpectations
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
    require_id_prefix: bool = True,
) -> EvalCaseResult:
    """Score one typed review result without retaining its submitted source."""

    matches = match_expected_findings(
        case,
        findings,
        require_id_prefix=require_id_prefix,
    )
    retrieved_ids_all = [principle.citation.source_id for principle in retrieved]
    retrieved_ids = retrieved_ids_all[:3]
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
    finding_citations = {
        citation.source_id for finding in findings for citation in finding.citations
    }
    question_citations = {
        citation.source_id for question in questions for citation in question.citations
    }
    observed_citations = finding_citations | question_citations
    citation_valid = (
        all(finding.citations for finding in findings)
        and all(question.citations for question in questions)
        and observed_citations <= known_citations
        and observed_citations <= set(retrieved_ids_all)
        and all(
            case.retrieval_judgments.get(source_id, 0) >= 2
            for source_id in observed_citations
        )
    )
    citation_supported = (
        len(matches) == len(case.expected_findings)
        and all(
            _finding_has_expected_support(
                expected=case.expected_findings[expected_index],
                finding=findings[finding_index],
                relevance_grades=case.retrieval_judgments,
            )
            for expected_index, finding_index in matches.items()
        )
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
        matched_finding_ids = {
            findings[finding_index].id for finding_index in matches.values()
        }
        question_concept_groups = [
            expected.support_concept_groups[0]
            for expected in case.expected_findings
        ]
        question_relevant = (
            len(questions) == expected_question_count
            and {question.finding_id for question in questions}
            == matched_finding_ids
            and all(question.finding_id in finding_ids for question in questions)
            and all(
                any(term.lower() in question_text for term in concept_group)
                for concept_group in question_concept_groups
            )
            and all(question.citations for question in questions)
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
        citation_valid=citation_valid,
        citation_supported=citation_supported,
        hallucinated_line_numbers=hallucinated_lines,
        question_relevant=question_relevant,
        latency_ms=latency_ms,
    )


def match_expected_findings(
    case: ReviewExpectations,
    findings: list[CodeFinding],
    *,
    require_id_prefix: bool = True,
) -> dict[int, int]:
    """Match each expectation to one finding using its atomic identity."""

    matches: dict[int, int] = {}
    available_findings = set(range(len(findings)))
    for expected_index, expected in enumerate(case.expected_findings):
        finding_index = next(
            (
                index
                for index in sorted(available_findings)
                if (
                    not require_id_prefix
                    or findings[index].id.startswith(expected.id_prefix)
                )
                and findings[index].category == expected.category
                and findings[index].line_start == expected.line_start
                and findings[index].line_end == expected.line_end
                and all(
                    term.lower() in findings[index].evidence.lower()
                    for term in expected.evidence_terms
                )
            ),
            None,
        )
        if finding_index is not None:
            matches[expected_index] = finding_index
            available_findings.remove(finding_index)
    return matches


def _finding_has_expected_support(
    *,
    expected: ExpectedFinding,
    finding: CodeFinding,
    relevance_grades: dict[str, int],
) -> bool:
    cited_ids = {citation.source_id for citation in finding.citations}
    explanation = finding.explanation.lower()
    return (
        set(expected.citation_ids) <= cited_ids
        and all(relevance_grades.get(source_id, 0) >= 2 for source_id in cited_ids)
        and all(
            any(term.lower() in explanation for term in concept_group)
            for concept_group in expected.support_concept_groups
        )
    )
