"""Evidence resolvers for supported VERIFY sources (Phase 17C).

Reuse ProducedOutput / ExecutionRun / artifact inspection — no second Evidence DB.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ResolvedEvidence:
    source: str
    actual: Any = None
    present: bool | None = None
    detail: str | None = None
    execution_run_id: str | None = None
    output_id: str | None = None
    output_name: str | None = None
    evidence_status: str = "unverified"


def resolve_analysis_metric_evidence(
    *,
    summary: dict[str, Any] | None,
    metric_id: str,
    execution_run_id: str | None = None,
    output_id: str | None = None,
    output_name: str | None = "summary.json",
) -> ResolvedEvidence:
    if not isinstance(summary, dict):
        return ResolvedEvidence(
            source="analysis",
            present=False,
            detail=f"Expected metric {metric_id} was not produced.",
            execution_run_id=execution_run_id,
            output_id=output_id,
            output_name=output_name,
        )
    value = summary.get(metric_id)
    if value is None and metric_id == "accel_x_rms_noise_g":
        value = summary.get("metricValue")
    return ResolvedEvidence(
        source="analysis",
        actual=value,
        present=value is not None,
        detail=None if value is not None else f"Expected metric {metric_id} was not produced.",
        execution_run_id=execution_run_id,
        output_id=output_id,
        output_name=output_name,
        evidence_status="calculated" if value is not None else "unverified",
    )


def resolve_existence_evidence(
    *,
    produced_output_names: list[str],
    required_names: list[str],
    execution_run_id: str | None = None,
) -> ResolvedEvidence:
    missing = [name for name in required_names if not any(name in n for n in produced_output_names)]
    ok = not missing
    return ResolvedEvidence(
        source="produced-output",
        actual=",".join(produced_output_names),
        present=ok,
        detail="all required outputs present" if ok else f"missing: {', '.join(missing)}",
        execution_run_id=execution_run_id,
        evidence_status="grounded" if ok else "unverified",
    )


def resolve_marker_evidence(
    *,
    log_text: str | None,
    marker: str,
    execution_run_id: str | None = None,
) -> ResolvedEvidence:
    if log_text is None:
        return ResolvedEvidence(
            source="execution-log",
            present=False,
            detail=f"Marker {marker!r} not observed (no log).",
            execution_run_id=execution_run_id,
        )
    found = marker in log_text
    return ResolvedEvidence(
        source="execution-log",
        actual=log_text if found else None,
        present=found,
        detail=f"marker {marker!r} {'found' if found else 'missing'}",
        execution_run_id=execution_run_id,
        evidence_status="tested" if found else "unverified",
    )


def resolve_structural_mapping_evidence(
    *,
    signal: str,
    observed_mapping: str | None,
    expected_mapping: str,
) -> ResolvedEvidence:
    if observed_mapping is None:
        return ResolvedEvidence(
            source="structural-inspection",
            present=False,
            detail=f"{signal} mapping not available.",
        )
    return ResolvedEvidence(
        source="structural-inspection",
        actual=observed_mapping,
        present=True,
        detail=f"{signal} → {observed_mapping} (expected {expected_mapping})",
        evidence_status="grounded",
    )
