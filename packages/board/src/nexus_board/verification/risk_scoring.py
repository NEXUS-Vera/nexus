"""Deterministic risk priority scoring (Phase 17D)."""

from __future__ import annotations

from typing import Any

SEVERITY_SCORES = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

LIKELIHOOD_SCORES = {
    "rare": 1,
    "unlikely": 2,
    "possible": 3,
    "likely": 4,
}

RISK_CATEGORIES = frozenset(
    {
        "electrical",
        "firmware",
        "communication",
        "power",
        "thermal",
        "mechanical",
        "integration",
        "performance",
        "data-quality",
        "safety",
    }
)

RISK_STATUSES = frozenset({"open", "mitigating", "mitigated", "accepted", "monitoring"})


def compute_risk_priority(*, severity: str, likelihood: str) -> int:
    """Transparent engineering prioritization: severityScore × likelihoodScore."""

    s = SEVERITY_SCORES.get(severity)
    l = LIKELIHOOD_SCORES.get(likelihood)
    if s is None or l is None:
        raise ValueError(f"Invalid severity/likelihood: {severity!r}/{likelihood!r}")
    return s * l


def compute_risk_register_summary(risks: list[dict[str, Any]]) -> dict[str, int]:
    total = len(risks)
    open_risks = 0
    high_or_critical = 0
    mitigated = 0
    unverified = 0
    for risk in risks:
        if not isinstance(risk, dict):
            continue
        status = str(risk.get("status") or "open")
        severity = str(risk.get("severity") or "")
        if status in {"open", "mitigating", "monitoring"}:
            open_risks += 1
        if severity in {"high", "critical"}:
            high_or_critical += 1
        if status == "mitigated":
            mitigated += 1
        else:
            verification = risk.get("verificationTestIds") or []
            if verification and status != "accepted":
                unverified += 1
            elif not verification and status in {"open", "mitigating", "monitoring"}:
                unverified += 1
    return {
        "totalRisks": total,
        "openRisks": open_risks,
        "highOrCritical": high_or_critical,
        "mitigated": mitigated,
        "unverifiedMitigations": unverified,
    }
