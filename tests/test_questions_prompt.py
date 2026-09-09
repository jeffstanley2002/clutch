import json

from clutch.knowledge_base import retrieve_clean_code_principles
from clutch.parsing import parse_python_code
from clutch.prompts.questions import build_questions_prompt
from clutch.review.static import run_static_review
from clutch.schemas import ReviewRequest


def test_questions_prompt_is_bounded_grounded_and_excludes_raw_evidence() -> None:
    sentinel = "RAW_CODE_SENTINEL_MUST_NOT_ENTER_QUESTIONS"
    request = ReviewRequest(
        code=(
            "def load():\n"
            f"    value = '{sentinel}'\n"
            "    try:\n"
            "        return work(value)\n"
            "    except:\n"
            "        return None\n"
        )
    )
    findings = run_static_review(request, parsed_code=parse_python_code(request.code))
    principles = retrieve_clean_code_principles(
        "narrow exception handling",
        categories={"correctness"},
        limit=3,
    )

    prompt = build_questions_prompt(
        role_context=request.role_context,
        findings=findings,
        principles=principles,
    )
    payload = json.loads(prompt.user.split("\n\n", 1)[1])

    assert prompt.version == "questions.v1"
    assert len(payload["validated_findings"]) <= 3
    assert len(payload["grounding_items"]) <= 8
    assert sentinel not in prompt.user
    assert set(payload["grounding_items"][0]) == {
        "atomic_claim",
        "guidance",
        "kind",
        "source_id",
        "title",
    }
