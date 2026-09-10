import tomllib
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).parents[1] / "frontend" / "app.py"
SECRETS_EXAMPLE_PATH = Path(__file__).parents[1] / ".streamlit" / "secrets.example.toml"


def _review_result(*, mode: str = "static_fallback") -> dict[str, object]:
    return {
        "findings": [
            {
                "id": "finding-1",
                "severity": "medium",
                "category": "maintainability",
                "message": "Finish the temporary implementation",
                "evidence": "# TODO replace",
                "line_start": 2,
                "line_end": 2,
                "explanation": "The marker identifies unfinished behavior.",
                "suggestion": "Replace it and add a regression test.",
                "origin": (
                    "ai_generated" if mode == "model" else "deterministic_static"
                ),
                "citations": [
                    {
                        "source_id": "seed.reference.todo",
                        "title": "Google Engineering Practices",
                        "url": (
                            "https://google.github.io/eng-practices/review/"
                            "reviewer/looking-for.html#good-code-reviews"
                        ),
                        "origin": "retrieved_citation",
                    }
                ],
            }
        ],
        "questions": [
            {
                "id": "question-1",
                "finding_id": "finding-1",
                "question": "How would you verify the completed behavior?",
                "intent": "Assess test reasoning.",
                "difficulty": "medium",
                "origin": ("ai_generated" if mode == "model" else "template_generated"),
                "citations": [],
            }
        ],
        "mode": mode,
        "confidence": 0.7,
        "request_id": "request-1",
        "latency_ms": 12.5,
        "provenance": [
            {
                "stage": "review_synthesis",
                "status": "succeeded" if mode == "model" else "fallback",
                "origin": (
                    "ai_generated" if mode == "model" else "deterministic_static"
                ),
                "model_name": "gpt-5.4-mini" if mode == "model" else None,
                "prompt_version": "review.v2" if mode == "model" else None,
                "input_tokens": 100 if mode == "model" else None,
                "output_tokens": 40 if mode == "model" else None,
                "latency_ms": 10.0,
                "estimated_cost_usd": 0.001 if mode == "model" else 0.0,
                "attempt_count": 1 if mode == "model" else 0,
                "validation_failure_count": 0,
                "failure_category": (
                    None if mode == "model" else "model_not_configured"
                ),
            }
        ],
    }


def test_review_ui_labels_fallback_items_citations_and_github_scope() -> None:
    app = AppTest.from_file(str(APP_PATH)).run()
    app.session_state["review_result"] = _review_result()
    app.session_state["github_ingestion"] = {
        "source_type": "repository",
        "owner": "example",
        "repository": "project",
        "ref": "main",
        "pull_number": None,
        "files_included": ["app.py", "tests/test_app.py"],
        "skipped_file_count": 4,
        "total_bytes": 1200,
        "truncated": True,
    }
    app.run()

    warning_text = " ".join(item.value for item in app.warning)
    caption_text = " ".join(item.value for item in app.caption)
    markdown_text = " ".join(item.value for item in app.markdown)
    assert "No successful review model call occurred" in warning_text
    assert "Deterministic static finding" in caption_text
    assert "Template-generated follow-up question" in caption_text
    assert (
        "Included 2 files · skipped 4 · truncated: yes · full-codebase analysis: no"
    ) in caption_text
    assert "Google Engineering Practices — #good-code-reviews" in markdown_text


def test_review_ui_labels_successful_model_output() -> None:
    app = AppTest.from_file(str(APP_PATH)).run()
    app.session_state["review_result"] = _review_result(mode="model")
    app.run()

    assert any(
        "AI-generated review synthesis completed" in item.value for item in app.success
    )
    caption_text = " ".join(item.value for item in app.caption)
    assert "AI-generated review finding" in caption_text
    assert "AI-generated follow-up question" in caption_text


def test_auth_configured_shows_landing_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CLUTCH_DISABLE_STREAMLIT_LOGIN", raising=False)
    app = AppTest.from_file(str(APP_PATH))
    app.secrets["auth"] = {
        "redirect_uri": "http://localhost:8501/oauth2callback",
        "cookie_secret": "test-cookie-secret",
        "client_id": "test-client-id",
        "client_secret": "test-client-secret",
        "server_metadata_url": (
            "https://accounts.google.com/.well-known/openid-configuration"
        ),
    }

    app.run()

    assert any("Log in with Google" in item.label for item in app.button)
    markdown_text = " ".join(item.value for item in app.markdown)
    assert "Clutch turns code review into interview prep" in markdown_text
    assert "From code to signal" in markdown_text
    assert "Google handles authentication" in markdown_text
    assert "Recruiters" not in markdown_text
    assert "pretending to be AI" not in markdown_text
    assert "Review the evidence" not in markdown_text


def test_streamlit_secrets_example_keeps_api_settings_at_root() -> None:
    with SECRETS_EXAMPLE_PATH.open("rb") as secrets_file:
        secrets = tomllib.load(secrets_file)

    assert secrets["CLUTCH_API_BASE_URL"] == "http://127.0.0.1:8000"
    assert secrets["CLUTCH_API_KEY"]
    assert secrets["auth"]["redirect_uri"].endswith("/oauth2callback")
    assert "CLUTCH_API_BASE_URL" not in secrets["auth"]
    assert "CLUTCH_API_KEY" not in secrets["auth"]
