from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).parents[1] / "frontend" / "app.py"


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
                "origin": (
                    "ai_generated" if mode == "model" else "template_generated"
                ),
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
        "Included 2 files · skipped 4 · truncated: yes · "
        "full-codebase analysis: no"
    ) in caption_text
    assert "Google Engineering Practices — #good-code-reviews" in markdown_text


def test_review_ui_labels_successful_model_output() -> None:
    app = AppTest.from_file(str(APP_PATH)).run()
    app.session_state["review_result"] = _review_result(mode="model")
    app.run()

    assert any(
        "AI-generated review synthesis completed" in item.value
        for item in app.success
    )
    caption_text = " ".join(item.value for item in app.caption)
    assert "AI-generated review finding" in caption_text
    assert "AI-generated follow-up question" in caption_text
