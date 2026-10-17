"""Phase 16H unit tests for analysis semantics."""

from __future__ import annotations

import pytest
from nexus_board.analysis.semantics import (
    ANALYSIS_STAGE_IDS,
    assess_metric,
    build_verification_summary,
    new_investigation,
    validate_investigation_dict,
)


def test_exploration_investigation_allows_empty_requirement_links() -> None:
    inv = new_investigation(
        title="Explore vibration patterns",
        purpose="exploration",
        question="Explore vibration patterns in the uploaded IMU data.",
        linked_requirement_ids=[],
    )
    payload = inv.as_dict()
    validate_investigation_dict(payload)
    assert payload["linkedRequirementIds"] == []
    assert payload["purpose"] == "exploration"
    assert payload["stageVocabulary"] == list(ANALYSIS_STAGE_IDS)


def test_deterministic_assessment_is_authoritative() -> None:
    assert assess_metric(metric_value=0.038, operator="<", threshold=0.05) == "PASS"
    assert assess_metric(metric_value=0.12, operator="<", threshold=0.10) == "FAIL"
    assert assess_metric(metric_value=None, operator="<", threshold=0.10) == "INCONCLUSIVE"
    summary = build_verification_summary(
        metric_id="accel_x_rms_noise_g",
        metric_value=0.038,
        unit="g",
        requirement_id="req_R7",
        operator="<",
        threshold=0.10,
    )
    assert summary["assessment"] == "PASS"
    assert summary["authority"] == "deterministic-code"


def test_unknown_stage_rejected() -> None:
    with pytest.raises(ValueError):
        new_investigation(title="x", lifecycle_stage="CUSTOM")


def test_validate_investigation_dict_raises_value_error_for_bad_types() -> None:
    import pytest

    base = new_investigation(title="Noise check", purpose="verification").as_dict()
    validate_investigation_dict(base)
    bad_values = [
        ("investigationId", "   "),
        ("purpose", ["verification"]),
        ("lifecycleStage", ["INPUTS"]),
        ("question", 3),
        ("linkedRequirementIds", "R7"),
        ("linkedComponentIds", [1]),
        ("linkedTestPlanIds", None),
        ("linkedEvidenceIds", {"a": "b"}),
        ("verificationCriterion", "metric < 0.1"),
        ("stageVocabulary", ["INPUTS", "DONE"]),
    ]
    for field, value in bad_values:
        with pytest.raises(ValueError):
            validate_investigation_dict({**base, field: value})
    with pytest.raises(ValueError):
        validate_investigation_dict(["not", "a", "dict"])  # type: ignore[arg-type]
    # Optional fields may be absent or null.
    minimal = {k: base[k] for k in ("schemaVersion", "investigationId", "title", "purpose")}
    validate_investigation_dict(minimal)
    validate_investigation_dict({**minimal, "question": None, "verificationCriterion": None})
