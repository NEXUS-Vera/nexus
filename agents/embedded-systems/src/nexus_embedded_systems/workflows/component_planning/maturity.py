"""Maturity calculator for Component Plan content."""

from __future__ import annotations

from typing import Any


def compute_maturity(content: dict[str, Any]) -> str:
    roles = [r for r in (content.get("componentRoles") or []) if isinstance(r, dict)]
    candidates = [c for c in (content.get("candidates") or []) if isinstance(c, dict)]
    selections = [s for s in (content.get("selectionDecisions") or []) if isinstance(s, dict)]
    checks = [c for c in (content.get("compatibilityChecks") or []) if isinstance(c, dict)]

    if not roles:
        return "roles-defined"
    if any(s.get("selectionState") == "approved" for s in selections):
        if checks and all(c.get("status") in {"pass", "unknown"} for c in checks):
            return "selection-approved"
        return "selection-approved"
    if any(s.get("selectionState") in {"proposed", "awaiting-user"} for s in selections):
        return "selection-proposed"
    if checks:
        return "compatibility-checked"
    if candidates and any(c.get("evidenceStatus") == "grounded" for c in candidates):
        return "candidates-grounded"
    if candidates:
        return "candidates-proposed"
    return "roles-defined"
