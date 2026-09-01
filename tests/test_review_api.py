from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_health_check_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_review_returns_structured_findings_for_static_issues() -> None:
    response = client.post(
        "/review",
        json={
            "code": "def collect(value, bucket=[]):\n    # TODO clean this up\n    print(value)\n    return bucket\n",
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

