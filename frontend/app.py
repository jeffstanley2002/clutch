"""Streamlit UI for the Day 1 pasted-code review workflow."""

import os

import requests
import streamlit as st


API_BASE_URL = os.getenv("CLUTCH_API_BASE_URL", "http://localhost:8000")


st.set_page_config(page_title="Clutch", page_icon="CL", layout="wide")
st.title("Clutch")

role_context = st.text_input("Role context", value="backend intern")
code = st.text_area(
    "Paste Python code",
    height=360,
    placeholder="def calculate_total(items):\n    ...",
)

submitted = st.button("Review code", type="primary")

if submitted:
    payload = {
        "code": code,
        "language": "python",
        "role_context": role_context,
    }

    try:
        response = requests.post(
            f"{API_BASE_URL}/review",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        st.error(f"Review request failed: {exc}")
    else:
        findings = response.json()
        st.subheader("Findings")
        for finding in findings:
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
                        "Citations: "
                        + ", ".join(citation["title"] for citation in citations)
                    )

