from clutch.rag.query import MAX_RETRIEVAL_TERMS, extract_code_retrieval_terms


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
