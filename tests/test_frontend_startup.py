"""Startup must render without waiting for external services."""

from pathlib import Path
from unittest.mock import Mock

import pytest
import requests
from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).parents[1] / "frontend" / "app.py"


def _landing(monkeypatch: pytest.MonkeyPatch) -> AppTest:
    monkeypatch.delenv("CLUTCH_DISABLE_STREAMLIT_LOGIN", raising=False)
    app = AppTest.from_file(str(APP_PATH))
    app.secrets["stytch"] = {
        "project_id": "project-test-id",
        "secret": "secret-test-value",  # pragma: allowlist secret
        "environment": "test",
        "redirect_url": "http://localhost:8501",
    }
    return app


def test_landing_and_invalid_email_never_wait_for_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    network = Mock(side_effect=AssertionError("Unexpected startup network call"))
    monkeypatch.setattr(requests.sessions.Session, "request", network)
    app = _landing(monkeypatch).run()
    assert not app.exception
    assert app.text_input[0].label == "Email"
    app.text_input[0].set_value("invalid-email")
    app.button[0].click().run()
    assert not app.exception
    assert app.text_input[0].value == "invalid-email"
    assert any("valid email" in message.value for message in app.warning)
    network.assert_not_called()


def test_login_failure_preserves_email_and_can_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = Mock()
    response.json.return_value = {}
    send = Mock(side_effect=[requests.Timeout(), response])
    monkeypatch.setattr(requests, "post", send)
    app = _landing(monkeypatch).run()
    app.text_input[0].set_value("candidate@example.com")
    app.button[0].click().run()
    assert not app.exception
    assert app.text_input[0].value == "candidate@example.com"
    assert any("could not be sent" in message.value for message in app.error)
    app.button[0].click().run()
    assert not app.exception
    assert any("Check your inbox" in message.value for message in app.success)
    assert not app.error
    assert send.call_count == 2


def test_review_workbench_is_available_without_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLUTCH_DISABLE_STREAMLIT_LOGIN", "true")
    network = Mock(side_effect=AssertionError("Unexpected startup network call"))
    monkeypatch.setattr(requests.sessions.Session, "request", network)
    app = AppTest.from_file(str(APP_PATH)).run()
    assert not app.exception
    assert app.text_area[0].label == "Python code"
    assert any("Copy this example" in item.value for item in app.caption)
    assert any("def get_user" in item.value for item in app.code)
    network.assert_not_called()
