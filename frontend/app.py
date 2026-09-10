"""Streamlit workbench for review, interview practice, and progress."""

from __future__ import annotations

import os
from hashlib import sha256
from typing import Any, Literal, cast
from urllib.parse import unquote, urlparse
from uuid import uuid4

import requests
import streamlit as st

PageName = Literal["Review", "Interview", "Progress"]

_STAGE_LABELS = {
    "retrieval": "Review retrieval",
    "review_synthesis": "Review synthesis",
    "question_generation": "Question generation",
    "interview_retrieval": "Interview retrieval",
    "interview_assessment": "Interview assessment",
    "final_aggregation": "Final report aggregation",
}
_FAILURE_LABELS = {
    "model_not_configured": "no model credentials were configured",
    "budget_rejected": "the model spend ceiling rejected the call",
    "provider_error": "the model provider did not complete the call",
    "schema_validation_failed": "the model response failed schema validation",
    "grounding_validation_failed": "the model response failed grounding validation",
    "retrieval_failed": "retrieval did not complete",
    "fallback_failed": "the fallback path did not complete",
    "persistence_failed": "derived result persistence did not complete",
    "unknown": "the stage failed for a safely redacted reason",
}


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
    try:
        auth_config = st.secrets.get("auth", None)
    except Exception:
        return False
    return bool(auth_config)


def _user_value(name: str) -> str:
    try:
        value = st.user.get(name, "")
    except Exception:
        value = getattr(st.user, name, "")
    return str(value or "").strip()


def _authenticated_profile_id() -> str | None:
    if not _auth_configured():
        return None
    user = st.user
    if not getattr(user, "is_logged_in", False):
        return None
    identity = (
        _user_value("sub")
        or _user_value("email")
        or _user_value("preferred_username")
        or _user_value("name")
    )
    if not identity:
        return None
    digest = sha256(identity.encode("utf-8")).hexdigest()
    return f"user_{digest[:40]}"


def _render_landing_gate() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stMainBlockContainer"] {
            padding-top: 1.75rem;
            padding-bottom: 3rem;
        }
        .st-key-landing_hero {
            position: relative;
            overflow: hidden;
            padding: clamp(1.4rem, 3vw, 2.6rem);
            border: 1px solid #d9e0ec;
            border-top: 4px solid #365fd9;
            border-radius: 0.8rem;
            background: #ffffff;
        }
        .st-key-landing_hero [data-testid="stHorizontalBlock"] {
            gap: clamp(1.75rem, 4vw, 4rem);
        }
        .clutch-eyebrow {
            color: #365fd9;
            font-size: 0.82rem;
            font-weight: 700;
            letter-spacing: 0.045em;
            text-transform: uppercase;
        }
        .clutch-hero-title {
            max-width: 14ch;
            margin: 0.7rem 0 1rem;
            color: #172033;
            font-size: clamp(2.7rem, 5vw, 4.6rem);
            line-height: 0.96;
            letter-spacing: -0.035em;
        }
        .clutch-hero-title > a {
            display: none;
        }
        .clutch-hero-copy {
            max-width: 37rem;
            margin: 0;
            color: #42506a;
            font-size: clamp(1rem, 1.35vw, 1.14rem);
            line-height: 1.65;
        }
        .clutch-proof-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.55rem;
            margin: 1.25rem 0 0;
        }
        .clutch-chip {
            border: 1px solid #c8d3e6;
            border-radius: 999px;
            color: #33415c;
            background: #f5f7fb;
            padding: 0.42rem 0.7rem;
            font-size: 0.88rem;
            font-weight: 600;
        }
        .st-key-landing_hero [data-testid="stButton"] {
            margin-top: 1.4rem;
        }
        .st-key-landing_hero button[kind="primary"] {
            min-height: 3rem;
            padding-inline: 1.15rem;
            font-weight: 700;
        }
        .clutch-preview {
            display: grid;
            gap: 0.7rem;
        }
        .clutch-preview-label {
            display: flex;
            align-items: center;
            gap: 0.65rem;
            margin-bottom: 0.15rem;
            color: #5e6a7d;
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.06em;
            text-transform: uppercase;
        }
        .clutch-preview-label::after {
            content: "";
            flex: 1;
            height: 1px;
            background: #d9e0ec;
        }
        .clutch-note {
            border: 1px solid #d9e0ec;
            border-left: 4px solid #365fd9;
            border-radius: 0.55rem;
            background: #f8faff;
            padding: 0.95rem 1rem;
            color: #4c5a72;
            font-size: 0.94rem;
            line-height: 1.55;
        }
        .clutch-note strong {
            display: block;
            margin-bottom: 0.3rem;
            color: #172033;
        }
        .clutch-note code {
            white-space: normal;
            color: #2448b5;
            background: #eef2f8;
            border-radius: 0.35rem;
            padding: 0.12rem 0.3rem;
        }
        .clutch-sections {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 1rem;
            margin-top: 1.1rem;
        }
        .clutch-panel {
            border: 1px solid #d9e0ec;
            border-radius: 0.55rem;
            background: #ffffff;
            padding: 1.1rem;
            min-height: 11.5rem;
        }
        .clutch-panel h2 {
            margin: 0 0 0.7rem;
            color: #172033;
            font-size: 1.05rem;
            letter-spacing: 0;
        }
        .clutch-panel p,
        .clutch-panel li {
            color: #4c5a72;
            line-height: 1.6;
            font-size: 0.96rem;
        }
        .clutch-panel ul {
            padding-left: 1.1rem;
            margin-bottom: 0;
        }
        .clutch-cta-copy {
            max-width: 34rem;
            color: #5e6a7d;
            font-size: 0.9rem;
            line-height: 1.55;
            margin: 0.65rem 0 0;
        }
        @media (max-width: 820px) {
            .st-key-landing_hero [data-testid="stHorizontalBlock"] {
                flex-wrap: wrap;
            }
            .st-key-landing_hero [data-testid="stColumn"] {
                flex: 1 1 100%;
                width: 100%;
            }
            .clutch-sections {
                grid-template-columns: 1fr;
            }
            .clutch-panel {
                min-height: 0;
            }
            .clutch-hero-title {
                max-width: 12ch;
                font-size: clamp(2.6rem, 13vw, 4rem);
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.container(key="landing_hero"):
        copy, preview = st.columns(
            [1.08, 0.92], gap="large", vertical_alignment="center"
        )
        with copy:
            st.markdown(
                """
                <div class="clutch-eyebrow">
                    AI code review + interview practice
                </div>
                <h1 class="clutch-hero-title">
                    Clutch turns code review into interview prep.
                </h1>
                <p class="clutch-hero-copy">
                    Paste Python or review a GitHub repo, get cited findings,
                    practice the follow-up questions an interviewer would ask,
                    and track the engineering habits that improve over time.
                </p>
                <div class="clutch-proof-row" aria-label="Product capabilities">
                    <span class="clutch-chip">Cited code findings</span>
                    <span class="clutch-chip">GitHub repo review</span>
                    <span class="clutch-chip">Practice interview loop</span>
                    <span class="clutch-chip">Progress history</span>
                    <span class="clutch-chip">Privacy-aware tracing</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.button(
                "Log in with Google",
                key="landing_login",
                type="primary",
                on_click=st.login,
            )
            st.markdown(
                """
                <p class="clutch-cta-copy">
                    Sign in to run a private practice session, save progress,
                    and return to your review history later.
                </p>
                """,
                unsafe_allow_html=True,
            )
        with preview:
            st.markdown(
                """
                <div class="clutch-preview" aria-label="Clutch workflow preview">
                    <div class="clutch-preview-label">
                        The practice loop
                    </div>
                    <div class="clutch-note">
                        <strong>1. Review evidence</strong>
                        <code># TODO validate discounts before launch</code>
                    </div>
                    <div class="clutch-note">
                        <strong>2. Explain the tradeoff</strong>
                        Generated questions probe scope, ownership, testing, and
                        failure modes.
                    </div>
                    <div class="clutch-note">
                        <strong>3. Track progress</strong>
                        Derived snapshots show recurring issues and next practice
                        tasks without storing raw code.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown(
        """
        <div class="clutch-sections">
            <section class="clutch-panel">
                <h2>From code to signal</h2>
                <ul>
                    <li>Findings cite clean-code and review guidance.</li>
                    <li>Each issue includes evidence, impact, and a fix path.</li>
                    <li>GitHub ingestion is read-only and scope-bounded.</li>
                </ul>
            </section>
            <section class="clutch-panel">
                <h2>Practice the explanation</h2>
                <ul>
                    <li>Review, interview, feedback, and progress are one flow.</li>
                    <li>Questions probe design choices and tradeoffs.</li>
                    <li>Answer feedback turns weak spots into next tasks.</li>
                </ul>
            </section>
            <section class="clutch-panel">
                <h2>Built for safe practice</h2>
                <ul>
                    <li>Google handles authentication.</li>
                    <li>Raw code and raw answers are not stored durably.</li>
                    <li>Progress is tied to an opaque profile ID.</li>
                </ul>
            </section>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _initialize_state(profile_id: str | None = None) -> None:
    defaults: dict[str, Any] = {
        "profile_id": profile_id or str(uuid4()),
        "workflow_nav": "Review",
        "review_input_mode": "Paste code",
        "review_result": None,
        "github_ingestion": None,
        "review_role_context": "backend intern",
        "interview_result": None,
        "feedback_report": None,
        "progress_result": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    if profile_id is not None and st.session_state.profile_id != profile_id:
        st.session_state.profile_id = profile_id
        st.session_state.review_result = None
        st.session_state.github_ingestion = None
        st.session_state.interview_result = None
        st.session_state.feedback_report = None
        st.session_state.progress_result = None
    requested_page = st.session_state.pop("requested_page", None)
    if requested_page is not None:
        st.session_state.workflow_nav = requested_page


def _queue_page(page: PageName) -> None:
    st.session_state.requested_page = page


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
        timeout=30,
    )
    response.raise_for_status()
    result: dict[str, Any] = response.json()
    return result


def _render_header() -> PageName:
    st.caption("READ-ONLY REVIEW  /  PYTHON  /  INTERVIEW PRACTICE")
    st.title("Turn code review into interview practice")
    st.write(
        "Move from concrete code evidence to a practiced explanation, then track "
        "which engineering habits are changing across sessions."
    )
    if _auth_configured() and getattr(st.user, "is_logged_in", False):
        name = _user_value("name") or _user_value("email") or "Signed in"
        account, action = st.columns([3, 1])
        with account:
            st.caption(f"Signed in as {name}")
        with action:
            st.button("Log out", on_click=st.logout)
    selected = st.segmented_control(
        "Workflow",
        options=["Review", "Interview", "Progress"],
        key="workflow_nav",
        selection_mode="single",
    )
    st.caption(
        "Review → Interview → Progress  ·  Practice profile "
        f"{st.session_state.profile_id[:8]}"
    )
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
    with st.expander("How this result was produced"):
        for stage in provenance:
            stage_name = str(stage.get("stage") or "unknown")
            label = _STAGE_LABELS.get(stage_name, stage_name)
            details = [str(stage.get("status", "unknown")).replace("_", " ")]
            if stage.get("model_name"):
                details.append(str(stage["model_name"]))
            if stage.get("prompt_version"):
                details.append(str(stage["prompt_version"]))
            input_tokens = stage.get("input_tokens")
            output_tokens = stage.get("output_tokens")
            if isinstance(input_tokens, int) or isinstance(output_tokens, int):
                details.append(f"{(input_tokens or 0) + (output_tokens or 0):,} tokens")
            details.append(f"{float(stage.get('latency_ms') or 0):,.1f} ms")
            estimated_cost = float(stage.get("estimated_cost_usd") or 0)
            if estimated_cost > 0:
                details.append(f"estimated ${estimated_cost:.6f}")
            failure_category = stage.get("failure_category")
            if failure_category:
                details.append(
                    _FAILURE_LABELS.get(failure_category, str(failure_category))
                )
            st.markdown(f"**{label}**  ")
            st.caption(" · ".join(details))


def _render_review_provenance(review: dict[str, Any]) -> None:
    mode = review.get("mode")
    provenance = review.get("provenance", [])
    if mode == "model":
        st.success("AI-generated review synthesis completed.")
    elif mode == "static_fallback":
        st.warning(
            "No successful review model call occurred. These findings came from "
            "deterministic static analysis, so they are not AI-generated."
        )
    else:
        st.warning(
            "No successful review model call occurred and no static issue matched. "
            "This result used retrieval-only/static logic, not AI synthesis."
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


def _render_finding(finding: dict[str, Any]) -> None:
    with st.container(border=True):
        st.caption(_origin_label(finding.get("origin"), item="finding"))
        st.markdown(f"**{finding['severity'].upper()} · {finding['category']}**")
        st.markdown(f"### {finding['message']}")
        if finding.get("line_start"):
            line_end = finding.get("line_end") or finding["line_start"]
            st.caption(f"Lines {finding['line_start']}-{line_end}")
        st.code(finding["evidence"], language="python")
        st.write(finding["explanation"])
        st.info(finding["suggestion"])
        _render_citations(finding.get("citations", []))


def _render_review_page() -> None:
    st.subheader("1 · Review the evidence")
    st.write(
        "Paste Python or fetch a public GitHub repository/PR through the read-only "
        "MCP boundary. Durable history contains only hashes and derived metadata."
    )
    input_mode = st.segmented_control(
        "Review source",
        options=["Paste code", "GitHub"],
        key="review_input_mode",
        selection_mode="single",
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
                    "private access remains backend-only."
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
        )

    if submitted:
        if input_mode != "GitHub" and not code.strip():
            st.warning("Paste a Python snippet before starting the review.")
        elif input_mode == "GitHub" and not source_url.strip():
            st.warning("Enter a GitHub repository or pull-request URL.")
        else:
            try:
                with st.spinner(
                    "Reviewing structure, evidence, and interview signals…"
                ):
                    if input_mode == "GitHub":
                        github_result = _api_request(
                            "POST",
                            "/review/github",
                            payload={
                                "source_url": source_url,
                                "ref": ref.strip() or None,
                                "role_context": role_context,
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
                                "code": code,
                                "language": "python",
                                "role_context": role_context,
                                "session_id": st.session_state.profile_id,
                            },
                        )
                        ingestion = None
            except requests.RequestException as exc:
                st.error(
                    "The review service could not complete this request. Keep the "
                    "code here, check that FastAPI is running, then try again. "
                    f"Technical detail: {exc}"
                )
            else:
                st.session_state.review_result = review
                st.session_state.github_ingestion = ingestion
                st.session_state.review_role_context = role_context.strip() or (
                    "backend intern"
                )
                st.session_state.interview_result = None
                st.session_state.feedback_report = None
                st.session_state.progress_result = None

    review = st.session_state.review_result
    if review is None:
        st.info(
            "Start with a function you recently wrote—especially one with error "
            "handling, state, or an unfinished tradeoff."
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

    st.caption(
        f"Confidence: {review['confidence']:.0%} · "
        f"Request: {review['request_id']} · {review['latency_ms']:.1f} ms"
    )
    _render_review_provenance(review)
    st.markdown("#### Findings")
    if review["findings"]:
        for finding in review["findings"]:
            _render_finding(finding)
    else:
        st.success(
            "No deterministic issue was found in this snippet. This is not proof "
            "of correctness; add broader context or tests for a deeper review."
        )

    questions = review.get("questions", [])
    if questions:
        st.markdown("#### Interview follow-ups")
        for question in questions:
            with st.container(border=True):
                st.caption(_origin_label(question.get("origin"), item="question"))
                st.markdown(f"**{question['difficulty'].upper()}**")
                st.write(question["question"])
                st.caption(question["intent"])
                if question.get("finding_id"):
                    st.caption(f"Grounded in finding {question['finding_id']}")
                _render_citations(question.get("citations", []))
        st.button(
            "Practice these questions",
            type="primary",
            on_click=_queue_page,
            args=("Interview",),
        )


def _render_assessment(assessment: dict[str, Any]) -> None:
    st.caption(_origin_label(assessment.get("origin"), item="assessment"))
    st.markdown(f"#### Answer feedback · {assessment['score']}/5")
    st.write(assessment["feedback"])
    left, right = st.columns(2)
    with left:
        st.markdown("**What worked**")
        if assessment["strengths"]:
            for strength in assessment["strengths"]:
                st.write(f"• {strength}")
        else:
            st.caption("No strong signal yet—add more explicit reasoning.")
    with right:
        st.markdown("**Strengthen next**")
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
    except requests.RequestException as exc:
        st.error(
            "The final report could not be loaded. The interview is still complete; "
            f"retry after checking the backend. Technical detail: {exc}"
        )
        return None


def _render_feedback_report(report: dict[str, Any]) -> None:
    st.markdown("### Final feedback report")
    st.caption(
        report.get(
            "aggregation_label",
            "Rule-based report aggregation from assessed turns.",
        )
    )
    st.caption(_origin_label(report.get("origin"), item="report"))
    st.write(report["interview_readiness_summary"])
    strengths, issues = st.columns(2)
    with strengths:
        st.markdown("#### Demonstrated strengths")
        if report["strengths"]:
            for strength in report["strengths"]:
                st.success(strength)
        else:
            st.caption("No repeated strength signal yet.")
    with issues:
        st.markdown("#### Recurring issues")
        if report["recurring_issues"]:
            for issue in report["recurring_issues"]:
                st.warning(issue)
        else:
            st.caption("No issue repeated across the completed answers.")

    st.markdown("#### Recommended practice")
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
    st.subheader("2 · Practice the explanation")
    review = st.session_state.review_result
    if review is None or not review.get("questions"):
        st.info(
            "Complete a review first. Clutch will turn its findings into the "
            "questions used here."
        )
        st.button("Go to review", on_click=_queue_page, args=("Review",))
        return

    interview = st.session_state.interview_result
    if interview is None:
        st.write(
            "Answer aloud or in writing as if an interviewer asked the question. "
            "Clutch stores only an answer hash and rubric-signal summary."
        )
        if st.button("Start interview", type="primary"):
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
            except requests.RequestException as exc:
                st.error(
                    "The interview could not start. Check the backend and try "
                    f"again. Technical detail: {exc}"
                )
            else:
                st.session_state.interview_result = interview
                st.session_state.feedback_report = None
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
        st.success("Interview complete. Your structured report is ready.")
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
            on_click=_queue_page,
            args=("Progress",),
        )
        return

    question = interview["question"]
    st.caption(
        f"QUESTION {interview['turn_number']}  /  {question['difficulty'].upper()}"
    )
    with st.container(border=True):
        st.caption(_origin_label(question.get("origin"), item="question"))
        st.markdown(f"### {question['question']}")
        st.caption(question["intent"])
        _render_citations(question.get("citations", []))

    if st.session_state.pop("clear_interview_answer", False):
        st.session_state.interview_answer = ""
    with st.form("answer-form", clear_on_submit=False):
        answer = st.text_area(
            "Your answer",
            height=220,
            placeholder=(
                "Explain the decision, name a tradeoff, and describe how you would "
                "verify it…"
            ),
            key="interview_answer",
        )
        answered = st.form_submit_button("Submit answer", type="primary")
    if not answered:
        return
    if not answer.strip():
        st.warning("Write an answer before submitting this turn.")
        return
    try:
        with st.spinner("Assessing the reasoning and preparing the next step…"):
            next_state = _api_request(
                "POST",
                "/interview/turn",
                payload={
                    "interview_session_id": interview["interview_session_id"],
                    "answer": answer,
                },
            )
    except requests.RequestException as exc:
        st.error(
            "The answer was not accepted. Your text remains here; check the backend "
            f"and try again. Technical detail: {exc}"
        )
    else:
        st.session_state.interview_result = next_state
        st.session_state.feedback_report = None
        st.session_state.progress_result = None
        st.session_state.clear_interview_answer = True
        st.rerun()


def _load_progress() -> dict[str, Any] | None:
    try:
        with st.spinner("Reading review patterns…"):
            return _api_request(
                "GET",
                f"/progress/{st.session_state.profile_id}",
            )
    except requests.RequestException as exc:
        st.error(
            "Progress could not be loaded. Check the backend and try again. "
            f"Technical detail: {exc}"
        )
        return None


def _render_progress_page() -> None:
    st.subheader("3 · Track the pattern")
    st.write(
        "Progress is based on repeated finding categories for this generated "
        "practice profile—not on a vague model score."
    )
    if st.session_state.progress_result is None:
        st.session_state.progress_result = _load_progress()
    if st.button("Refresh progress"):
        st.session_state.progress_result = _load_progress()

    progress = st.session_state.progress_result
    if progress is None:
        return
    st.caption(progress["time_window"])
    if not progress["evidence_sessions"]:
        st.info(progress["next_practice_tasks"][0])
        st.button("Start a review", on_click=_queue_page, args=("Review",))
        return

    improved, persistent = st.columns(2)
    with improved:
        st.markdown("#### Improved areas")
        if progress["improved_areas"]:
            for area in progress["improved_areas"]:
                st.success(area.replace("_", " ").title())
        else:
            st.caption("Complete another review to reveal improvements.")
    with persistent:
        st.markdown("#### Recurring issues")
        if progress["persistent_issues"]:
            for issue in progress["persistent_issues"]:
                st.warning(issue.replace("_", " ").title())
        else:
            st.caption("No category has repeated across the current evidence.")

    st.markdown("#### Next practice tasks")
    for task in progress["next_practice_tasks"]:
        with st.container(border=True):
            st.write(task)
    if st.button("Save progress snapshot"):
        try:
            with st.spinner("Saving the derived snapshot…"):
                saved = _api_request(
                    "POST",
                    f"/progress/{st.session_state.profile_id}/snapshots",
                )
        except requests.RequestException as exc:
            st.error(
                "The snapshot was not saved. The current summary is unchanged; "
                f"try again after checking the backend. Technical detail: {exc}"
            )
        else:
            st.session_state.progress_result = saved
            st.success("Progress snapshot saved.")


st.set_page_config(page_title="Clutch", page_icon="CL", layout="wide")
st.markdown(
    """
    <style>
    .stApp {
        font-family: "Avenir Next", Avenir, "Segoe UI", sans-serif;
    }
    [data-testid="stMainBlockContainer"] {
        max-width: 76rem;
        padding-top: 3rem;
    }
    [data-testid="stCaptionContainer"] {
        color: #5e6a7d;
    }
    textarea {
        font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace !important;
        resize: none !important;
    }
    *:focus-visible {
        outline: 3px solid #88a4ff !important;
        outline-offset: 2px !important;
    }
    html {
        scrollbar-color: #a8b4c9 #eef2f8;
        scrollbar-width: thin;
    }
    @media (forced-colors: active) {
        html { scrollbar-color: auto; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

authenticated_profile_id = _authenticated_profile_id()
if _auth_configured() and authenticated_profile_id is None:
    _render_landing_gate()
    st.stop()

_initialize_state(authenticated_profile_id)
active_page = _render_header()
if active_page == "Review":
    _render_review_page()
elif active_page == "Interview":
    _render_interview_page()
else:
    _render_progress_page()
