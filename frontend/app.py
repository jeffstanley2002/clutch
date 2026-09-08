"""Streamlit workbench for review, interview practice, and progress."""

from __future__ import annotations

import os
from typing import Any, Literal, cast
from uuid import uuid4

import requests
import streamlit as st

API_BASE_URL = os.getenv("CLUTCH_API_BASE_URL", "http://localhost:8000")
PageName = Literal["Review", "Interview", "Progress"]


def _initialize_state() -> None:
    defaults: dict[str, Any] = {
        "profile_id": str(uuid4()),
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
    api_key = os.getenv("CLUTCH_API_KEY", "").strip()
    response = requests.request(
        method,
        f"{API_BASE_URL}{path}",
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


def _render_finding(finding: dict[str, Any]) -> None:
    with st.container(border=True):
        st.markdown(f"**{finding['severity'].upper()} · {finding['category']}**")
        st.markdown(f"### {finding['message']}")
        if finding.get("line_start"):
            line_end = finding.get("line_end") or finding["line_start"]
            st.caption(f"Lines {finding['line_start']}-{line_end}")
        st.code(finding["evidence"], language="python")
        st.write(finding["explanation"])
        st.info(finding["suggestion"])
        citations = finding.get("citations", [])
        if citations:
            st.caption(
                "Citations: " + ", ".join(citation["title"] for citation in citations)
            )


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
            f"Fetched {len(ingestion['files_included'])} Python file(s) from "
            f"{ingestion['owner']}/{ingestion['repository']} ({source_label}) through "
            "the read-only MCP boundary. All fetched content was treated as untrusted."
        )

    st.caption(
        f"Mode: {review['mode']} · Confidence: {review['confidence']:.0%} · "
        f"Request: {review['request_id']} · {review['latency_ms']:.1f} ms"
    )
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
                st.markdown(f"**{question['difficulty'].upper()}**")
                st.write(question["question"])
                st.caption(question["intent"])
        st.button(
            "Practice these questions",
            type="primary",
            on_click=_queue_page,
            args=("Interview",),
        )


def _render_assessment(assessment: dict[str, Any]) -> None:
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
        st.markdown(f"### {question['question']}")
        st.caption(question["intent"])

    with st.form("answer-form", clear_on_submit=False):
        answer = st.text_area(
            "Your answer",
            height=220,
            placeholder=(
                "Explain the decision, name a tradeoff, and describe how you would "
                "verify it…"
            ),
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

_initialize_state()
active_page = _render_header()
if active_page == "Review":
    _render_review_page()
elif active_page == "Interview":
    _render_interview_page()
else:
    _render_progress_page()
