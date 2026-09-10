from clutch.observability.audit import audit_trace_observations


def _review_observations() -> list[dict[str, object]]:
    observations: list[dict[str, object]] = []
    for name in (
        "review.request",
        "review.parse_code",
        "review.static_review",
        "review.retrieve_principles",
        "review.synthesize",
        "review.validate_findings",
        "review.generate_questions",
        "review.persistence",
    ):
        observation: dict[str, object] = {
            "name": name,
            "latency": 0.01,
            "level": "DEFAULT",
            "status_message": "succeeded",
            "metadata": {
                "redaction_policy": "hashes_counts_ids_only.v1",
                "stage_status": "succeeded",
            },
            "input": {"request_id": "opaque-id"},
            "output": {"count": 1},
        }
        if name in {"review.synthesize", "review.generate_questions"}:
            observation.update(
                {
                    "provided_model_name": "test-model",
                    "version": "test.v1",
                    "usage_details": {"input": 10, "output": 5, "total": 15},
                    "cost_details": {"total": 0.001},
                }
            )
        observations.append(observation)
    return observations


def test_trace_audit_accepts_complete_native_redacted_trace() -> None:
    report = audit_trace_observations(
        _review_observations(),
        trace_id="trace-1",
        workflow="review",
    )

    assert report.passed is True
    assert report.native_generation_names == [
        "review.generate_questions",
        "review.synthesize",
    ]
    assert report.redaction_evidence_present is True


def test_trace_audit_accepts_native_total_cost_projection() -> None:
    observations = _review_observations()
    for observation in observations:
        if observation["name"] in {
            "review.synthesize",
            "review.generate_questions",
        }:
            observation.pop("cost_details")
            observation["total_cost"] = 0.001

    report = audit_trace_observations(
        observations,
        trace_id="trace-native-total-cost",
        workflow="review",
    )

    assert report.passed is True
    assert all(item.cost_present for item in report.evidence if item.model)


def test_trace_audit_rejects_missing_native_usage_and_raw_keys() -> None:
    observations = _review_observations()
    generation = next(
        item for item in observations if item["name"] == "review.synthesize"
    )
    generation.pop("usage_details")
    generation["input"] = {"code": "must never be present"}

    report = audit_trace_observations(
        observations,
        trace_id="trace-2",
        workflow="review",
    )

    assert report.passed is False
    assert "review.synthesize lacks native token usage" in report.failures
    assert "review.synthesize exposes a prohibited IO key" in report.failures


def test_trace_audit_requires_safe_category_for_expected_fallback() -> None:
    observations = _review_observations()
    generation = next(
        item for item in observations if item["name"] == "review.synthesize"
    )
    generation["level"] = "WARNING"
    generation["metadata"] = {
        "redaction_policy": "hashes_counts_ids_only.v1",
        "stage_status": "fallback",
    }

    report = audit_trace_observations(
        observations,
        trace_id="trace-3",
        workflow="review",
        expect_fallback=True,
    )

    assert report.passed is False
    assert "review.synthesize lacks a safe failure category" in report.failures


def test_trace_audit_does_not_accept_fallback_as_model_backed() -> None:
    observations = _review_observations()
    for observation in observations:
        if observation["name"] in {
            "review.synthesize",
            "review.generate_questions",
        }:
            observation["level"] = "WARNING"
            observation["metadata"] = {
                "redaction_policy": "hashes_counts_ids_only.v1",
                "stage_status": "fallback",
                "failure_category": "model_not_configured",
            }

    report = audit_trace_observations(
        observations,
        trace_id="trace-fallback-misclassified",
        workflow="review",
    )

    assert report.passed is False
    assert any(
        failure.startswith("missing complete native generations:")
        for failure in report.failures
    )
