"""Seeded clean-code knowledge base and deterministic retrieval."""

import re

from pydantic import BaseModel, Field

from clutch.schemas import Citation, FindingCategory


class CleanCodePrinciple(BaseModel):
    """A review principle that can ground findings and interview questions."""

    id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    category: FindingCategory
    summary: str = Field(..., min_length=1)
    guidance: str = Field(..., min_length=1)
    tags: list[str] = Field(default_factory=list)
    citation: Citation


SEED_CLEAN_CODE_PRINCIPLES: tuple[CleanCodePrinciple, ...] = (
    CleanCodePrinciple(
        id="seed.clean_code.explicit_incomplete_work",
        title="Make incomplete work explicit and actionable",
        category="maintainability",
        summary=(
            "Unresolved TODOs and FIXMEs should communicate remaining scope, "
            "risk, ownership, or a tracked follow-up."
        ),
        guidance=(
            "Interview reviewers should be able to tell whether unfinished work is "
            "intentional, acceptable for the current scope, and safely tracked."
        ),
        tags=["todo", "fixme", "scope", "maintainability", "tradeoff"],
        citation=Citation(
            source_id="seed.clean_code.explicit_incomplete_work",
            title="Seed clean-code principle: make incomplete work explicit",
        ),
    ),
    CleanCodePrinciple(
        id="seed.clean_code.boundary_observability",
        title="Use intentional observability at system boundaries",
        category="maintainability",
        summary=(
            "Production behavior should rely on intentional logs or traces rather "
            "than stray debug prints."
        ),
        guidance=(
            "Prefer structured logging where behavior crosses an API, job, or user "
            "workflow boundary, and remove local debugging output before review."
        ),
        tags=["print", "logging", "observability", "debug", "boundary"],
        citation=Citation(
            source_id="seed.clean_code.boundary_observability",
            title="Seed clean-code principle: intentional boundary observability",
        ),
    ),
    CleanCodePrinciple(
        id="seed.clean_code.narrow_error_handling",
        title="Preserve failure context with narrow error handling",
        category="correctness",
        summary=(
            "Catch only exceptions the code can handle and keep enough context to "
            "debug unexpected failures."
        ),
        guidance=(
            "A bare except can hide programmer errors, interrupts, and important "
            "runtime details that interviewers expect candidates to reason about."
        ),
        tags=["except", "exception", "error", "failure", "correctness"],
        citation=Citation(
            source_id="seed.clean_code.narrow_error_handling",
            title="Seed clean-code principle: narrow error handling",
        ),
    ),
    CleanCodePrinciple(
        id="seed.clean_code.safe_python_defaults",
        title="Avoid shared mutable Python defaults",
        category="correctness",
        summary=(
            "Mutable default arguments are created once at function definition time "
            "and can leak state between calls."
        ),
        guidance=(
            "Use None as the default for lists, dicts, and sets, then create a fresh "
            "object inside the function."
        ),
        tags=["mutable", "default", "argument", "list", "dict", "python"],
        citation=Citation(
            source_id="seed.clean_code.safe_python_defaults",
            title="Seed clean-code principle: avoid shared mutable Python defaults",
        ),
    ),
    CleanCodePrinciple(
        id="seed.clean_code.small_reviewable_units",
        title="Keep units small enough to review and test",
        category="design",
        summary=(
            "Functions, classes, and pasted snippets should be small enough that a "
            "reviewer can identify responsibilities and test boundaries."
        ),
        guidance=(
            "Extract distinct decisions into named helpers when a unit grows large "
            "enough to obscure behavior, dependencies, or edge cases."
        ),
        tags=["large", "function", "class", "snippet", "extraction", "design"],
        citation=Citation(
            source_id="seed.clean_code.small_reviewable_units",
            title="Seed clean-code principle: small reviewable units",
        ),
    ),
    CleanCodePrinciple(
        id="seed.clean_code.behavioral_test_boundaries",
        title="Test behavior at meaningful boundaries",
        category="testing",
        summary=(
            "Tests should cover expected behavior, important edge cases, and the "
            "boundaries where code collaborates with other systems."
        ),
        guidance=(
            "When no deterministic issue is found, the next useful interview signal "
            "is usually whether the candidate can explain and test the behavior."
        ),
        tags=["tests", "behavior", "edge", "boundary", "confidence"],
        citation=Citation(
            source_id="seed.clean_code.behavioral_test_boundaries",
            title="Seed clean-code principle: behavioral test boundaries",
        ),
    ),
)


def retrieve_clean_code_principles(
    query: str,
    *,
    categories: set[FindingCategory] | None = None,
    limit: int = 3,
) -> list[CleanCodePrinciple]:
    """Return the highest-scoring seed principles for a short review query."""

    if limit < 1:
        return []

    query_terms = set(_tokenize(query))
    scored_principles = []

    for principle in SEED_CLEAN_CODE_PRINCIPLES:
        if categories is not None and principle.category not in categories:
            continue

        searchable_text = " ".join(
            [
                principle.title,
                principle.summary,
                principle.guidance,
                " ".join(principle.tags),
            ]
        )
        principle_terms = set(_tokenize(searchable_text))
        overlap = query_terms & principle_terms
        tag_overlap = query_terms & set(principle.tags)
        score = len(overlap) + (2 * len(tag_overlap))

        if score > 0:
            scored_principles.append((score, principle.id, principle))

    scored_principles.sort(key=lambda item: (-item[0], item[1]))
    return [principle for _, _, principle in scored_principles[:limit]]


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", text.lower())
