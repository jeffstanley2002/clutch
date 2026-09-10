"""Validation for immutable prompt versions and their committed content hashes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, Field

from clutch.prompts.interview_assessment import (
    PROMPT_VERSION as INTERVIEW_ASSESSMENT_VERSION,
)
from clutch.prompts.questions import PROMPT_VERSION as QUESTIONS_VERSION
from clutch.prompts.review import PROMPT_VERSION as REVIEW_VERSION

PROMPT_ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = PROMPT_ROOT / "manifest.json"
CURRENT_BASELINE_PATH = (
    PROMPT_ROOT.parents[2] / "evals" / "baselines" / "live-current.json"
)


class PromptManifestEntry(BaseModel):
    name: str = Field(..., min_length=1)
    version: str = Field(..., pattern=r"^[a-z_]+\.v[1-9][0-9]*$")
    module_file: str = Field(..., pattern=r"^[a-z0-9_]+\.py$")
    system_file: str = Field(..., pattern=r"^[a-z0-9_]+\.txt$")
    content_sha256: str = Field(..., pattern=r"^[a-f0-9]{64}$")


class PromptManifest(BaseModel):
    schema_version: int = 1
    prompts: list[PromptManifestEntry] = Field(..., min_length=3)


def prompt_content_sha256(entry: PromptManifestEntry) -> str:
    """Hash both executable prompt assembly and its system instruction text."""

    digest = hashlib.sha256()
    for file_name in (entry.module_file, entry.system_file):
        digest.update((PROMPT_ROOT / file_name).read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def load_and_validate_prompt_manifest() -> PromptManifest:
    """Reject stale hashes, duplicate versions, and code/version disagreement."""

    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest = PromptManifest.model_validate(payload)
    expected_versions = {
        "review": REVIEW_VERSION,
        "questions": QUESTIONS_VERSION,
        "interview_assessment": INTERVIEW_ASSESSMENT_VERSION,
    }
    entries_by_name = {entry.name: entry for entry in manifest.prompts}
    if len(entries_by_name) != len(manifest.prompts):
        raise ValueError("prompt manifest names must be unique")
    if set(entries_by_name) != set(expected_versions):
        raise ValueError("prompt manifest must cover every production prompt")
    for name, expected_version in expected_versions.items():
        entry = entries_by_name[name]
        if entry.version != expected_version:
            raise ValueError(f"prompt version mismatch for {name}")
        if entry.content_sha256 != prompt_content_sha256(entry):
            raise ValueError(f"prompt content hash is stale for {name}")
    baseline = json.loads(
        CURRENT_BASELINE_PATH.read_text(encoding="utf-8")
    )
    baseline_versions = baseline.get("prompt_versions")
    expected_hashes = {
        entry.version: entry.content_sha256 for entry in manifest.prompts
    }
    if baseline_versions != expected_hashes:
        raise ValueError("prompt changes require a refreshed baseline artifact")
    if baseline.get("evaluation_mode") != "live_model" or baseline.get("passed") is not True:
        raise ValueError("current prompt baseline must be a passing live-model run")
    return manifest
