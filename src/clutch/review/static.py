"""Deterministic static review grounded by the seed knowledge base."""

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
        *_find_long_units(parsed_code),
        *_find_long_snippet(lines, parsed_code),
    ]

    if findings:
        return findings

    return [
        CodeFinding(
            id="finding-001",
            severity="low",
            category="readability",
            message="No obvious deterministic issues found",
            evidence="Submitted Python snippet",
            explanation=(
                "The Day 1 reviewer only checks a small deterministic rule set. "
                "A future parser, retrieval layer, and model-backed reviewer will "
                "look for deeper design and correctness issues."
            ),
            suggestion=(
                "Add tests around expected behavior and resubmit once the richer "
                "review agent is wired in."
            ),
            citations=_citations_for(
                "tests expected behavior boundary confidence",
                category="testing",
            ),
        )
    ]


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
