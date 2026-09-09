"""Bounded prompt assembly for grounded interview-question generation."""

import json
from collections.abc import Sequence
from importlib.resources import files

from clutch.knowledge_base import CleanCodePrinciple
from clutch.prompts.review import PromptBundle
from clutch.schemas import CodeFinding

MAX_QUESTION_FINDINGS = 3
MAX_QUESTION_PRINCIPLES = 8
PROMPT_VERSION = "questions.v1"


def build_questions_prompt(
    *,
    role_context: str,
    findings: Sequence[CodeFinding],
    principles: Sequence[CleanCodePrinciple],
) -> PromptBundle:
    """Build a source-free question prompt from validated, grounded findings."""

    system = (
        files("clutch.prompts")
        .joinpath("questions_system_v1.txt")
        .read_text(encoding="utf-8")
        .strip()
    )
    payload = {
        "target_role": role_context,
        "validated_findings": [
            {
                "finding_id": finding.id,
                "severity": finding.severity,
                "category": finding.category,
                "message": finding.message,
                "explanation": finding.explanation,
                "suggestion": finding.suggestion,
                "citation_ids": [
                    citation.source_id for citation in finding.citations
                ],
            }
            for finding in findings[:MAX_QUESTION_FINDINGS]
        ],
        "grounding_items": [
            {
                "source_id": principle.id,
                "kind": principle.item_type,
                "title": principle.title,
                "atomic_claim": principle.summary,
                "guidance": principle.guidance,
            }
            for principle in principles[:MAX_QUESTION_PRINCIPLES]
        ],
    }
    user = (
        "Generate at most three interview follow-up questions from this trusted "
        "application payload. Each question must name exactly one supplied "
        "finding_id and cite only supplied source_id values.\n\n"
        + json.dumps(payload, ensure_ascii=True, sort_keys=True)
    )
    return PromptBundle(version=PROMPT_VERSION, system=system, user=user)
