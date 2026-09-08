"""Privacy-bounded lexical signals for knowledge retrieval."""

import ast
import io
import re
import tokenize

from pydantic import BaseModel, ConfigDict, Field

from clutch.schemas import CodeFinding, FindingCategory, ReviewRequest

MAX_RETRIEVAL_TERMS = 40
MAX_STRING_CHARS = 500
MAX_RETRIEVAL_FINDINGS = 8
MAX_RETRIEVAL_QUERY_CHARS = 4_000
MAX_RETRIEVAL_RESULTS = 8
_IGNORED_NAMES = {
    "as",
    "async",
    "await",
    "class",
    "def",
    "else",
    "for",
    "from",
    "if",
    "import",
    "in",
    "is",
    "lambda",
    "none",
    "pass",
    "return",
    "true",
    "while",
    "with",
    "yield",
}
_SQL_TERMS = {"select", "insert", "update", "delete"}


class RetrievalQuery(BaseModel):
    """Bounded derived query passed to a knowledge retriever."""

    model_config = ConfigDict(frozen=True)

    text: str = Field(..., min_length=1, max_length=MAX_RETRIEVAL_QUERY_CHARS)
    categories: frozenset[FindingCategory] | None = None
    limit: int = Field(default=3, ge=1, le=MAX_RETRIEVAL_RESULTS)


def build_retrieval_query(
    request: ReviewRequest,
    findings: list[CodeFinding],
) -> RetrievalQuery:
    """Build bounded grounding context without retaining raw submitted source."""

    selected_findings = findings[:MAX_RETRIEVAL_FINDINGS]
    if selected_findings:
        parts = [
            request.role_context,
            "rubric question interview",
            *(finding.message for finding in selected_findings),
            *(finding.explanation for finding in selected_findings),
            *(finding.suggestion for finding in selected_findings),
            *(finding.category for finding in selected_findings),
        ]
        categories: frozenset[FindingCategory] | None = frozenset(
            finding.category for finding in selected_findings
        )
        limit = min(
            MAX_RETRIEVAL_RESULTS,
            max(
                3,
                sum(len(finding.citations) for finding in selected_findings),
            ),
        )
    else:
        code_terms = extract_code_retrieval_terms(request.code)
        parts = [
            request.role_context,
            "rubric",
            "maintainability readability correctness testing design security",
            *code_terms,
        ]
        categories = None
        limit = 3

    return RetrievalQuery(
        text=" ".join(parts)[:MAX_RETRIEVAL_QUERY_CHARS].rstrip(),
        categories=categories,
        limit=limit,
    )


def extract_code_retrieval_terms(code: str) -> list[str]:
    """Extract bounded identifiers/literal words without retaining source text."""

    terms: list[str] = []
    try:
        tokens = tokenize.generate_tokens(io.StringIO(code).readline)
        for token in tokens:
            if token.type == tokenize.NAME:
                terms.extend(_identifier_terms(token.string))
            elif token.type == tokenize.STRING:
                terms.extend(_literal_terms(token.string))
            if len(terms) >= MAX_RETRIEVAL_TERMS:
                break
    except (IndentationError, SyntaxError, tokenize.TokenError):
        terms.extend(_word_terms(code[:MAX_STRING_CHARS]))

    normalized = _deduplicate(terms)
    if _SQL_TERMS & set(normalized):
        normalized.extend(["sql", "query", "database"])
    if "except" in normalized or any(term.endswith("error") for term in normalized):
        normalized.extend(["exception", "error", "handling"])
    return _deduplicate(normalized)[:MAX_RETRIEVAL_TERMS]


def _identifier_terms(identifier: str) -> list[str]:
    expanded = identifier.replace("_", " ")
    expanded = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", expanded)
    return _word_terms(expanded)


def _literal_terms(literal: str) -> list[str]:
    try:
        value = ast.literal_eval(literal)
    except (SyntaxError, ValueError):
        return []
    if not isinstance(value, str):
        return []
    return _word_terms(value[:MAX_STRING_CHARS])


def _word_terms(value: str) -> list[str]:
    return [
        term
        for term in re.findall(r"[a-z0-9]+", value.lower())
        if len(term) >= 2 and term not in _IGNORED_NAMES
    ]


def _deduplicate(terms: list[str]) -> list[str]:
    return list(dict.fromkeys(terms))
