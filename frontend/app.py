"""Streamlit workbench for review, interview practice, and progress."""

from __future__ import annotations

import os
from hashlib import sha256
from typing import Any, Literal, cast
from urllib.parse import unquote, urlencode, urlparse
from uuid import uuid4

import requests
import streamlit as st

PageName = Literal["Review", "Interview", "Progress"]
FINDINGS_PER_PAGE = 5

_STAGE_LABELS = {
    "retrieval": "Review retrieval",
    "review_synthesis": "Review synthesis",
    "question_generation": "Question generation",
    "interview_retrieval": "Interview retrieval",
    "interview_assessment": "Interview assessment",
    "final_aggregation": "Final report aggregation",
}
_FAILURE_LABELS = {
    "model_not_configured": "AI review is not available right now",
    "budget_rejected": "AI review is temporarily paused",
    "provider_error": "AI review did not complete",
    "schema_validation_failed": "AI review returned an unusable result",
    "grounding_validation_failed": "AI review returned an unsupported result",
    "retrieval_failed": "supporting references could not be loaded",
    "fallback_failed": "the backup review path did not complete",
    "persistence_failed": "this result could not be saved",
    "unknown": "this step did not complete",
}


class ApiRequestError(requests.RequestException):
    """Safe API error text that can be shown in the Streamlit UI."""

    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


def _setting(name: str, default: str = "") -> str:
    env_value = os.getenv(name, "").strip()
    if env_value:
        return env_value
    try:
        secret_value = st.secrets.get(name, default)
    except Exception:
        secret_value = default
    return str(secret_value).strip()


def _auth_configured() -> bool:
    if os.getenv("CLUTCH_DISABLE_STREAMLIT_LOGIN", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return False
    return _stytch_configured()


def _stytch_setting(name: str, default: str = "") -> str:
    env_name = f"STYTCH_{name.upper()}"
    env_value = os.getenv(env_name, "").strip()
    if env_value:
        return env_value
    try:
        config = st.secrets.get("stytch", {})
        value = config.get(name, default)
    except Exception:
        value = default
    return str(value).strip()


def _stytch_configured() -> bool:
    return bool(_stytch_setting("project_id") and _stytch_setting("secret"))


def _stytch_base_url() -> str:
    environment = _stytch_setting("environment", "test").lower()
    if environment in {"live", "production", "prod"}:
        return "https://api.stytch.com/v1"
    return "https://test.stytch.com/v1"


def _stytch_redirect_url() -> str:
    configured = _stytch_setting("redirect_url")
    if configured:
        return configured
    try:
        query_params = dict(st.query_params)
    except Exception:
        query_params = {}
    if "token" in query_params:
        query_params.pop("token", None)
    if "stytch_token_type" in query_params:
        query_params.pop("stytch_token_type", None)
    query_string = urlencode(query_params, doseq=True)
    suffix = f"?{query_string}" if query_string else ""
    return f"http://localhost:8501/{suffix}"


def _stytch_post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    project_id = _stytch_setting("project_id")
    secret = _stytch_setting("secret")
    response = requests.post(
        f"{_stytch_base_url()}{path}",
        auth=(project_id, secret),
        json=payload,
        timeout=20,
    )
    response.raise_for_status()
    result: dict[str, Any] = response.json()
    return result


def _send_stytch_magic_link(email: str) -> None:
    redirect_url = _stytch_redirect_url()
    _stytch_post(
        "/magic_links/email/login_or_create",
        {
            "email": email,
            "login_magic_link_url": redirect_url,
            "signup_magic_link_url": redirect_url,
        },
    )


def _authenticate_stytch_magic_link(token: str) -> str:
    result = _stytch_post(
        "/magic_links/authenticate",
        {"token": token, "session_duration_minutes": 60 * 24 * 7},
    )
    user = result.get("user", {})
    emails = user.get("emails") if isinstance(user, dict) else None
    email = ""
    if isinstance(emails, list) and emails:
        first_email = emails[0]
        if isinstance(first_email, dict):
            email = str(first_email.get("email") or "")
    st.session_state.stytch_session_jwt = str(result["session_jwt"])
    st.session_state.stytch_user_id = str(user.get("user_id") or email or token)
    st.session_state.stytch_user_email = email
    return st.session_state.stytch_user_id


def _handle_stytch_redirect() -> None:
    if not _stytch_configured():
        return
    try:
        token = st.query_params.get("token")
    except Exception:
        token = None
    if not token:
        return
    try:
        _authenticate_stytch_magic_link(str(token))
    except requests.RequestException:
        st.session_state.stytch_auth_error = True
    except (KeyError, TypeError, ValueError):
        st.session_state.stytch_auth_error = True
    else:
        st.session_state.pop("stytch_auth_error", None)
        st.query_params.clear()
        st.rerun()


def _logout_stytch() -> None:
    for key in (
        "stytch_session_jwt",
        "stytch_user_id",
        "stytch_user_email",
        "stytch_auth_error",
        "stytch_link_sent_to",
    ):
        st.session_state.pop(key, None)


def _is_authenticated() -> bool:
    return bool(_auth_configured() and st.session_state.get("stytch_session_jwt"))


def _authenticated_profile_id() -> str | None:
    if not _auth_configured():
        return None
    identity = str(st.session_state.get("stytch_user_id") or "").strip()
    if not identity:
        return None
    digest = sha256(identity.encode("utf-8")).hexdigest()
    return f"user_{digest[:40]}"


def _render_landing_gate() -> None:
    st.markdown(
        """
        <style>

        [data-testid="stToolbar"],
        [data-testid="stDecoration"],
        #MainMenu {
            visibility: hidden;
            height: 0;
        }
        html, .stApp {
            font-family: "Avenir Next", "Segoe UI", sans-serif;
            background: var(--clutch-bg);
        }
        [data-testid="stMainBlockContainer"] {
            padding-top: 2rem;
            padding-bottom: 3rem;
        }
        .st-key-landing_hero {
            padding: clamp(1.25rem, 3vw, 2.4rem);
            border: 1px solid var(--clutch-border);
            border-radius: 0.5rem;
            background: var(--clutch-surface);
        }
        .st-key-landing_hero [data-testid="stHorizontalBlock"] {
            gap: clamp(1.75rem, 4vw, 3.5rem);
        }
        .stApp .clutch-wordmark {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 1.4rem;
        }
        .stApp .clutch-wordmark-mark {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 1.6rem;
            height: 1.6rem;
            border-radius: 0.35rem;
            background: var(--clutch-accent);
            color: var(--clutch-surface);
            font-weight: 700;
            font-size: 0.85rem;
        }
        .stApp .clutch-wordmark-word {
            font-size: 1.05rem;
            font-weight: 700;
            color: var(--clutch-text);
        }
        .stApp .clutch-hero-title {
            max-width: 22ch;
            margin: 0 0 1rem;
            color: var(--clutch-text);
            font-size: clamp(2rem, 3.2vw, 3rem);
            padding: 0;
            line-height: 1.12;
            letter-spacing: -0.01em;
            font-weight: 700;
        }
        .stApp .clutch-hero-title > a {
            display: none;
        }
        .stApp .clutch-hero-copy {
            max-width: 34rem;
            margin: 0;
            color: var(--clutch-text-muted);
            font-size: 1.05rem;
            line-height: 1.6;
        }
        .stApp .clutch-trust-line {
            max-width: 34rem;
            margin: 1.1rem 0 0;
            color: var(--clutch-text-muted);
            font-size: 0.88rem;
            line-height: 1.5;
        }
        .stApp .clutch-signin-lead {
            margin: 1.5rem 0 0.6rem;
            padding-top: 1.5rem;
            border-top: 1px solid var(--clutch-border);
            color: var(--clutch-text);
            font-size: 0.95rem;
            font-weight: 600;
        }
        .st-key-landing_hero [data-testid="stForm"] {
            margin-top: 0.25rem;
            padding: 1.1rem 1.15rem;
            background: var(--clutch-surface-2);
            border-color: var(--clutch-border);
            border-radius: 0.5rem;
        }
        .st-key-landing_hero [data-testid="stForm"] label p {
            font-weight: 600;
            color: var(--clutch-text);
        }
        .st-key-landing_hero [data-testid="stButton"] {
            margin-top: 0.6rem;
        }
        .st-key-landing_hero button[kind="primary"] {
            min-height: 2.75rem;
            padding-inline: 1.1rem;
            font-weight: 600;
        }
        .stApp .clutch-cta-copy {
            max-width: 34rem;
            color: var(--clutch-text-muted);
            font-size: 0.86rem;
            line-height: 1.5;
            margin: 0.6rem 0 0;
        }
        .stApp .clutch-preview-label {
            margin: 0 0 0.6rem;
            color: var(--clutch-text-muted);
            font-size: 0.82rem;
            font-weight: 600;
            letter-spacing: 0.02em;
        }
        .stApp .clutch-code-card {
            border: 1px solid var(--clutch-border);
            border-radius: 0.5rem;
            background: var(--clutch-surface-2);
            overflow: hidden;
        }
        .stApp .clutch-code-filename {
            padding: 0.5rem 0.85rem;
            border-bottom: 1px solid var(--clutch-border);
            color: var(--clutch-text-muted);
            font-family: "SFMono-Regular", Consolas, monospace;
            font-size: 0.8rem;
        }
        .stApp .clutch-code-body {
            display: block;
            overflow-wrap: anywhere;
            white-space: pre-wrap;
            margin: 0;
            padding: 0.9rem 0.85rem;
            color: var(--clutch-text);
            font-family: "SFMono-Regular", Consolas, monospace;
            font-size: 0.85rem;
            line-height: 1.55;
        }
        .stApp .clutch-finding {
            border-top: 1px solid var(--clutch-border);
            padding: 0.95rem 0.85rem;
        }
        .stApp .clutch-finding-tag {
            display: inline-block;
            margin-bottom: 0.5rem;
            padding: 0.15rem 0.5rem;
            border-radius: 0.3rem;
            background: var(--clutch-accent-muted);
            color: var(--clutch-accent-strong);
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.02em;
            text-transform: uppercase;
        }
        .stApp .clutch-finding h3 {
            margin: 0 0 0.4rem;
            color: var(--clutch-text);
            font-size: 0.98rem;
        }
        .stApp .clutch-finding p {
            margin: 0;
            color: var(--clutch-text-muted);
            font-size: 0.9rem;
            line-height: 1.55;
        }
        .stApp .clutch-followup {
            border-top: 1px solid var(--clutch-border);
            padding: 0.95rem 0.85rem;
        }
        .stApp .clutch-followup span {
            display: block;
            margin-bottom: 0.35rem;
            color: var(--clutch-text-muted);
            font-size: 0.78rem;
            font-weight: 600;
        }
        .stApp .clutch-followup p {
            margin: 0;
            color: var(--clutch-text);
            font-size: 0.92rem;
            line-height: 1.5;
        }
        .stApp .clutch-features {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 1.75rem;
            margin-top: 2rem;
            padding-top: 1.75rem;
            border-top: 1px solid var(--clutch-border);
        }
        .stApp .clutch-feature h3 {
            margin: 0 0 0.4rem;
            color: var(--clutch-text);
            font-size: 1rem;
        }
        .stApp .clutch-feature p {
            margin: 0;
            color: var(--clutch-text-muted);
            font-size: 0.92rem;
            line-height: 1.55;
        }
        .stApp .clutch-sections {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 1rem;
            margin-top: 1.75rem;
        }
        .stApp .clutch-panel {
            border: 1px solid var(--clutch-border);
            border-radius: 0.5rem;
            background: var(--clutch-surface);
            padding: 1.1rem;
        }
        .stApp .clutch-panel h2 {
            margin: 0 0 0.65rem;
            color: var(--clutch-text);
            font-size: 1rem;
            font-weight: 600;
        }
        .stApp .clutch-panel p,
        .stApp .clutch-panel li {
            color: var(--clutch-text-muted);
            line-height: 1.6;
            font-size: 0.92rem;
        }
        .stApp .clutch-panel ul {
            padding-left: 1.1rem;
            margin-bottom: 0;
        }
        .stApp .clutch-masthead, .clutch-footer {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 1rem;
            flex-wrap: wrap;
            color: var(--clutch-text-muted);
            font-size: 0.8rem;
            padding: 0.25rem 0 1.1rem;
        }
        .stApp .clutch-masthead > span { letter-spacing: 0.08em; font-size: 0.7rem; }
        .stApp .clutch-footer { margin-top: 1.5rem; }
        .stApp .clutch-code-filename { display: flex; justify-content: space-between; gap: 1rem; }
        .stApp .clutch-code-body { padding-inline: 0; }
        .stApp .clutch-code-body code { background: none; padding: 0; font-size: inherit; }
        .stApp .clutch-code-line { display: block; padding-inline: 0.85rem; }
        .stApp .clutch-line-number { color: var(--clutch-text-muted); margin-right: 1rem; user-select: none; }
        .stApp .clutch-code-highlight { background: var(--clutch-accent-muted); border-left: 3px solid var(--clutch-accent); }
        .stApp .clutch-code-line b { color: var(--clutch-accent-strong); }
        .stApp .clutch-revision { border-top: 1px solid var(--clutch-border); }
        .stApp .clutch-revision summary, .clutch-engineering summary {
            padding: 1rem;
            cursor: pointer;
            font-size: 0.9rem;
            font-weight: 600;
            color: var(--clutch-accent-strong);
        }
        .stApp .clutch-revision summary:hover, .clutch-engineering summary:hover {
            background: var(--clutch-accent-muted);
        }
        .stApp .clutch-revision summary:active, .clutch-engineering summary:active {
            background: var(--clutch-border);
        }
        .stApp .clutch-revision .clutch-code-body { padding: 0.5rem 1rem; }
        .stApp .clutch-revision p { padding: 0 1rem 1rem; margin: 0; font-size: 0.85rem; color: var(--clutch-text-muted); }
        .stApp .clutch-engineering { border-block: 1px solid var(--clutch-border); margin-top: 2rem; }
        .stApp .clutch-engineering summary { padding-inline: 0.5rem; }
        .stApp .clutch-engineering summary span { font-weight: 400; color: var(--clutch-text-muted); margin-left: 0.75rem; }
        .stApp .clutch-engineering .clutch-sections { margin: 0.5rem 0 1rem; }
        @media (max-width: 820px) {
            .st-key-landing_hero [data-testid="stHorizontalBlock"] {
                flex-wrap: wrap;
            }
            .st-key-landing_hero [data-testid="stColumn"] {
                flex: 1 1 100%;
                width: 100%;
            }
            .stApp .clutch-sections,
            .stApp .clutch-features {
                grid-template-columns: 1fr;
            }
            .stApp .clutch-hero-title {
                max-width: none;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    
    with st.container(key="landing_hero"):
        copy, preview = st.columns([1.05, 0.95], gap="large", vertical_alignment="top")
        with copy:
            st.markdown(
                """
                <div class="clutch-wordmark">
                    <span class="clutch-wordmark-mark">C</span>
                    <span class="clutch-wordmark-word">Clutch</span>
                </div>
                <h1 class="clutch-hero-title">
                    Review your code. Explain your decisions.
                </h1>
                <p class="clutch-hero-copy">
                    Paste a Python file or connect a GitHub pull request.
                    Clutch shows what needs attention, why it matters, and
                    which questions an interviewer might ask next.
                </p>
                <p class="clutch-trust-line">
                    Designed for developers preparing for backend and AI
                    engineering interviews.
                </p>
                <p class="clutch-signin-lead">
                    Sign in to start a private review
                </p>
                """,
                unsafe_allow_html=True,
            )
            with st.form("stytch-login-form", clear_on_submit=False):
                email = st.text_input(
                    "Email",
                    placeholder="you@example.com",
                    autocomplete="email",
                )
                submitted = st.form_submit_button(
                    "Email me a login link",
                    type="primary",
                    width="stretch",
                )
            if submitted:
                if "@" not in email:
                    st.warning("Enter a valid email address.")
                else:
                    try:
                        with st.spinner("Sending your sign-in link…"):
                            _send_stytch_magic_link(email.strip())
                    except requests.RequestException:
                        st.error(
                            "The login link could not be sent. Check the email "
                            "address and try again in a moment."
                        )
                    else:
                        st.session_state.stytch_link_sent_to = email.strip()
                        st.success("Check your inbox for the Clutch login link.")
            if st.session_state.get("stytch_auth_error"):
                st.error(
                    "The login link could not be verified. Request a fresh link "
                    "and try again."
                )
            if st.session_state.get("stytch_link_sent_to"):
                st.caption(
                    "Sent to "
                    f"{st.session_state.stytch_link_sent_to}. "
                    "Click the link in the same browser to finish signing in."
                )
            st.markdown(
                """
                <p class="clutch-cta-copy">
                    We'll email a one-time sign-in link — no password needed.
                    Review code, practise your reasoning, and revisit your progress.
                </p>
                """,
                unsafe_allow_html=True,
            )
        with preview:
            st.markdown(
                """
                <p class="clutch-preview-label">Example finding</p>
                <div class="clutch-code-card" aria-label="Example code review">
                    <div class="clutch-code-filename"><span>review.py</span><span>Python · 3 lines</span></div>
                    <div class="clutch-code-body" role="code"><span class="clutch-code-line"><span class="clutch-line-number" aria-hidden="true">1</span><b>def</b> get_user(user_id):</span><span class="clutch-code-line"><span class="clutch-line-number" aria-hidden="true">2</span>    users = load_users()</span><span class="clutch-code-line clutch-code-highlight"><span class="clutch-line-number" aria-hidden="true">3</span>    <b>return</b> [u for u in users if u["id"] == user_id][0]</span></div>
                    <div class="clutch-finding">
                        <span class="clutch-finding-tag">Correctness · Line 3</span>
                        <h3>Possible IndexError</h3>
                        <p>
                            This raises <code>IndexError</code> if no user
                            matches the id, instead of a clear, catchable
                            error. Return <code>None</code> or raise a
                            domain-specific <code>NotFoundError</code>.
                        </p>
                    </div>
                    <div class="clutch-followup">
                        <span>Interview follow-up</span>
                        <p>Why did you choose this error-handling strategy?</p>
                    </div>
                    <details class="clutch-revision">
                        <summary>See a suggested revision</summary>
                        <pre class="clutch-code-body"><code>def get_user(user_id):&#10;    return next(&#10;        (u for u in load_users()&#10;         if u["id"] == user_id),&#10;        None,&#10;    )</code></pre>
                        <p>An explicit missing-user result. The caller must handle
                        <code>None</code>; a domain exception is another valid choice.</p>
                    </details>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown(
        """
        <div class="clutch-features" aria-label="Product highlights">
            <div class="clutch-feature">
                <h3>Evidence-based review</h3>
                <p>Every finding includes the relevant code, impact, and reasoning.</p>
            </div>
            <div class="clutch-feature">
                <h3>Interview practice</h3>
                <p>Turn review findings into realistic technical follow-up questions.</p>
            </div>
            <div class="clutch-feature">
                <h3>Private progress</h3>
                <p>Track recurring issues without exposing your practice sessions.</p>
            </div>
        </div>
        <details class="clutch-engineering">
        <summary>Under the hood <span>Architecture, guardrails &amp; evaluation</span></summary>
        <div class="clutch-sections">
            <section class="clutch-panel">
                <h2>AI review pipeline</h2>
                <ul>
                    <li>Tree-sitter extracts Python structure and line ranges.</li>
                    <li>Hybrid-ready retrieval grounds findings in a rubric corpus.</li>
                    <li>Strict schemas validate findings, questions, and reports.</li>
                </ul>
            </section>
            <section class="clutch-panel">
                <h2>Agent + tool boundary</h2>
                <ul>
                    <li>FastAPI exposes the system beyond the Streamlit client.</li>
                    <li>LangGraph coordinates review, retrieval, and interview turns.</li>
                    <li>GitHub reads go through one scoped, read-only MCP server.</li>
                </ul>
            </section>
            <section class="clutch-panel">
                <h2>Production signals</h2>
                <ul>
                    <li>Prompt-injection tests treat code and README text as untrusted.</li>
                    <li>Langfuse traces are privacy-reduced and redact raw inputs.</li>
                    <li>Versioned evals gate regressions; Redis caches retrieval results.</li>
                </ul>
            </section>
        </div>
        </details>
        <div class="clutch-footer">Built for thoughtful practice.
        """,
        unsafe_allow_html=True,
    )


def _initialize_state(profile_id: str | None = None) -> None:
    defaults: dict[str, Any] = {
        "profile_id": profile_id or str(uuid4()),
        "workflow_nav": "Review",
        "review_input_mode": "Paste code",
        "review_result": None,
        "review_findings_page": 1,
        "github_ingestion": None,
        "review_role_context": "backend intern",
        "interview_result": None,
        "feedback_report": None,
        "progress_result": None,
        "review_pending": None,
        "interview_pending": None,
        "review_error": None,
        "interview_error": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    if profile_id is not None and st.session_state.profile_id != profile_id:
        st.session_state.profile_id = profile_id
        st.session_state.review_result = None
        st.session_state.review_findings_page = 1
        st.session_state.github_ingestion = None
        st.session_state.interview_result = None
        st.session_state.feedback_report = None
        st.session_state.progress_result = None
    requested_page = st.session_state.pop("requested_page", None)
    if requested_page is not None:
        st.session_state.workflow_nav = requested_page


def _queue_page(page: PageName) -> None:
    st.session_state.requested_page = page


def _set_findings_page(page: int) -> None:
    st.session_state.review_findings_page = page


def _api_request(
    method: Literal["GET", "POST"],
    path: str,
    *,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    api_base_url = _setting("CLUTCH_API_BASE_URL", "http://localhost:8000")
    api_key = _setting("CLUTCH_API_KEY")
    response = requests.request(
        method,
        f"{api_base_url}{path}",
        json=payload,
        headers={"X-Clutch-API-Key": api_key} if api_key else None,
        timeout=90,
    )
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise ApiRequestError(_safe_api_error_message(response)) from exc
    result: dict[str, Any] = response.json()
    return result


def _safe_api_error_message(response: requests.Response) -> str:
    default = "The request could not complete. Your input is still here; try again."
    try:
        payload = response.json()
    except ValueError:
        return default
    detail = payload.get("detail") if isinstance(payload, dict) else None
    if not isinstance(detail, str) or not detail.strip():
        return default
    return detail.strip()


def _github_url_validation_message(source_url: str) -> str | None:
    value = source_url.strip()
    if not value:
        return "Enter a GitHub repository or pull-request URL."

    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.netloc != "github.com":
        return "Use an HTTPS github.com link."

    segments = [unquote(segment) for segment in parsed.path.strip("/").split("/")]
    if any(not segment or segment in {".", ".."} for segment in segments):
        return "Use a GitHub repository link like https://github.com/owner/repository."

    is_repository = len(segments) == 2
    is_pull_request = (
        len(segments) == 4 and segments[2] == "pull" and segments[3].isdigit()
    )
    if is_repository or is_pull_request:
        return None

    return (
        "Use a repository or pull request link like "
        "https://github.com/owner/repository or "
        "https://github.com/owner/repository/pull/123."
    )


_PAGE_ICONS = {
    "Review": ":material/search:",
    "Interview": ":material/forum:",
    "Progress": ":material/trending_up:",
}


def _render_sidebar_nav() -> PageName:
    review = st.session_state.get("review_result")
    interview = st.session_state.get("interview_result")
    # A review or interview submission runs its API call synchronously on the
    # same script run that renders this sidebar. If the user switches tabs
    # while that call is in flight, Streamlit abandons the running script for
    # the new one, so the pending result never gets saved and the page comes
    # back blank. Locking navigation until the pending call finishes avoids
    # that lost-work state.
    nav_locked = bool(
        st.session_state.get("review_pending")
        or st.session_state.get("interview_pending")
    )
    with st.sidebar:
        st.markdown(
            """
            <div class="clutch-brand">
                <span class="clutch-brand-mark">C</span>
                <span class="clutch-brand-word">Clutch</span>
            </div>
            <p class="clutch-sidebar-tagline">
                Review code, then practice explaining it.
            </p>
            """,
            unsafe_allow_html=True,
        )
        selected = st.radio(
            "Workflow",
            options=["Review", "Interview", "Progress"],
            captions=[
                "Inspect the evidence",
                "Practise your reasoning",
                "See what improves",
            ],
            key="workflow_nav",
            label_visibility="collapsed",
            disabled=nav_locked,
        )
        if nav_locked:
            st.caption(
                ":material/hourglass_top: Processing — navigation is locked "
                "until this finishes."
            )
        st.divider()
        with st.container(horizontal=True):
            st.metric(
                "Confidence",
                f"{review['confidence']:.0%}" if review else "—",
                icon=":material/verified:",
            )
            st.metric(
                "Findings",
                len(review["findings"]) if review else "—",
                icon=":material/flag:",
            )
        st.metric(
            "Interview turn",
            interview["turn_number"]
            if interview and not interview["completed"]
            else ("Done" if interview and interview["completed"] else "—"),
            icon=":material/mic:",
        )
        st.divider()
        if _is_authenticated():
            name = st.session_state.get("stytch_user_email") or "Signed in"
            st.caption(f":material/account_circle: Signed in as {name}")
            if st.button(
                "Log out",
                icon=":material/logout:",
                width="stretch",
                disabled=nav_locked,
            ):
                _logout_stytch()
                st.rerun()
        st.caption(f"Practice profile `{st.session_state.profile_id[:8]}`")
    return cast(PageName, selected or "Review")


def _origin_label(origin: str | None, *, item: str) -> str:
    if origin == "ai_generated":
        return {
            "finding": "AI-generated review finding",
            "question": "AI-generated follow-up question",
            "assessment": "AI-generated interview assessment",
        }.get(item, "AI-generated output")
    if origin == "template_generated":
        return "Template-generated follow-up question"
    if origin == "retrieved_citation":
        return "Retrieved citation"
    return {
        "finding": "Deterministic static finding",
        "assessment": "Rule-based interview assessment",
        "report": "Deterministic report aggregation",
    }.get(item, "Deterministic output")


def _citation_markdown(citation: dict[str, Any]) -> str:
    title = str(citation.get("title") or citation.get("source_id") or "Source")
    title = title.replace("[", "\\[").replace("]", "\\]")
    url = str(citation.get("url") or "")
    fragment = unquote(urlparse(url).fragment)
    locator = f"#{fragment}" if fragment else "source page"
    label = f"{title} — {locator}"
    return f"[{label}]({url})" if url else label


def _render_citations(citations: list[dict[str, Any]]) -> None:
    if not citations:
        return
    st.caption(_origin_label("retrieved_citation", item="citation"))
    rendered: set[tuple[str, str]] = set()
    for citation in citations:
        identity = (
            str(citation.get("source_id") or ""),
            str(citation.get("url") or ""),
        )
        if identity in rendered:
            continue
        rendered.add(identity)
        st.markdown(f"- {_citation_markdown(citation)}")


def _render_stage_provenance(provenance: list[dict[str, Any]]) -> None:
    if not provenance:
        return
    with st.expander(":material/route: How this result was produced"):
        for stage in provenance:
            stage_name = str(stage.get("stage") or "unknown")
            label = _STAGE_LABELS.get(stage_name, stage_name)
            status = str(stage.get("status", "unknown"))
            state: Literal["running", "complete", "error"] = (
                "complete"
                if status == "completed"
                else "error"
                if status in {"failed", "fallback"}
                else "running"
            )
            with st.status(label, state=state, expanded=False):
                with st.container(horizontal=True):
                    st.badge(
                        status.replace("_", " "),
                        color="green" if state == "complete" else "orange",
                    )
                    if stage.get("model_name"):
                        st.badge(str(stage["model_name"]), color="violet")
                    if stage.get("prompt_version"):
                        st.badge(str(stage["prompt_version"]), color="gray")
                input_tokens = stage.get("input_tokens")
                output_tokens = stage.get("output_tokens")
                metric_cols = st.container(horizontal=True)
                with metric_cols:
                    if isinstance(input_tokens, int) or isinstance(output_tokens, int):
                        st.metric(
                            "Tokens",
                            f"{(input_tokens or 0) + (output_tokens or 0):,}",
                        )
                    st.metric(
                        "Latency", f"{float(stage.get('latency_ms') or 0):,.0f} ms"
                    )
                    estimated_cost = float(stage.get("estimated_cost_usd") or 0)
                    if estimated_cost > 0:
                        st.metric("Est. cost", f"${estimated_cost:.6f}")
                failure_category = stage.get("failure_category")
                if failure_category:
                    st.caption(
                        "⚠️ "
                        + _FAILURE_LABELS.get(failure_category, str(failure_category))
                    )


def _render_review_provenance(review: dict[str, Any]) -> None:
    mode = review.get("mode")
    provenance = review.get("provenance", [])
    synthesis_reason = next(
        (
            _FAILURE_LABELS.get(
                stage.get("failure_category"),
                "the model path did not complete",
            )
            for stage in provenance
            if stage.get("stage") == "review_synthesis"
            and stage.get("failure_category")
        ),
        "the model path did not complete",
    )
    if mode == "model":
        st.success(
            "AI-generated review synthesis completed.", icon=":material/auto_awesome:"
        )
    elif mode == "static_fallback":
        st.warning(
            f"No successful review model call occurred because {synthesis_reason}. "
            "These findings came from deterministic static analysis, so they are "
            "not AI-generated.",
            icon=":material/rule:",
        )
    else:
        st.warning(
            f"No successful review model call occurred because {synthesis_reason}, "
            "and no static issue matched. This result used retrieval-only/static "
            "logic, not AI synthesis.",
            icon=":material/rule:",
        )
    for stage in provenance:
        if (
            stage.get("status") == "fallback"
            and stage.get("stage") != "review_synthesis"
        ):
            label = _STAGE_LABELS.get(stage.get("stage"), "A later stage")
            reason = _FAILURE_LABELS.get(
                stage.get("failure_category"),
                "the model path did not complete",
            )
            st.warning(f"{label} used its fallback because {reason}.")
    _render_stage_provenance(provenance)


BadgeColor = Literal["red", "orange", "yellow", "blue", "green", "violet", "gray"]

_SEVERITY_COLOR: dict[str, BadgeColor] = {
    "critical": "red",
    "high": "orange",
    "medium": "yellow",
    "low": "blue",
}
_SEVERITY_ICON = {
    "critical": ":material/report:",
    "high": ":material/warning:",
    "medium": ":material/info:",
    "low": ":material/circle:",
}
_DIFFICULTY_COLOR: dict[str, BadgeColor] = {
    "easy": "green",
    "medium": "yellow",
    "hard": "red",
}


def _render_finding(finding: dict[str, Any]) -> None:
    severity = str(finding["severity"]).lower()
    color = _SEVERITY_COLOR.get(severity, "gray")
    with st.container(border=True):
        with st.container(horizontal=True, vertical_alignment="center"):
            st.badge(
                severity.upper(),
                icon=_SEVERITY_ICON.get(severity, ":material/circle:"),
                color=color,
            )
            st.badge(finding["category"].replace("_", " "), color="gray")
            st.caption(_origin_label(finding.get("origin"), item="finding"))
        st.markdown(f"#### {finding['message']}")
        if finding.get("line_start"):
            line_end = finding.get("line_end") or finding["line_start"]
            st.caption(f":material/code: Lines {finding['line_start']}-{line_end}")
        st.code(finding["evidence"], language="python")
        st.write(finding["explanation"])
        st.info(finding["suggestion"], icon=":material/lightbulb:")
        _render_citations(finding.get("citations", []))


def _render_findings(findings: list[dict[str, Any]]) -> None:
    total = len(findings)
    total_pages = max(1, (total + FINDINGS_PER_PAGE - 1) // FINDINGS_PER_PAGE)
    current_page = int(st.session_state.get("review_findings_page", 1))
    current_page = min(max(current_page, 1), total_pages)
    st.session_state.review_findings_page = current_page

    start_index = (current_page - 1) * FINDINGS_PER_PAGE
    end_index = min(start_index + FINDINGS_PER_PAGE, total)
    if total_pages > 1:
        with st.container(horizontal=True, vertical_alignment="center"):
            st.caption(
                f"Showing findings {start_index + 1}-{end_index} of {total} "
                f"· page {current_page} of {total_pages}"
            )
            st.button(
                "Previous",
                icon=":material/chevron_left:",
                disabled=current_page <= 1,
                on_click=_set_findings_page,
                args=(current_page - 1,),
            )
            st.button(
                "Next",
                icon=":material/chevron_right:",
                disabled=current_page >= total_pages,
                on_click=_set_findings_page,
                args=(current_page + 1,),
            )

    for finding in findings[start_index:end_index]:
        _render_finding(finding)

    if total_pages > 1:
        with st.container(horizontal=True, vertical_alignment="center"):
            st.caption(f"Page {current_page} of {total_pages}")
            st.button(
                "Previous page",
                icon=":material/chevron_left:",
                disabled=current_page <= 1,
                on_click=_set_findings_page,
                args=(current_page - 1,),
            )
            st.button(
                "Next page",
                icon=":material/chevron_right:",
                disabled=current_page >= total_pages,
                on_click=_set_findings_page,
                args=(current_page + 1,),
            )


def _render_review_page() -> None:
    review_pending = st.session_state.review_pending is not None
    st.subheader(f"{_PAGE_ICONS['Review']} 1 · Review the evidence", divider="gray")
    st.write(
        "Bring a Python snippet or a GitHub pull request. Get specific findings, "
        "supporting references, and questions to practise next."
    )
    input_mode = st.segmented_control(
        "Review source",
        options=["Paste code", "GitHub"],
        key="review_input_mode",
        selection_mode="single",
        disabled=review_pending,
    )
    code = ""
    source_url = ""
    ref = ""
    with st.form("review-form", clear_on_submit=False):
        role_context = st.text_input(
            "Target role",
            value="backend intern",
            help="Findings and questions are framed for this interview context.",
        )
        if input_mode == "GitHub":
            source_url = st.text_input(
                "GitHub repository or PR URL",
                placeholder="https://github.com/owner/repository",
                help=(
                    "HTTPS github.com URLs only. Public repositories need no token; "
                    "private access is handled server-side."
                ),
            )
            ref = st.text_input(
                "Git ref (optional)",
                placeholder="main",
                help="Used for repository links; PR links use the PR's patch.",
            )
        else:
            code = st.text_area(
                "Python code",
                height=360,
                placeholder="def calculate_total(items):\n    ...",
                help="Maximum 50,000 characters. Raw code is not stored by Clutch.",
            )
        submitted = st.form_submit_button(
            "Review GitHub source" if input_mode == "GitHub" else "Review code",
            type="primary",
            icon=":material/rocket_launch:",
            disabled=review_pending,
        )

    if submitted:
        if input_mode != "GitHub" and not code.strip():
            st.warning("Paste a Python snippet before starting the review.")
        elif input_mode == "GitHub" and (
            validation_message := _github_url_validation_message(source_url)
        ):
            st.warning(validation_message)
        else:
            # Stash the inputs and rerun immediately, rather than calling the
            # API inline here. That lets the next run render the sidebar as
            # locked *before* the blocking call starts, so a tab switch can't
            # abandon this run mid-flight (see _render_sidebar_nav).
            st.session_state.review_pending = {
                "input_mode": input_mode,
                "code": code,
                "source_url": source_url,
                "ref": ref,
                "role_context": role_context,
            }
            st.rerun()

    pending = st.session_state.review_pending
    if pending is not None:
        try:
            with st.spinner("Reviewing structure, evidence, and interview signals…"):
                if pending["input_mode"] == "GitHub":
                    github_result = _api_request(
                        "POST",
                        "/review/github",
                        payload={
                            "source_url": pending["source_url"],
                            "ref": pending["ref"].strip() or None,
                            "role_context": pending["role_context"],
                            "session_id": st.session_state.profile_id,
                        },
                    )
                    review = github_result["review"]
                    ingestion = github_result["ingestion"]
                else:
                    review = _api_request(
                        "POST",
                        "/review",
                        payload={
                            "code": pending["code"],
                            "language": "python",
                            "role_context": pending["role_context"],
                            "session_id": st.session_state.profile_id,
                        },
                    )
                    ingestion = None
        except ApiRequestError as exc:
            st.session_state.review_pending = None
            st.session_state.review_error = exc.user_message
            st.rerun()
        except requests.RequestException:
            # Clear the pending flag and rerun so the sidebar (rendered at
            # the top of this same run, before the call failed) redraws
            # unlocked. The error message can't be shown inline here since
            # rerun() abandons the rest of this run — stash it so the next
            # run can display it instead.
            st.session_state.review_pending = None
            st.session_state.review_error = (
                "The review could not complete. Your input is still here; "
                "try again in a moment."
            )
            st.rerun()
        else:
            st.session_state.review_result = review
            st.session_state.review_findings_page = 1
            st.session_state.github_ingestion = ingestion
            st.session_state.review_role_context = pending["role_context"].strip() or (
                "backend intern"
            )
            st.session_state.interview_result = None
            st.session_state.feedback_report = None
            st.session_state.progress_result = None
            st.session_state.review_pending = None
            st.rerun()

    review_error = st.session_state.pop("review_error", None)
    if review_error is not None:
        st.error(review_error)

    review = st.session_state.review_result
    if review is None:
        st.info(
            "Start with a function you recently wrote—especially one with error "
            "handling, state, or an unfinished tradeoff."
        )
        with st.expander("Need a snippet to try?", icon=":material/code:"):
            st.caption(
                "Copy this example into Python code above, then choose Review code. "
                "Consider what happens when a user cannot be found."
            )
            st.code(
                "def get_user(users, user_id):\n"
                '    return [u for u in users if u["id"] == user_id][0]\n',
                language="python",
            )
        return

    ingestion = st.session_state.github_ingestion
    if ingestion is not None:
        source_label = (
            f"PR #{ingestion['pull_number']}"
            if ingestion["source_type"] == "pull_request"
            else f"ref {ingestion['ref']}"
        )
        st.info(
            f"Reviewed a bounded Python selection from "
            f"{ingestion['owner']}/{ingestion['repository']} ({source_label}) through "
            "the read-only MCP boundary. Fetched content was treated as untrusted."
        )
        st.caption(
            f"Included {len(ingestion['files_included'])} files · "
            f"skipped {ingestion['skipped_file_count']} · "
            f"truncated: {'yes' if ingestion['truncated'] else 'no'} · "
            "full-codebase analysis: no"
        )
        with st.expander("Included files"):
            for path in ingestion["files_included"]:
                st.code(path, language=None)

    with st.container(horizontal=True):
        st.metric(
            "Confidence",
            f"{review['confidence']:.0%}",
            icon=":material/verified:",
        )
        st.metric("Findings", len(review["findings"]), icon=":material/flag:")
        st.metric(
            "Latency",
            f"{review['latency_ms']:.0f} ms",
            icon=":material/timer:",
        )
    st.caption(f"Request `{review['request_id']}`")
    _render_review_provenance(review)
    st.markdown("#### :material/flag: Findings")
    if review["findings"]:
        _render_findings(review["findings"])
    else:
        st.success(
            "No deterministic issue was found in this snippet. This is not proof "
            "of correctness; add broader context or tests for a deeper review."
        )

    questions = review.get("questions", [])
    if questions:
        st.markdown("#### :material/forum: Interview follow-ups")
        for question in questions:
            with st.container(border=True):
                with st.container(horizontal=True, vertical_alignment="center"):
                    st.badge(
                        question["difficulty"].upper(),
                        color=_DIFFICULTY_COLOR.get(
                            question["difficulty"].lower(), "gray"
                        ),
                    )
                    st.caption(_origin_label(question.get("origin"), item="question"))
                st.write(question["question"])
                st.caption(question["intent"])
                if question.get("finding_id"):
                    st.caption(f"Grounded in finding {question['finding_id']}")
                _render_citations(question.get("citations", []))
        st.button(
            "Practice these questions",
            type="primary",
            icon=":material/forum:",
            on_click=_queue_page,
            args=("Interview",),
        )


def _render_assessment(assessment: dict[str, Any]) -> None:
    with st.container(border=True):
        with st.container(horizontal=True, vertical_alignment="center"):
            st.metric(
                "Answer score",
                f"{assessment['score']}/5",
                icon=":material/star:",
            )
            st.caption(_origin_label(assessment.get("origin"), item="assessment"))
        st.progress(min(max(assessment["score"], 0), 5) / 5)
        st.write(assessment["feedback"])
        left, right = st.columns(2)
        with left:
            st.markdown(":material/thumb_up: **What worked**")
            if assessment["strengths"]:
                for strength in assessment["strengths"]:
                    st.write(f"• {strength}")
            else:
                st.caption("No strong signal yet—add more explicit reasoning.")
        with right:
            st.markdown(":material/target: **Strengthen next**")
            if assessment["gaps"]:
                for gap in assessment["gaps"]:
                    st.write(f"• {gap}")
            else:
                st.caption("No major gap detected in this answer.")
        _render_citations(assessment.get("citations", []))
    provenance = assessment.get("provenance")
    if provenance:
        _render_stage_provenance([provenance])


def _load_feedback(session_id: str) -> dict[str, Any] | None:
    try:
        with st.spinner("Assembling the final feedback report…"):
            return _api_request("GET", f"/interview/{session_id}/feedback")
    except requests.RequestException:
        st.error(
            "The final report could not be loaded. The interview is still complete; "
            "try again in a moment."
        )
        return None


def _render_feedback_report(report: dict[str, Any]) -> None:
    st.markdown("### :material/summarize: Final feedback report")
    st.caption(
        report.get(
            "aggregation_label",
            "Rule-based report aggregation from assessed turns.",
        )
    )
    st.caption(_origin_label(report.get("origin"), item="report"))
    with st.container(horizontal=True):
        st.metric("Strengths", len(report["strengths"]), icon=":material/thumb_up:")
        st.metric(
            "Recurring issues",
            len(report["recurring_issues"]),
            icon=":material/warning:",
        )
        st.metric(
            "Practice tasks",
            len(report["recommended_tasks"]),
            icon=":material/checklist:",
        )
    st.write(report["interview_readiness_summary"])
    strengths, issues = st.columns(2)
    with strengths:
        st.markdown("#### :material/thumb_up: Demonstrated strengths")
        if report["strengths"]:
            for strength in report["strengths"]:
                st.success(strength)
        else:
            st.caption("No repeated strength signal yet.")
    with issues:
        st.markdown("#### :material/replay: Recurring issues")
        if report["recurring_issues"]:
            for issue in report["recurring_issues"]:
                st.warning(issue)
        else:
            st.caption("No issue repeated across the completed answers.")

    st.markdown("#### :material/checklist: Recommended practice")
    for task in report["recommended_tasks"]:
        with st.container(border=True):
            st.write(task)

    findings = report.get("supporting_findings", [])
    if findings:
        with st.expander("Supporting review findings"):
            for finding in findings:
                line = ""
                if finding.get("line_start"):
                    line_end = finding.get("line_end") or finding["line_start"]
                    line = f" · lines {finding['line_start']}-{line_end}"
                st.markdown(
                    f"**{finding['severity'].upper()} · {finding['category']}"
                    f"{line}**  \n{finding['message']}"
                )


def _render_interview_page() -> None:
    st.subheader(
        f"{_PAGE_ICONS['Interview']} 2 · Practice the explanation", divider="gray"
    )
    review = st.session_state.review_result
    if review is None or not review.get("questions"):
        st.info(
            "Complete a review first. Clutch will turn its findings into the "
            "questions used here."
        )
        st.button("Go to review", on_click=_queue_page, args=("Review",))
        return

    interview = st.session_state.interview_result
    pending = st.session_state.interview_pending
    # Popped once and reused below — only one of the two branches that can
    # display it is ever reached in a given run.
    interview_error = st.session_state.pop("interview_error", None)
    if interview is None:
        st.write(
            "Answer aloud or in writing as if an interviewer asked the question. "
            "Clutch stores only an answer hash and rubric-signal summary."
        )
        if interview_error is not None:
            st.error(interview_error)
        if pending is None:
            if st.button(
                "Start interview", type="primary", icon=":material/play_arrow:"
            ):
                # Stash-then-rerun so the sidebar renders locked before the
                # blocking call starts (see _render_sidebar_nav) — otherwise
                # switching tabs mid-call abandons this run and the result is
                # lost.
                st.session_state.interview_pending = {"type": "start"}
                st.rerun()
        else:
            try:
                with st.spinner("Preparing the first question…"):
                    interview = _api_request(
                        "POST",
                        "/interview/turn",
                        payload={
                            "review_session_id": review["request_id"],
                            "profile_id": st.session_state.profile_id,
                            "role_context": st.session_state.review_role_context,
                            "questions": review["questions"],
                        },
                    )
            except requests.RequestException:
                # Clear pending and rerun so the sidebar (already drawn
                # locked earlier in this run) redraws unlocked; stash the
                # message since rerun() abandons the rest of this run.
                st.session_state.interview_pending = None
                st.session_state.interview_error = (
                    "The interview could not start. Your review is still saved; "
                    "try again in a moment."
                )
                st.rerun()
            else:
                st.session_state.interview_result = interview
                st.session_state.feedback_report = None
                st.session_state.interview_pending = None
                st.rerun()
        return

    assessment = interview.get("assessment")
    if assessment:
        if assessment.get("origin") != "ai_generated":
            st.warning(
                "No successful interview-assessment model call occurred for the "
                "previous answer. The score and feedback are rule-based."
            )
        _render_assessment(assessment)
    if interview["completed"]:
        st.success(
            "Interview complete. Your structured report is ready.",
            icon=":material/celebration:",
        )
        celebrated = st.session_state.setdefault("_celebrated_interviews", set())
        if interview["interview_session_id"] not in celebrated:
            celebrated.add(interview["interview_session_id"])
            st.balloons()
        if st.session_state.feedback_report is None:
            st.session_state.feedback_report = _load_feedback(
                interview["interview_session_id"]
            )
        report = st.session_state.feedback_report
        if report is not None:
            _render_feedback_report(report)
        st.button(
            "View progress",
            type="primary",
            icon=":material/trending_up:",
            on_click=_queue_page,
            args=("Progress",),
        )
        return

    question = interview["question"]
    with st.container(horizontal=True, vertical_alignment="center"):
        st.badge(f"QUESTION {interview['turn_number']}", color="violet")
        st.badge(
            question["difficulty"].upper(),
            color=_DIFFICULTY_COLOR.get(question["difficulty"].lower(), "gray"),
        )
    with st.container(border=True):
        st.caption(_origin_label(question.get("origin"), item="question"))
        st.markdown(f"### {question['question']}")
        st.caption(question["intent"])
        _render_citations(question.get("citations", []))

    if st.session_state.pop("clear_interview_answer", False):
        st.session_state.interview_answer = ""
    answering = pending is not None and pending.get("type") == "answer"
    with st.form("answer-form", clear_on_submit=False):
        answer = st.text_area(
            "Your answer",
            height=220,
            placeholder=(
                "Explain the decision, name a tradeoff, and describe how you would "
                "verify it…"
            ),
            key="interview_answer",
            disabled=answering,
        )
        answered = st.form_submit_button(
            "Submit answer",
            type="primary",
            icon=":material/send:",
            disabled=answering,
        )

    if interview_error is not None:
        st.error(interview_error)

    if answering:
        try:
            with st.spinner("Assessing the reasoning and preparing the next step…"):
                next_state = _api_request(
                    "POST",
                    "/interview/turn",
                    payload={
                        "interview_session_id": pending["interview_session_id"],
                        "answer": pending["answer"],
                    },
                )
        except requests.RequestException:
            # Clear pending and rerun so the sidebar redraws unlocked;
            # stash the message since rerun() abandons the rest of this run.
            st.session_state.interview_pending = None
            st.session_state.interview_error = (
                "The answer was not accepted. Your text remains here; try again "
                "in a moment."
            )
            st.rerun()
        else:
            st.session_state.interview_result = next_state
            st.session_state.feedback_report = None
            st.session_state.progress_result = None
            st.session_state.clear_interview_answer = True
            st.session_state.interview_pending = None
            st.rerun()
        return

    if not answered:
        return
    if not answer.strip():
        st.warning("Write an answer before submitting this turn.")
        return
    st.session_state.interview_pending = {
        "type": "answer",
        "interview_session_id": interview["interview_session_id"],
        "answer": answer,
    }
    st.rerun()


def _load_progress() -> dict[str, Any] | None:
    try:
        with st.spinner("Reading review patterns…"):
            return _api_request(
                "GET",
                f"/progress/{st.session_state.profile_id}",
            )
    except requests.RequestException:
        st.error("Progress could not be loaded. Try again in a moment.")
        return None


def _render_progress_page() -> None:
    st.subheader(f"{_PAGE_ICONS['Progress']} 3 · Track the pattern", divider="gray")
    st.write(
        "Progress is based on repeated finding categories for this generated "
        "practice profile—not on a vague model score."
    )
    if st.session_state.progress_result is None:
        st.session_state.progress_result = _load_progress()
    if st.button("Refresh progress", icon=":material/refresh:"):
        st.session_state.progress_result = _load_progress()

    progress = st.session_state.progress_result
    if progress is None:
        return
    st.caption(progress["time_window"])
    if not progress["evidence_sessions"]:
        st.info(progress["next_practice_tasks"][0], icon=":material/info:")
        st.button(
            "Start a review",
            icon=":material/rocket_launch:",
            on_click=_queue_page,
            args=("Review",),
        )
        return

    with st.container(horizontal=True):
        st.metric(
            "Sessions",
            len(progress["evidence_sessions"]),
            icon=":material/history:",
        )
        st.metric(
            "Improved areas",
            len(progress["improved_areas"]),
            icon=":material/trending_up:",
        )
        st.metric(
            "Recurring issues",
            len(progress["persistent_issues"]),
            icon=":material/replay:",
        )
    if progress["improved_areas"] or progress["persistent_issues"]:
        import pandas as pd

        st.bar_chart(
            pd.Series(
                {
                    "Improved": len(progress["improved_areas"]),
                    "Recurring": len(progress["persistent_issues"]),
                },
                name="count",
            ),
            color="#7C6CFF",
            horizontal=True,
        )

    improved, persistent = st.columns(2)
    with improved:
        st.markdown("#### :material/trending_up: Improved areas")
        if progress["improved_areas"]:
            for area in progress["improved_areas"]:
                st.success(area.replace("_", " ").title())
        else:
            st.caption("Complete another review to reveal improvements.")
    with persistent:
        st.markdown("#### :material/replay: Recurring issues")
        if progress["persistent_issues"]:
            for issue in progress["persistent_issues"]:
                st.warning(issue.replace("_", " ").title())
        else:
            st.caption("No category has repeated across the current evidence.")

    st.markdown("#### :material/checklist: Next practice tasks")
    for task in progress["next_practice_tasks"]:
        with st.container(border=True):
            st.write(task)
    if st.button("Save progress snapshot", icon=":material/save:"):
        try:
            with st.spinner("Saving the derived snapshot…"):
                saved = _api_request(
                    "POST",
                    f"/progress/{st.session_state.profile_id}/snapshots",
                )
        except requests.RequestException:
            st.error(
                "The snapshot was not saved. The current summary is unchanged; "
                "try again in a moment."
            )
        else:
            st.session_state.progress_result = saved
            st.toast("Progress snapshot saved.", icon=":material/save:")


st.set_page_config(
    page_title="Clutch",
    page_icon=":material/rate_review:",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(
    """
    <style>

    [data-testid="stToolbar"],
    [data-testid="stDecoration"],
    [data-testid="stStatusWidget"],
    #MainMenu {
        visibility: hidden;
        height: 0;
    }
    /* The sidebar's "reopen" control lives inside stToolbar, so the rule
       above hides it once a user collapses the sidebar, leaving no way
       back in (nav and logout live only in the sidebar). Force it back
       to visible and pin it so it stays clickable despite the
       zero-height parent. */
    [data-testid="stExpandSidebarButton"] {
        visibility: visible !important;
        height: auto !important;
        position: fixed !important;
        top: 0.6rem;
        left: 0.6rem;
        z-index: 999999;
    }

    :root {
        --clutch-bg: #F7F6F3;
        --clutch-surface: #FFFFFF;
        --clutch-surface-2: #F1F1EE;
        --clutch-border: #E1E1DC;
        --clutch-text: #171717;
        --clutch-text-muted: #666666;
        --clutch-accent: #267A5B;
        --clutch-accent-strong: #1B5C44;
        --clutch-accent-muted: #E3F0E9;
        --clutch-danger: #B3261E;
        --clutch-warning: #8A5A00;
        --clutch-success: #267A5B;
        --clutch-scroll-thumb: #C7C7C0;
        --clutch-scroll-track: #F1F1EE;
        --clutch-scroll-hover: #666666;
        --clutch-scroll-active: #267A5B;
        color-scheme: light;
    }

    html, .stApp {
        font-family: "Avenir Next", "Segoe UI", sans-serif;
        background: var(--clutch-bg);
    }
    [data-testid="stMainBlockContainer"] {
        max-width: 76rem;
        padding-top: 2rem;
    }
    [data-testid="stCaptionContainer"] {
        color: var(--clutch-text-muted);
    }
    [data-testid="stSidebar"] {
        border-right: 1px solid var(--clutch-border);
    }
    textarea, .stTextArea textarea {
        font-family: "SFMono-Regular", Consolas, monospace !important;
        resize: none !important;
    }
    code, pre, [data-testid="stCode"] {
        font-family: "SFMono-Regular", Consolas, monospace !important;
    }
    *:focus-visible {
        outline: 2px solid var(--clutch-accent) !important;
        outline-offset: 2px !important;
    }
    * {
        scrollbar-color: var(--clutch-scroll-thumb) var(--clutch-scroll-track);
        scrollbar-width: thin;
    }
    ::-webkit-scrollbar { width: 10px; height: 10px; }
    ::-webkit-scrollbar-track { background: var(--clutch-scroll-track); }
    ::-webkit-scrollbar-thumb { background: var(--clutch-scroll-thumb); border-radius: 5px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--clutch-scroll-hover); }
    ::-webkit-scrollbar-thumb:active { background: var(--clutch-scroll-active); }
    @media (forced-colors: active) {
        * { scrollbar-color: auto; }
        ::-webkit-scrollbar-thumb { background: ButtonText; }
        ::-webkit-scrollbar-track { background: Canvas; }
        *:focus-visible { outline-color: Highlight !important; }
    }
    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after {
            animation: none !important;
            transition: none !important;
            scroll-behavior: auto !important;
        }
    }
    a { text-underline-offset: 0.2em; }
    button:not(:disabled), a { cursor: pointer; }
    button:disabled { cursor: not-allowed; }
    @media (max-width: 640px) {
        [data-testid="stMainBlockContainer"] { padding: 2.5rem 1rem 2rem; }
    }

    /* Primary buttons: solid, flat, no gradient/glow */
    button[kind="primary"], .stFormSubmitButton button[kind="primary"] {
        background: var(--clutch-accent) !important;
        border: none !important;
        box-shadow: none !important;
    }
    button[kind="primary"]:hover:not(:disabled) {
        background: var(--clutch-accent-strong) !important;
    }

    button[kind="primary"]:active:not(:disabled) {
        background: var(--clutch-accent-strong) !important;
        outline: 2px solid var(--clutch-accent-muted);
    }

    /* Cards: thin border, minimal radius, no gradient fill */
    [data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 0.5rem !important;
    }

    .clutch-brand {
        display: flex;
        align-items: center;
        gap: 0.55rem;
        margin-bottom: 0.2rem;
    }
    .clutch-brand-mark {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 1.85rem;
        height: 1.85rem;
        border-radius: 0.4rem;
        background: var(--clutch-accent);
        color: #FFFFFF;
        font-weight: 700;
        font-size: 0.95rem;
    }
    .clutch-brand-word {
        font-size: 1.2rem;
        font-weight: 700;
        letter-spacing: -0.01em;
        color: var(--clutch-text);
    }
    .clutch-sidebar-tagline {
        color: var(--clutch-text-muted);
        font-size: 0.85rem;
        line-height: 1.5;
        margin: 0.1rem 0 1.1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

_handle_stytch_redirect()
authenticated_profile_id = _authenticated_profile_id()
if _auth_configured() and authenticated_profile_id is None:
    _render_landing_gate()
    st.stop()

_initialize_state(authenticated_profile_id)
active_page = _render_sidebar_nav()
if active_page == "Review":
    _render_review_page()
elif active_page == "Interview":
    _render_interview_page()
else:
    _render_progress_page()
