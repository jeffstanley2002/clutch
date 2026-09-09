"""Validated local knowledge corpus and deterministic lexical retrieval."""

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, model_validator

from clutch.schemas import Citation, FindingCategory

KnowledgeItemKind = Literal["reference", "rubric", "question_bank"]
SeniorityLevel = Literal["intern", "junior", "mid", "senior"]
SourceFamily = Literal[
    "python_docs",
    "python_pep",
    "owasp_cheat_sheet",
    "pytest_docs",
    "unittest_docs",
    "google_engineering_practices",
    "google_python_style",
]
CORPUS_PATH = Path(__file__).with_name("corpus.json")
EXPECTED_CORPUS_VERSION = "2026-09-09.v1"
EXPECTED_TYPE_COUNTS = {"reference": 72, "rubric": 18, "question_bank": 30}
ALLOWED_SOURCE_HOSTS = {
    "docs.python.org",
    "peps.python.org",
    "cheatsheetseries.owasp.org",
    "docs.pytest.org",
    "google.github.io",
}
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
    source_family: SourceFamily
    section_locator: str = Field(..., pattern=r"^#[A-Za-z0-9._:-]+$")
    corpus_version: str = Field(..., min_length=1)
    content_sha256: str = Field(..., pattern=r"^[a-f0-9]{64}$")
    derived_from_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_source_provenance(self) -> "CleanCodePrinciple":
        if self.corpus_version != EXPECTED_CORPUS_VERSION:
            raise ValueError("knowledge item uses an unexpected corpus version")
        if not self.citation.url:
            raise ValueError("knowledge item citation requires an anchored URL")
        parsed = urlparse(self.citation.url)
        if parsed.scheme != "https" or parsed.netloc not in ALLOWED_SOURCE_HOSTS:
            raise ValueError("knowledge item citation source is not allowlisted")
        if f"#{parsed.fragment}" != self.section_locator:
            raise ValueError("section locator must match the citation URL anchor")
        expected_hash = hashlib.sha256(
            f"{self.summary}\n{self.guidance}".encode()
        ).hexdigest()
        if self.content_sha256 != expected_hash:
            raise ValueError("knowledge item content hash is stale")
        if self.item_type == "reference" and self.derived_from_ids:
            raise ValueError("authoritative references cannot derive from corpus items")
        if self.item_type != "reference" and not self.derived_from_ids:
            raise ValueError("rubrics and questions require an authoritative derivation")
        if len(self.derived_from_ids) != len(set(self.derived_from_ids)):
            raise ValueError("derived knowledge IDs must be unique")
        return self


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
    type_counts = Counter(principle.item_type for principle in principles)
    if type_counts != EXPECTED_TYPE_COUNTS:
        raise ValueError(
            f"knowledge corpus item-type balance must be {EXPECTED_TYPE_COUNTS}"
        )
    category_counts = Counter(principle.category for principle in principles)
    if any(category_counts[category] != 20 for category in category_counts):
        raise ValueError("knowledge corpus must contain 20 items per category")
    by_id = {principle.id: principle for principle in principles}
    invalid_derivations = []
    for principle in principles:
        for source_id in principle.derived_from_ids:
            source = by_id.get(source_id)
            if (
                source is None
                or source.item_type != "reference"
                or source.category != principle.category
            ):
                invalid_derivations.append(f"{principle.id}->{source_id}")
    if invalid_derivations:
        raise ValueError(
            "knowledge derivations must target same-category references: "
            + ", ".join(invalid_derivations)
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
