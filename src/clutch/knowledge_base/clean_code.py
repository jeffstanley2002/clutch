"""Validated local knowledge corpus and deterministic lexical retrieval."""

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from clutch.schemas import Citation, FindingCategory

KnowledgeItemKind = Literal["reference", "rubric", "question_bank"]
SeniorityLevel = Literal["intern", "junior", "mid", "senior"]
CORPUS_PATH = Path(__file__).with_name("corpus.json")
_STOP_WORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "with",
}
_ROUTING_TERMS = {
    "backend",
    "correctness",
    "data",
    "design",
    "general",
    "intern",
    "interview",
    "junior",
    "library",
    "maintainability",
    "mid",
    "platform",
    "question",
    "readability",
    "rubric",
    "security",
    "senior",
    "testing",
}


def _default_seniority_levels() -> list[SeniorityLevel]:
    return ["intern", "junior"]


class CleanCodePrinciple(BaseModel):
    """A cited reference, rubric, or question-bank item used for grounding."""

    id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    category: FindingCategory
    summary: str = Field(..., min_length=1)
    guidance: str = Field(..., min_length=1)
    tags: list[str] = Field(default_factory=list)
    item_type: KnowledgeItemKind = "reference"
    roles: list[str] = Field(default_factory=lambda: ["general"])
    seniority_levels: list[SeniorityLevel] = Field(
        default_factory=_default_seniority_levels
    )
    citation: Citation


def load_clean_code_corpus(path: Path = CORPUS_PATH) -> tuple[CleanCodePrinciple, ...]:
    """Load and validate the committed corpus, including stable ID invariants."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"knowledge corpus must contain a JSON list: {path}")
    principles = tuple(CleanCodePrinciple.model_validate(item) for item in payload)
    identifiers = [principle.id for principle in principles]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("knowledge corpus source IDs must be unique")
    mismatches = [
        principle.id
        for principle in principles
        if principle.citation.source_id != principle.id
    ]
    if mismatches:
        raise ValueError(
            "knowledge corpus citation IDs must match item IDs: "
            + ", ".join(mismatches)
        )
    return principles


SEED_CLEAN_CODE_PRINCIPLES = load_clean_code_corpus()


def retrieve_clean_code_principles(
    query: str,
    *,
    categories: set[FindingCategory] | None = None,
    limit: int = 3,
) -> list[CleanCodePrinciple]:
    """Return the highest-scoring corpus items for a short review query."""

    if limit < 1:
        return []

    query_terms = set(_tokenize(query))
    issue_terms = query_terms - _ROUTING_TERMS
    scored_principles = []

    for principle in SEED_CLEAN_CODE_PRINCIPLES:
        if categories is not None and principle.category not in categories:
            continue

        title_terms = set(_tokenize(principle.title)) - _ROUTING_TERMS
        body_terms = set(
            _tokenize(f"{principle.summary} {principle.guidance}")
        ) - _ROUTING_TERMS
        tag_terms = set(principle.tags) - _ROUTING_TERMS
        tag_overlap = issue_terms & tag_terms
        title_overlap = issue_terms & title_terms
        body_overlap = issue_terms & body_terms
        role_bonus = int(bool(query_terms & set(principle.roles)))
        intent_bonus = int(
            (principle.item_type == "rubric" and "rubric" in query_terms)
            or (
                principle.item_type == "question_bank"
                and "question" in query_terms
            )
        )
        score = (
            (4 * len(tag_overlap))
            + (2 * len(title_overlap))
            + len(body_overlap)
            + role_bonus
            + intent_bonus
        )

        if score > 0:
            scored_principles.append((score, principle.id, principle))

    scored_principles.sort(key=lambda item: (-item[0], item[1]))
    return [principle for _, _, principle in scored_principles[:limit]]


def _tokenize(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9_]+", text.lower())
        if token not in _STOP_WORDS
    ]
