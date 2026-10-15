"""Analysis product semantics (Phase 16H).

Lightweight investigation metadata, Nexus-owned stage vocabulary, and
deterministic verification assessment. Does not introduce a new primary
board artifact or Phase 14 session primitive.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from nexus_board.ids import new_id

ANALYSIS_STAGE_IDS: tuple[str, ...] = (
    "INPUTS",
    "TRANSFORM",
    "METRICS",
    "VISUALIZATION",
    "VERIFY",
)

AnalysisPurpose = Literal["exploration", "verification"]
AssessmentResult = Literal["PASS", "FAIL", "INCONCLUSIVE"]
ComparisonOperator = Literal["<", "<=", ">", ">=", "==", "!="]

INVESTIGATION_METADATA_PATH = "nexus/investigation.json"
VERIFICATION_CONTRACT_PATH = "nexus/verification.json"

# RMS of demeaned accel_x (stationary noise definition used by golden Analysis).
RMS_NOISE_DEFINITION = "demeaned"


@dataclass(frozen=True)
class AnalysisInvestigation:
    """Individual engineering analysis/investigation within the analysis artifact."""

    investigation_id: str
    title: str
    purpose: AnalysisPurpose
    question: str | None = None
    linked_requirement_ids: tuple[str, ...] = ()
    linked_component_ids: tuple[str, ...] = ()
    linked_test_plan_ids: tuple[str, ...] = ()
    linked_evidence_ids: tuple[str, ...] = ()
    lifecycle_stage: str = "INPUTS"
    verification_criterion: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": "1.0.0",
            "investigationId": self.investigation_id,
            "title": self.title,
            "purpose": self.purpose,
            "question": self.question,
            "linkedRequirementIds": list(self.linked_requirement_ids),
            "linkedComponentIds": list(self.linked_component_ids),
            "linkedTestPlanIds": list(self.linked_test_plan_ids),
            "linkedEvidenceIds": list(self.linked_evidence_ids),
            "lifecycleStage": self.lifecycle_stage,
            "verificationCriterion": self.verification_criterion,
            "stageVocabulary": list(ANALYSIS_STAGE_IDS),
        }


def new_investigation(
    *,
    title: str,
    purpose: AnalysisPurpose = "exploration",
    question: str | None = None,
    linked_requirement_ids: list[str] | None = None,
    lifecycle_stage: str = "INPUTS",
    verification_criterion: dict[str, Any] | None = None,
) -> AnalysisInvestigation:
    if lifecycle_stage not in ANALYSIS_STAGE_IDS:
        raise ValueError(f"Unknown analysis stage: {lifecycle_stage}")
    return AnalysisInvestigation(
        investigation_id=new_id("ainv"),
        title=title,
        purpose=purpose,
        question=question,
        linked_requirement_ids=tuple(linked_requirement_ids or ()),
        lifecycle_stage=lifecycle_stage,
        verification_criterion=verification_criterion,
    )


def validate_investigation_dict(raw: dict[str, Any]) -> None:
    if raw.get("schemaVersion") != "1.0.0":
        raise ValueError("investigation.schemaVersion must be 1.0.0")
    if not isinstance(raw.get("investigationId"), str) or not raw["investigationId"]:
        raise ValueError("investigationId is required")
    if not isinstance(raw.get("title"), str) or not raw["title"].strip():
        raise ValueError("title is required")
    if raw.get("purpose") not in {"exploration", "verification"}:
        raise ValueError("purpose must be exploration or verification")
    stage = raw.get("lifecycleStage", "INPUTS")
    if stage not in ANALYSIS_STAGE_IDS:
        raise ValueError(f"lifecycleStage must be one of {ANALYSIS_STAGE_IDS}")
    # Empty linkedRequirementIds is explicitly valid for exploration.


def assess_metric(
    *,
    metric_value: float | None,
    operator: ComparisonOperator,
    threshold: float,
) -> AssessmentResult:
    """Deterministic criterion assessment. LLM must never author this result."""
    if metric_value is None:
        return "INCONCLUSIVE"
    ops = {
        "<": metric_value < threshold,
        "<=": metric_value <= threshold,
        ">": metric_value > threshold,
        ">=": metric_value >= threshold,
        "==": metric_value == threshold,
        "!=": metric_value != threshold,
    }
    try:
        return "PASS" if ops[operator] else "FAIL"
    except KeyError as exc:
        raise ValueError(f"Unsupported operator: {operator}") from exc


def build_verification_summary(
    *,
    metric_id: str,
    metric_value: float,
    unit: str,
    requirement_id: str,
    operator: ComparisonOperator,
    threshold: float,
    execution_run_id: str | None = None,
    output_id: str | None = None,
) -> dict[str, Any]:
    assessment = assess_metric(
        metric_value=metric_value,
        operator=operator,
        threshold=threshold,
    )
    return {
        "schemaVersion": "1.0.0",
        "computedMetric": {
            "metricId": metric_id,
            "value": metric_value,
            "unit": unit,
            "executionRunId": execution_run_id,
            "outputId": output_id,
            "rmsNoiseDefinition": RMS_NOISE_DEFINITION,
        },
        "verificationCriterion": {
            "linkedRequirementId": requirement_id,
            "metricId": metric_id,
            "operator": operator,
            "threshold": threshold,
            "unit": unit,
        },
        "assessment": assessment,
        "authority": "deterministic-code",
        "notes": "LLM prose is never verification authority.",
    }


# Explore vs Verify product semantics (documentation constants; behavior unchanged).
EXPLORE_SEMANTICS = {
    "purpose": "fast iteration",
    "provisional": True,
    "evidenceEligible": False,
    "authoritativePassFail": False,
    "durableHistory": False,
    "mayUseEphemeralState": True,
}

VERIFY_SEMANTICS = {
    "purpose": "durable verification",
    "requiresSavedFilesystem": True,
    "immutableSnapshot": True,
    "durableExecutionRun": True,
    "durableOutputs": True,
    "historyVisible": True,
    "reproducible": True,
    "evidenceEligible": True,
    "deterministicAssessment": True,
}

HISTORICAL_RERUN_SEMANTICS = {
    "executesExactHistoricalSnapshot": True,
    "usesCurrentMutableFiles": False,
    "durableExecutionProvenance": True,
}
