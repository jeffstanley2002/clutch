"""Deterministic static review grounded by the seed knowledge base."""

import re
from collections.abc import Iterable

from clutch.knowledge_base import retrieve_clean_code_principles
from clutch.schemas import (
    Citation,
    CodeFinding,
    FindingCategory,
    ParsedCode,
    ReviewRequest,
)


def run_static_review(
    request: ReviewRequest, *, parsed_code: ParsedCode | None = None
) -> list[CodeFinding]:
    """Return deterministic findings for the first local review endpoint."""

    lines = request.code.splitlines()
    findings = [
        *_find_todos(lines),
        *_find_debug_prints(lines),
        *_find_bare_excepts(lines),
        *_find_mutable_defaults(lines),
        *_find_insecure_sql(lines),
        *_find_long_units(parsed_code),
        *_find_duplicated_units(parsed_code),
        *_find_long_snippet(lines, parsed_code),
    ]

    return findings


def _find_todos(lines: list[str]) -> Iterable[CodeFinding]:
    for line_number, line in enumerate(lines, start=1):
        if "TODO" in line or "FIXME" in line:
            yield CodeFinding(
                id=f"finding-todo-{line_number}",
                severity="medium",
                category="maintainability",
                message="Unresolved TODO or FIXME left in code",
                evidence=line.strip(),
                line_start=line_number,
                line_end=line_number,
                explanation=(
                    "Interview reviewers often treat unresolved TODOs as a signal "
                    "that tradeoffs or incomplete behavior were not made explicit."
                ),
                suggestion=(
                    "Either complete the work or replace the marker with a clear "
                    "issue, owner, and decision about acceptable scope."
                ),
                citations=_citations_for(
                    "TODO FIXME incomplete work scope tradeoff",
                    category="maintainability",
                ),
            )


def _find_debug_prints(lines: list[str]) -> Iterable[CodeFinding]:
    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("print("):
            yield CodeFinding(
                id=f"finding-print-{line_number}",
                severity="low",
                category="maintainability",
                message="Debug print should not be the main observability path",
                evidence=stripped,
                line_start=line_number,
                line_end=line_number,
                explanation=(
                    "A stray print can make production behavior noisy and gives an "
                    "interviewer a reason to ask how the code would be monitored."
                ),
                suggestion=(
                    "Use structured logging at the boundary, or remove the print if "
                    "it was only used while debugging."
                ),
                citations=_citations_for(
                    "print debug logging observability boundary",
                    category="maintainability",
                ),
            )


def _find_bare_excepts(lines: list[str]) -> Iterable[CodeFinding]:
    for line_number, line in enumerate(lines, start=1):
        if line.strip().startswith("except:"):
            yield CodeFinding(
                id=f"finding-bare-except-{line_number}",
                severity="high",
                category="correctness",
                message="Bare except hides important failure modes",
                evidence=line.strip(),
                line_start=line_number,
                line_end=line_number,
                explanation=(
                    "Catching every exception can swallow programmer errors and "
                    "makes debugging or interview discussion much harder."
                ),
                suggestion=(
                    "Catch the narrow exception type you can handle, preserve useful "
                    "context, and let unexpected errors surface."
                ),
                citations=_citations_for(
                    "bare except exception failure context",
                    category="correctness",
                ),
            )


def _find_mutable_defaults(lines: list[str]) -> Iterable[CodeFinding]:
    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("def ") and ("=[]" in stripped or "={}" in stripped):
            yield CodeFinding(
                id=f"finding-mutable-default-{line_number}",
                severity="high",
                category="correctness",
                message="Mutable default argument can leak state between calls",
                evidence=stripped,
                line_start=line_number,
                line_end=line_number,
                explanation=(
                    "Python evaluates default arguments once, so a shared list or "
                    "dict can create surprising behavior across calls."
                ),
                suggestion=(
                    "Use None as the default, create the list or dict inside the "
                    "function, and type the parameter explicitly."
                ),
                citations=_citations_for(
                    "mutable default argument list dict python shared state",
                    category="correctness",
                ),
            )


def _find_insecure_sql(lines: list[str]) -> Iterable[CodeFinding]:
    sql_pattern = re.compile(r"\b(select|insert|update|delete)\b", re.IGNORECASE)

    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        lower = stripped.lower()
        is_interpolated = (
            lower.startswith(('f"', "f'"))
            or '= f"' in lower
            or "= f'" in lower
            or ".format(" in lower
        )
        if not is_interpolated or sql_pattern.search(stripped) is None:
            continue

        yield CodeFinding(
            id=f"finding-sql-interpolation-{line_number}",
            severity="high",
            category="security",
            message="SQL query interpolates values into command text",
            evidence=stripped,
            line_start=line_number,
            line_end=line_number,
            explanation=(
                "Building SQL with string interpolation can turn untrusted values "
                "into executable query syntax and makes the data boundary unclear."
            ),
            suggestion=(
                "Use the database driver's parameter binding and keep SQL structure "
                "separate from user-controlled values."
            ),
            citations=_citations_for(
                "sql query interpolation parameter binding injection security",
                category="security",
            ),
        )


def _find_long_units(parsed_code: ParsedCode | None) -> Iterable[CodeFinding]:
    if parsed_code is None:
        return

    for chunk in parsed_code.chunks:
        if chunk.symbol_kind not in {"class", "function"}:
            continue

        non_empty_lines = [
            line for line in chunk.source_text.splitlines() if line.strip()
        ]
        if len(non_empty_lines) <= 40:
            continue

        yield CodeFinding(
            id=f"finding-long-{chunk.symbol_kind}-{chunk.line_start}",
            severity="medium",
            category="design",
            message=(
                f"{chunk.symbol_kind.title()} is large enough to deserve extraction"
            ),
            evidence=(
                f"{chunk.symbol_kind.title()} `{chunk.symbol_name}` spans lines "
                f"{chunk.line_start}-{chunk.line_end}"
            ),
            line_start=chunk.line_start,
            line_end=chunk.line_end,
            explanation=(
                "Large functions or classes are harder to reason about, test, and "
                "discuss in an interview setting."
            ),
            suggestion=(
                "Split distinct responsibilities into named helpers and add tests "
                "for the behavior at each boundary."
            ),
            citations=_citations_for(
                f"large {chunk.symbol_kind} extraction small reviewable unit",
                category="design",
            ),
        )


def _find_duplicated_units(
    parsed_code: ParsedCode | None,
) -> Iterable[CodeFinding]:
    if parsed_code is None:
        return

    fingerprints: dict[str, list[tuple[str, int, int]]] = {}
    for chunk in parsed_code.chunks:
        if chunk.symbol_kind != "function":
            continue
        body_lines = chunk.source_text.splitlines()[1:]
        fingerprint = "\n".join(
            line.strip()
            for line in body_lines
            if line.strip() and not line.lstrip().startswith("#")
        )
        if len(fingerprint) < 20:
            continue
        fingerprints.setdefault(fingerprint, []).append(
            (chunk.symbol_name, chunk.line_start, chunk.line_end)
        )

    for matches in fingerprints.values():
        if len(matches) < 2:
            continue
        names = ", ".join(f"`{name}`" for name, _, _ in matches)
        first_line = min(line_start for _, line_start, _ in matches)
        last_line = max(line_end for _, _, line_end in matches)
        yield CodeFinding(
            id=f"finding-duplicated-functions-{first_line}",
            severity="medium",
            category="design",
            message="Multiple functions duplicate the same implementation",
            evidence=f"Functions {names} contain the same body",
            line_start=first_line,
            line_end=last_line,
            explanation=(
                "Duplicated behavior creates multiple change points and lets small "
                "fixes drift between otherwise equivalent paths."
            ),
            suggestion=(
                "Extract the shared behavior into one named helper and keep each "
                "caller responsible only for its distinct context."
            ),
            citations=_citations_for(
                "duplicated logic shared behavior extraction change points design",
                category="design",
            ),
        )


def _find_long_snippet(
    lines: list[str], parsed_code: ParsedCode | None
) -> Iterable[CodeFinding]:
    if parsed_code is not None and any(
        chunk.symbol_kind in {"class", "function"} for chunk in parsed_code.chunks
    ):
        return

    non_empty_lines = [line for line in lines if line.strip()]
    if len(non_empty_lines) <= 60:
        return

    yield CodeFinding(
        id="finding-long-snippet",
        severity="medium",
        category="design",
        message="Snippet is large enough to deserve smaller reviewable units",
        evidence=f"{len(non_empty_lines)} non-empty lines submitted",
        explanation=(
            "Large functions or pasted snippets are harder to reason about, test, "
            "and discuss in an interview setting."
        ),
        suggestion=(
            "Split distinct responsibilities into named helpers and add tests for "
            "the behavior at each boundary."
        ),
        citations=_citations_for(
            "large snippet extraction small reviewable unit",
            category="design",
        ),
    )


def _citations_for(query: str, *, category: FindingCategory) -> list[Citation]:
    principles = retrieve_clean_code_principles(query, categories={category}, limit=1)
    return [principle.citation for principle in principles]
