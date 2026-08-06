"""Derive component roles from functional architecture nodes."""

from __future__ import annotations

from typing import Any

from nexus_embedded_systems.workflows.project_initialization.ids import new_id

# Nodes whose names/responsibilities imply a physical implementable role.
_SENSING_HINTS = (
    "sense",
    "sensing",
    "sensor",
    "measure",
    "measurement",
    "acquire",
    "acquisition",
    "detect",
    "detection",
    "tremor",
    "vibration",
    "obstacle",
    "temperature",
    "humidity",
    "moisture",
    "light",
    "air-quality",
    "air quality",
)

_COMPUTE_HINTS = ("process", "processing", "compute", "control", "controller", "mcu")
_POWER_HINTS = ("power", "battery", "energy")
_COMM_HINTS = ("comm", "communication", "radio", "transmit", "report", "connectivity")
_STORAGE_HINTS = ("stor", "log", "record", "memory")


def derive_roles_from_architecture(
    architecture_content: dict[str, Any],
    *,
    source: str = "inferred",
) -> list[dict[str, Any]]:
    """Create one component role per architecture node that needs physical realization.

    Prefers sensing/acquisition nodes; if none match, falls back to the first
    non-boundary node so every architecture yields at least one role.
    """

    nodes = [n for n in (architecture_content.get("nodes") or []) if isinstance(n, dict)]
    roles: list[dict[str, Any]] = []
    for index, node in enumerate(nodes, start=1):
        category = _infer_category(node)
        if category is None:
            continue
        node_id = node.get("nodeId")
        if not isinstance(node_id, str):
            continue
        name = str(node.get("name") or "Component role")
        req_ids = [
            rid for rid in (node.get("satisfiesRequirementIds") or []) if isinstance(rid, str)
        ]
        roles.append(
            {
                "componentRoleId": new_id("role_"),
                "displayId": f"CR{index}",
                "name": f"{name} role",
                "category": category,
                "description": _role_description(node, category),
                "architectureNodeIds": [node_id],
                "requirementIds": req_ids[:8],
                "requiredCapabilities": ["implementation-pending"],
                "status": "identified",
                "priority": "high" if category == "sensor" else "medium",
                "source": source,
                "rationale": (
                    "Derived from functional architecture node that requires "
                    "physical implementation."
                ),
            }
        )

    if roles:
        # Prefer sensor roles for Phase 12 minimum plans; keep compute if no sensors.
        sensor_roles = [r for r in roles if r["category"] == "sensor"]
        if sensor_roles:
            return _renumber(sensor_roles[:3])
        return _renumber(roles[:2])

    # Fallback: first node with any requirement coverage.
    for node in nodes:
        node_id = node.get("nodeId")
        if not isinstance(node_id, str):
            continue
        req_ids = [
            rid for rid in (node.get("satisfiesRequirementIds") or []) if isinstance(rid, str)
        ]
        return [
            {
                "componentRoleId": new_id("role_"),
                "displayId": "CR1",
                "name": f"{node.get('name', 'Primary')} role",
                "category": "compute",
                "description": "Primary implementable role derived from architecture.",
                "architectureNodeIds": [node_id],
                "requirementIds": req_ids[:8],
                "requiredCapabilities": ["implementation-pending"],
                "status": "identified",
                "priority": "high",
                "source": source,
                "rationale": "Fallback role so component planning can begin.",
            }
        ]
    return []


def _renumber(roles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for index, role in enumerate(roles, start=1):
        updated = dict(role)
        updated["displayId"] = f"CR{index}"
        out.append(updated)
    return out


def _infer_category(node: dict[str, Any]) -> str | None:
    blob = _node_blob(node)
    if any(h in blob for h in _SENSING_HINTS):
        return "sensor"
    if any(h in blob for h in _COMPUTE_HINTS):
        return "compute"
    if any(h in blob for h in _POWER_HINTS):
        return "power"
    if any(h in blob for h in _COMM_HINTS):
        return "communication"
    if any(h in blob for h in _STORAGE_HINTS):
        return "storage"
    return None


def _node_blob(node: dict[str, Any]) -> str:
    parts = [
        str(node.get("name") or ""),
        str(node.get("description") or ""),
        " ".join(str(r) for r in (node.get("responsibilities") or [])),
    ]
    return " ".join(parts).casefold()


def _role_description(node: dict[str, Any], category: str) -> str:
    name = str(node.get("name") or "architecture node")
    if category == "sensor":
        return f"Provide physical sensing for: {name}."
    if category == "compute":
        return f"Provide compute/control for: {name}."
    if category == "power":
        return f"Provide power delivery for: {name}."
    if category == "communication":
        return f"Provide communication for: {name}."
    if category == "storage":
        return f"Provide storage for: {name}."
    return f"Implement physical capabilities for: {name}."
