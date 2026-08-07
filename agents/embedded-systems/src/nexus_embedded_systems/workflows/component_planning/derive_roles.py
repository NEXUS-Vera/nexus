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

_CATEGORY_PRIORITY = ("sensor", "compute", "power", "communication", "storage")
_MAX_ROLES = 6
_MAX_PER_CATEGORY = 2


def derive_roles_from_architecture(
    architecture_content: dict[str, Any],
    *,
    source: str = "inferred",
) -> list[dict[str, Any]]:
    """Create component roles for architecture nodes that need physical realization.

    Returns a diversified set across sensor/compute/power/communication/storage so
    the Component Plan is useful immediately after initialization.
    """

    nodes = [n for n in (architecture_content.get("nodes") or []) if isinstance(n, dict)]
    by_category: dict[str, list[dict[str, Any]]] = {c: [] for c in _CATEGORY_PRIORITY}
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
        role = {
            "componentRoleId": new_id("role_"),
            "displayId": f"CR{index}",
            "name": f"{name} role",
            "category": category,
            "description": _role_description(node, category),
            "architectureNodeIds": [node_id],
            "requirementIds": req_ids[:8],
            "requiredCapabilities": ["implementation-pending"],
            "status": "ready-for-candidates",
            "priority": "high" if category == "sensor" else "medium",
            "source": source,
            "rationale": (
                "Derived from functional architecture node that requires physical implementation."
            ),
        }
        by_category.setdefault(category, []).append(role)

    roles: list[dict[str, Any]] = []
    for category in _CATEGORY_PRIORITY:
        for role in by_category.get(category, [])[:_MAX_PER_CATEGORY]:
            roles.append(role)
            if len(roles) >= _MAX_ROLES:
                break
        if len(roles) >= _MAX_ROLES:
            break

    if roles:
        return _renumber(roles)

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
                "status": "ready-for-candidates",
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
