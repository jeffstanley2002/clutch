import ast
import tomllib
from pathlib import Path
from typing import Any, cast
from urllib.parse import unquote, urlparse

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


def _review_result_with_findings(count: int) -> dict[str, object]:
    result = _review_result()
    findings = cast(list[dict[str, Any]], result["findings"])
    base_finding = findings[0]
    result["findings"] = [
        {
            **base_finding,
            "id": f"finding-{index}",
            "message": f"Finding {index} needs attention",
            "evidence": f"# TODO replace {index}",
        }
        for index in range(1, count + 1)
    ]
    return result


def _load_github_url_validator() -> Any:
    tree = ast.parse(APP_PATH.read_text(encoding="utf-8"))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_github_url_validation_message"
    )
    module = ast.Module(body=[function], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {"unquote": unquote, "urlparse": urlparse}
    exec(compile(module, str(APP_PATH), "exec"), namespace)  # noqa: S102
    return namespace["_github_url_validation_message"]


def test_github_url_validator_accepts_only_supported_repo_and_pr_links() -> None:
    validate = _load_github_url_validator()

    assert validate("https://github.com/openai/openai-python") is None
    assert validate("https://github.com/openai/openai-python/pull/123") is None
    assert (
        validate("https://github.com/openai/openai-python?tab=readme-ov-file#readme")
        is None
    )
    assert validate("") == "Enter a GitHub repository or pull-request URL."
    assert validate("http://github.com/openai/openai-python") == (
        "Use an HTTPS github.com link."
    )
    assert "repository or pull request link" in validate(
        "https://github.com/openai/openai-python/tree/main"
    )


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
    assert "because AI review is not available right now" in warning_text
    assert "Deterministic static finding" in caption_text
    assert "Template-generated follow-up question" in caption_text
    assert (
        "Included 2 files · skipped 4 · truncated: yes · full-codebase analysis: no"
    ) in caption_text
    assert "Google Engineering Practices — #good-code-reviews" in markdown_text


def test_review_ui_paginates_long_finding_lists() -> None:
    app = AppTest.from_file(str(APP_PATH)).run()
    app.session_state["review_result"] = _review_result_with_findings(12)
    app.run()

    caption_text = " ".join(item.value for item in app.caption)
    markdown_text = " ".join(item.value for item in app.markdown)
    button_labels = [item.label for item in app.button]
    assert "Showing findings 1-5 of 12 · page 1 of 3" in caption_text
    assert "Finding 1 needs attention" in markdown_text
    assert "Finding 5 needs attention" in markdown_text
    assert "Finding 6 needs attention" not in markdown_text
    assert "Previous" in button_labels
    assert "Next" in button_labels


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


def test_authenticated_workbench_keeps_sidebar_logout_visible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CLUTCH_DISABLE_STREAMLIT_LOGIN", raising=False)
    app = AppTest.from_file(str(APP_PATH))
    app.secrets["stytch"] = {
        "project_id": "project-test-id",
        "secret": "secret-test-value",  # pragma: allowlist secret
        "environment": "test",
        "redirect_url": "http://localhost:8501",
    }
    app.session_state["stytch_session_jwt"] = "session-test-jwt"
    app.session_state["stytch_user_id"] = "user-test-id"
    app.session_state["stytch_user_email"] = "junior@example.com"

    app.run()

    caption_text = " ".join(item.value for item in app.caption)
    button_labels = [item.label for item in app.button]
    assert "Signed in as junior@example.com" in caption_text
    assert "Log out" in button_labels
    tree = ast.parse(APP_PATH.read_text(encoding="utf-8"))
    assert any(
        keyword.arg == "initial_sidebar_state"
        and isinstance(keyword.value, ast.Constant)
        and keyword.value.value == "expanded"
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for keyword in node.keywords
    )


def test_frontend_error_copy_does_not_expose_raw_runtime_details() -> None:
    source = APP_PATH.read_text(encoding="utf-8")

    forbidden_fragments = [
        "Technical detail",
        "Detail:",
        "_stytch_error_detail",
        "check the backend",
        "FastAPI is running",
        "redirect URL and API keys",
        "f\"{exc}",
    ]
    for fragment in forbidden_fragments:
        assert fragment not in source

    assert "ApiRequestError" in source
    assert "_safe_api_error_message(response)" in source


def test_frontend_does_not_hide_streamlit_header_sidebar_toggle() -> None:
    source = APP_PATH.read_text(encoding="utf-8")

    assert "header {" not in source
    assert "header," not in source


def test_stytch_configured_shows_landing_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CLUTCH_DISABLE_STREAMLIT_LOGIN", raising=False)
    app = AppTest.from_file(str(APP_PATH))
    app.secrets["stytch"] = {
        "project_id": "project-test-id",
        "secret": "secret-test-value",  # pragma: allowlist secret
        "environment": "test",
        "redirect_url": "http://localhost:8501",
    }

    app.run()

    assert any("Email me a login link" in item.label for item in app.button)
    markdown_text = " ".join(item.value for item in app.markdown)
    assert "Review your code. Explain your decisions." in markdown_text
    assert "Evidence-based review" in markdown_text
    assert "Interview practice" in markdown_text
    assert "Example finding" in markdown_text
    assert "AI review pipeline" in markdown_text
    assert "GitHub reads go through one scoped, read-only MCP server" in markdown_text
    assert "Prompt-injection tests treat code and README text as untrusted" in markdown_text
    assert "Recruiters" not in markdown_text
    assert "recruiters" not in markdown_text
    assert "demo" not in markdown_text
    assert "pretending to be AI" not in markdown_text
    assert "CodeFinding[] -> InterviewQuestion[] -> FeedbackReport" not in markdown_text
    assert "Every model-facing boundary is typed" not in markdown_text
    assert "0 raw" not in markdown_text


def test_streamlit_secrets_example_keeps_api_settings_at_root() -> None:
    with SECRETS_EXAMPLE_PATH.open("rb") as secrets_file:
        secrets = tomllib.load(secrets_file)

    assert secrets["CLUTCH_API_BASE_URL"] == "http://127.0.0.1:8000"
    assert secrets["CLUTCH_API_KEY"]
    assert secrets["stytch"]["redirect_url"] == "http://localhost:8501"
    assert secrets["stytch"]["environment"] == "test"
    assert "CLUTCH_API_BASE_URL" not in secrets["stytch"]
    assert "CLUTCH_API_KEY" not in secrets["stytch"]


def test_frontend_does_not_eagerly_import_progress_chart_dependency() -> None:
    tree = ast.parse(APP_PATH.read_text(encoding="utf-8"))
    top_level_imports = [
        node
        for node in tree.body
        if isinstance(node, ast.Import | ast.ImportFrom)
    ]

    imported_modules = {
        alias.name.split(".", maxsplit=1)[0]
        for node in top_level_imports
        for alias in node.names
    }

    assert "pandas" not in imported_modules
