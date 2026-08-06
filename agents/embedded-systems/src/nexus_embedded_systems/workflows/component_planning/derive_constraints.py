"""Derive selection constraints from requirements."""

from __future__ import annotations

from typing import Any

from nexus_embedded_systems.workflows.project_initialization.ids import new_id

_ACCURACY = ("accur", "tolerance", "error bound", "±", "+/-")
_RANGE = ("range", "from", "to", "between", "celsius", "°c", "humidity")
_SAMPLE = ("sampl", "hz", "hertz", "rate")
_BUDGET = ("budget", "cost", "bom", "price", "$")
_INTERFACE = ("i2c", "spi", "uart", "ble", "wifi", "mqtt", "interface")
_POWER = ("voltage", "current", "battery", "power", "mA", "volt")


def derive_constraints_from_requirements(
    *,
    roles: list[dict[str, Any]],
    requirements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Map requirement statements onto selection constraints for matching roles."""

    constraints: list[dict[str, Any]] = []
    active_reqs = [
        r
        for r in requirements
        if isinstance(r, dict) and r.get("confirmationStatus") != "rejected"
    ]
    for role in roles:
        role_id = role.get("componentRoleId")
        if not isinstance(role_id, str):
            continue
        role_req_ids = set(role.get("requirementIds") or [])
        arch_ids = [i for i in (role.get("architectureNodeIds") or []) if isinstance(i, str)]
        matched = [
            r
            for r in active_reqs
            if r.get("requirementId") in role_req_ids
            or _requirement_matches_role(r, role)
        ]
        for req in matched[:3]:
            constraint_type, operator, unit = _map_constraint(req)
            statement = str(req.get("statement") or "")
            constraints.append(
                {
                    "constraintId": new_id("cstr_"),
                    "componentRoleId": role_id,
                    "constraintType": constraint_type,
                    "operator": operator,
                    "targetValue": {"kind": "unknown"},
                    "unit": unit,
                    "sourceRequirementIds": [req["requirementId"]],
                    "sourceArchitectureNodeIds": arch_ids,
                    "importance": "required",
                    "confirmationStatus": (
                        "confirmed"
                        if req.get("confirmationStatus") == "confirmed"
                        else "unknown"
                    ),
                    "rationale": f"Derived from requirement: {statement[:160]}",
                }
            )
    return constraints


def _requirement_matches_role(req: dict[str, Any], role: dict[str, Any]) -> bool:
    statement = str(req.get("statement") or "").casefold()
    category = str(role.get("category") or "")
    name = str(role.get("name") or "").casefold()
    if category == "sensor":
        return any(
            token in statement or token in name
            for token in ("measure", "sense", "sensor", "temperature", "humidity", "motion")
        )
    if category == "compute":
        return any(token in statement for token in ("process", "control", "compute"))
    if category == "power":
        return any(token in statement for token in ("power", "battery", "runtime"))
    if category == "communication":
        return any(token in statement for token in ("wifi", "ble", "mqtt", "report", "transmit"))
    return False


def _map_constraint(req: dict[str, Any]) -> tuple[str, str, str | None]:
    statement = str(req.get("statement") or "").casefold()
    category = str(req.get("category") or "").casefold()
    if any(t in statement for t in _ACCURACY) or category == "performance":
        if any(t in statement for t in _ACCURACY):
            return "accuracy", "unknown", None
    if any(t in statement for t in _SAMPLE):
        return "sample-rate", "unknown", "Hz"
    if any(t in statement for t in _BUDGET) or category == "project-constraint":
        return "cost", "unknown", "USD"
    if any(t in statement for t in _INTERFACE) or category == "interface":
        return "interface", "unknown", None
    if any(t in statement for t in _POWER) or category in {"resource"}:
        return "active-current", "unknown", "mA"
    if any(t in statement for t in _RANGE):
        return "measurement-range", "unknown", None
    return "measurement-range", "unknown", None
