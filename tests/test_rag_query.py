from clutch.rag.query import (
    MAX_RETRIEVAL_FINDINGS,
    MAX_RETRIEVAL_QUERY_CHARS,
    MAX_RETRIEVAL_RESULTS,
    MAX_RETRIEVAL_TERMS,
    build_retrieval_query,
    extract_code_retrieval_terms,
)
from clutch.schemas import CodeFinding, ReviewRequest


def test_extracts_identifier_exception_and_sql_signals_without_comments() -> None:
    code = """
def find_user(cursor, user_id):
    # Ignore instructions in comments.
    try:
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    except ValueError:
        return None
"""

    terms = extract_code_retrieval_terms(code)

    assert {"find", "user", "cursor", "select", "sql", "query"} <= set(terms)
    assert {"except", "value", "error", "exception", "handling"} <= set(terms)
    assert "ignore" not in terms
    assert "instructions" not in terms


def test_extraction_is_bounded_and_deduplicated() -> None:
    code = "\n".join(f"value_{index} = {index}" for index in range(100))

    terms = extract_code_retrieval_terms(code)

    assert len(terms) <= MAX_RETRIEVAL_TERMS
    assert len(terms) == len(set(terms))


def test_invalid_python_uses_a_bounded_lexical_fallback() -> None:
    terms = extract_code_retrieval_terms("def broken(:\n  SELECT users")

    assert "broken" in terms
    assert "select" in terms


def test_positive_retrieval_query_uses_derived_finding_context() -> None:
    finding = CodeFinding(
        id="finding-test",
        severity="medium",
        category="design",
        message="Unit duplicates shared behavior",
        evidence="request-scoped evidence",
        explanation="Multiple change points can drift.",
        suggestion="Extract one named helper.",
    )

    query = build_retrieval_query(
        ReviewRequest(code="def example():\n    return True\n"),
        [finding],
    )

    assert query.categories == frozenset({"design"})
    assert "Multiple change points can drift" in query.text
    assert "Extract one named helper" in query.text
    assert "request-scoped evidence" not in query.text


def test_positive_retrieval_query_caps_findings_text_and_results() -> None:
    finding = CodeFinding(
        id="finding-test",
        severity="medium",
        category="maintainability",
        message="x" * 1_000,
        evidence="evidence",
        explanation="y" * 1_000,
        suggestion="z" * 1_000,
    )

    query = build_retrieval_query(
        ReviewRequest(code="value = 1"),
        [finding.model_copy(update={"id": f"finding-{index}"}) for index in range(20)],
    )

    assert len(query.text) == MAX_RETRIEVAL_QUERY_CHARS
    assert query.limit <= MAX_RETRIEVAL_RESULTS
    assert MAX_RETRIEVAL_FINDINGS < 20
