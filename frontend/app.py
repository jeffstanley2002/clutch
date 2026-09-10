"""Streamlit workbench for review, interview practice, and progress."""

from __future__ import annotations

import os
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
        if stage.get("status") == "fallback" and stage.get("stage") != "review_synthesis":
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

_initialize_state()
active_page = _render_header()
if active_page == "Review":
    _render_review_page()
elif active_page == "Interview":
    _render_interview_page()
else:
    _render_progress_page()
