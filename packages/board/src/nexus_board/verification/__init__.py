"""Phase 17 VERIFY — deterministic test assessment, coverage, and risk scoring."""

from __future__ import annotations

from nexus_board.verification.assessment import (
    AssessmentResult,
    evaluate_criterion,
)
from nexus_board.verification.coverage import (
    RequirementVerificationState,
    compute_requirement_coverage,
    compute_test_plan_coverage_summary,
)
from nexus_board.verification.evidence import (
    ResolvedEvidence,
    resolve_analysis_metric_evidence,
    resolve_existence_evidence,
    resolve_marker_evidence,
    resolve_structural_mapping_evidence,
)
from nexus_board.verification.risk_scoring import (
    LIKELIHOOD_SCORES,
    SEVERITY_SCORES,
    compute_risk_priority,
    compute_risk_register_summary,
)
from nexus_board.verification.fixture_test_plan import (
    build_golden_vibration_test_plan_content,
)
from nexus_board.verification.close import (
    annotate_risk_mitigation_verification,
    apply_analysis_summary_to_test_plan,
    promote_analysis_evidence_into_test_plan,
    promote_marker_evidence_into_test_plan,
    promote_structural_evidence_into_test_plan,
    stable_evidence_id,
)
from nexus_board.verification.fixture_risk_register import (
    build_golden_vibration_risk_register_content,
)

__all__ = [
    "AssessmentResult",
    "LIKELIHOOD_SCORES",
    "SEVERITY_SCORES",
    "RequirementVerificationState",
    "ResolvedEvidence",
    "annotate_risk_mitigation_verification",
    "apply_analysis_summary_to_test_plan",
    "promote_analysis_evidence_into_test_plan",
    "promote_marker_evidence_into_test_plan",
    "promote_structural_evidence_into_test_plan",
    "stable_evidence_id",
    "build_golden_vibration_risk_register_content",
    "build_golden_vibration_test_plan_content",
    "compute_requirement_coverage",
    "compute_risk_priority",
    "compute_risk_register_summary",
    "compute_test_plan_coverage_summary",
    "evaluate_criterion",
    "resolve_analysis_metric_evidence",
    "resolve_existence_evidence",
    "resolve_marker_evidence",
    "resolve_structural_mapping_evidence",
]
