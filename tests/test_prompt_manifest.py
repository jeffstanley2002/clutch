import json
from pathlib import Path

from clutch.prompts.manifest import load_and_validate_prompt_manifest


def test_prompt_manifest_hashes_every_production_prompt() -> None:
    manifest = load_and_validate_prompt_manifest()

    assert {entry.version for entry in manifest.prompts} == {
        "review.v2",
        "questions.v1",
        "interview_assessment.v1",
    }
    baseline = json.loads(
        (
            Path(__file__).parents[1]
            / "evals"
            / "baselines"
            / "live-current.json"
        ).read_text(encoding="utf-8")
    )
    assert baseline["evaluation_mode"] == "live_model"
    assert baseline["passed"] is True
