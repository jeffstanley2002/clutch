from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_health_check_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_review_returns_structured_findings_for_static_issues() -> None:
    code = "\n".join(
        [
            "def collect(value, bucket=[]):",
            "    # TODO clean this up",
            "    print(value)",
            "    return bucket",
        ]
    )
    response = client.post(
        "/review",
        json={
            "code": code,
            "language": "python",
            "role_context": "backend intern",
        },
    )

    assert response.status_code == 200
    findings = response.json()

    assert len(findings) == 3
    assert {finding["category"] for finding in findings} == {
        "correctness",
        "maintainability",
    }
    assert all(finding["citations"] for finding in findings)
    assert all("id" in finding for finding in findings)
    citation_source_ids = {
        citation["source_id"]
        for finding in findings
        for citation in finding["citations"]
    }
    assert citation_source_ids == {
        "seed.clean_code.explicit_incomplete_work",
        "seed.clean_code.boundary_observability",
        "seed.clean_code.safe_python_defaults",
    }


def test_review_uses_parsed_line_metadata_for_large_functions() -> None:
    body = "\n".join(f"    value += {number}" for number in range(45))
    response = client.post(
        "/review",
        json={
            "code": f"def calculate(value):\n{body}\n    return value\n",
            "language": "python",
            "role_context": "backend intern",
        },
    )

    assert response.status_code == 200
    findings = response.json()
    long_function = next(
        finding
        for finding in findings
        if finding["id"].startswith("finding-long-function")
    )

    assert long_function["line_start"] == 1
    assert long_function["line_end"] == 47
    assert "`calculate`" in long_function["evidence"]
    assert (
        long_function["citations"][0]["source_id"]
        == "seed.clean_code.small_reviewable_units"
    )


def test_review_preserves_long_snippet_finding_for_top_level_code() -> None:
    code = "\n".join(f"value += {number}" for number in range(65))
    response = client.post(
        "/review",
        json={
            "code": code,
            "language": "python",
            "role_context": "backend intern",
        },
    )

    assert response.status_code == 200
    findings = response.json()
    assert any(finding["id"] == "finding-long-snippet" for finding in findings)


def test_review_rejects_blank_code() -> None:
    response = client.post(
        "/review",
        json={
            "code": "   ",
            "language": "python",
            "role_context": "backend intern",
        },
    )

    assert response.status_code == 422
