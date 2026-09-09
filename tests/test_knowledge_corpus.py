import json
from collections import Counter
from pathlib import Path

import pytest
from pydantic import ValidationError

from clutch.knowledge_base.clean_code import (
    ALLOWED_SOURCE_HOSTS,
    CORPUS_PATH,
    EXPECTED_CORPUS_VERSION,
    EXPECTED_TYPE_COUNTS,
    SEED_CLEAN_CODE_PRINCIPLES,
    load_clean_code_corpus,
)


def _payload() -> list[dict[str, object]]:
    value = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, list)
    return value


def _write_payload(tmp_path: Path, payload: list[dict[str, object]]) -> Path:
    path = tmp_path / "corpus.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_corpus_is_exactly_balanced_and_fully_source_traceable() -> None:
    assert len(SEED_CLEAN_CODE_PRINCIPLES) == 120
    assert Counter(item.item_type for item in SEED_CLEAN_CODE_PRINCIPLES) == (
        EXPECTED_TYPE_COUNTS
    )
    assert set(Counter(item.category for item in SEED_CLEAN_CODE_PRINCIPLES).values()) == {
        20
    }
    assert all(
        item.corpus_version == EXPECTED_CORPUS_VERSION
        and item.citation.url is not None
        and item.section_locator in item.citation.url
        and len(item.content_sha256) == 64
        for item in SEED_CLEAN_CODE_PRINCIPLES
    )


def test_corpus_rejects_missing_source_url(tmp_path: Path) -> None:
    payload = _payload()
    citation = payload[0]["citation"]
    assert isinstance(citation, dict)
    citation.pop("url")

    with pytest.raises(ValidationError, match="anchored URL"):
        load_clean_code_corpus(_write_payload(tmp_path, payload))


def test_corpus_rejects_non_allowlisted_source(tmp_path: Path) -> None:
    payload = _payload()
    citation = payload[0]["citation"]
    assert isinstance(citation, dict)
    citation["url"] = "https://example.com/style#rule"
    payload[0]["section_locator"] = "#rule"

    with pytest.raises(ValidationError, match="not allowlisted"):
        load_clean_code_corpus(_write_payload(tmp_path, payload))


def test_corpus_rejects_stale_content_hash(tmp_path: Path) -> None:
    payload = _payload()
    payload[0]["guidance"] = "Changed without refreshing the content hash."

    with pytest.raises(ValidationError, match="content hash is stale"):
        load_clean_code_corpus(_write_payload(tmp_path, payload))


def test_corpus_rejects_invalid_derivation(tmp_path: Path) -> None:
    payload = _payload()
    rubric = next(item for item in payload if item["item_type"] == "rubric")
    rubric["derived_from_ids"] = ["missing.authoritative.reference"]

    with pytest.raises(ValueError, match="same-category references"):
        load_clean_code_corpus(_write_payload(tmp_path, payload))


def test_allowlist_is_narrow_and_documentation_only() -> None:
    assert ALLOWED_SOURCE_HOSTS == {
        "docs.python.org",
        "peps.python.org",
        "cheatsheetseries.owasp.org",
        "docs.pytest.org",
        "google.github.io",
    }
