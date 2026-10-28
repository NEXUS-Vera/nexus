"""Derive component roles from functional architecture nodes."""

from __future__ import annotations

from typing import Any

from nexus_embedded_systems.workflows.project_initialization.ids import new_id

# Primary deterministic mapping from Functional Architecture functionalType →
# ComponentCategory. Responsibilities/name may refine only when type is absent
# or ambiguous (input/output/external-system/analysis).
_FUNCTIONAL_TYPE_TO_CATEGORY: dict[str, str | None] = {
    "sensing": "sensor",
    "processing": "compute",
    "control": "compute",
    "storage": "storage",
    "communication": "communication",
    "power": "power",
    "actuation": "actuation",
    "user-interface": "interface",
    "analysis": "compute",
    "input": None,  # refined by text or skipped with explicit reason
    "output": None,
    "external-system": None,  # intentionally no hardware role by default
}

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
)
_COMPUTE_HINTS = ("process", "processing", "compute", "control", "controller", "mcu")
_POWER_HINTS = ("power", "battery", "energy")
_COMM_HINTS = ("comm", "communication", "radio", "transmit", "report", "connectivity")
_STORAGE_HINTS = ("stor", "log", "record", "memory")
_ACTUATION_HINTS = ("actuat", "motor", "drive", "servo")
_INTERFACE_HINTS = ("user-interface", "ui", "display", "button", "hmi")

# Nodes that intentionally receive no hardware Component Role.
_NO_ROLE_FUNCTIONAL_TYPES = frozenset({"external-system"})


def derive_roles_from_architecture(
    architecture_content: dict[str, Any],
    *,
    source: str = "inferred",
) -> list[dict[str, Any]]:
    """Create component roles for architecture nodes that need physical realization.

    Uses ``functionalType`` as the primary category signal. Every relevant node is
    either covered by a role or recorded in ``coverageNotes``-style rationale on
    skipped nodes via returned metadata on the role list (see
    ``derive_roles_with_coverage``).
    """

    roles, _skipped = derive_roles_with_coverage(architecture_content, source=source)
    return roles


def derive_roles_with_coverage(
    architecture_content: dict[str, Any],
    *,
    source: str = "inferred",
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Return roles plus explicit skip records for uncovered FA nodes.

    Each skip record: ``{nodeId, reason}``.
    """

    nodes = [n for n in (architecture_content.get("nodes") or []) if isinstance(n, dict)]
    roles: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    for index, node in enumerate(nodes, start=1):
        node_id = node.get("nodeId")
        if not isinstance(node_id, str):
            continue
        category, skip_reason = _resolve_category(node, architecture_content)
        if category is None:
            skipped.append(
                {
                    "nodeId": node_id,
                    "reason": skip_reason
                    or "Functional node intentionally has no hardware Component Role.",
                }
            )
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
                "status": "ready-for-candidates",
                "priority": "high" if category == "sensor" else "medium",
                "source": source,
                "rationale": (
                    "Derived from functional architecture node "
                    f"({node.get('functionalType') or 'untyped'}) that requires "
                    "physical implementation."
                ),
            }
        )

    if roles:
        return _renumber(roles), skipped

    # Fallback: first node with any requirement coverage.
    for node in nodes:
        node_id = node.get("nodeId")
        if not isinstance(node_id, str):
            continue
        req_ids = [
            rid for rid in (node.get("satisfiesRequirementIds") or []) if isinstance(rid, str)
        ]
        return (
            [
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
            ],
            [s for s in skipped if s.get("nodeId") != node_id],
        )
    return [], skipped


def _renumber(roles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for index, role in enumerate(roles, start=1):
        updated = dict(role)
        updated["displayId"] = f"CR{index}"
        out.append(updated)
    return out


def is_i2c_bus(node: dict[str, Any], architecture: dict[str, Any] | None) -> bool:
    """Recognize explicit buses or I2C transports adjoining compute and sensing."""
    if node.get("functionalType") != "communication":
        return False
    name = str(node.get("name") or "").casefold()
    if "i2c" in name and "bus" in name:
        return True
    text = " ".join(
        str(node.get(key) or "") for key in ("name", "responsibilities", "interfaces")
    ).casefold()
    if "i2c" not in text:
        return False
    node_id = node.get("nodeId")
    if not isinstance(node_id, str):
        return False
    neighbors = {
        endpoint
        for edge in ((architecture or {}).get("edges") or [])
        if isinstance(edge, dict)
        and edge.get("flowType") in {"data", "control"}
        and node_id in (edge.get("fromNodeId"), edge.get("toNodeId"))
        for endpoint in (edge.get("fromNodeId"), edge.get("toNodeId"))
        if isinstance(endpoint, str) and endpoint != node_id
    }
    categories = {
        _resolve_category(neighbor, {})[0]
        for neighbor in ((architecture or {}).get("nodes") or [])
        if isinstance(neighbor, dict)
        and neighbor.get("nodeId") in neighbors
        and neighbor.get("functionalType") != "communication"
    }
    return {"compute", "sensor"}.issubset(categories)


def _resolve_category(
    node: dict[str, Any], architecture: dict[str, Any]
) -> tuple[str | None, str | None]:
    """Return (category, skip_reason). Category None means no hardware role."""

    if is_i2c_bus(node, architecture):
        return None, "I2C transport is realized as an electrical connection between hardware roles."

    functional_type = node.get("functionalType")
    if isinstance(functional_type, str):
        if functional_type in _NO_ROLE_FUNCTIONAL_TYPES:
            return None, (
                f"functionalType '{functional_type}' is external and does not "
                "require an in-system hardware Component Role."
            )
        mapped = _FUNCTIONAL_TYPE_TO_CATEGORY.get(functional_type)
        if mapped is not None:
            return mapped, None
        # Ambiguous typed nodes: allow text refinement.
        refined = _infer_category_from_text(node)
        if refined is not None:
            return refined, None
        if functional_type in {"input", "output"}:
            return None, (
                f"functionalType '{functional_type}' has no hardware Component Role; "
                "responsibilities did not refine to an implementable category."
            )
        # Unknown functionalType string — fall through to text.
    refined = _infer_category_from_text(node)
    if refined is not None:
        return refined, None
    return None, (
        "No Component Role: missing/unmapped functionalType and responsibilities "
        "did not match an implementable category."
    )


def _infer_category_from_text(node: dict[str, Any]) -> str | None:
    """Secondary classifier from name/responsibilities when functionalType is absent."""

    blob = _node_blob(node)
    if any(h in blob for h in _SENSING_HINTS):
        return "sensor"
    if any(h in blob for h in _ACTUATION_HINTS):
        return "actuation"
    if any(h in blob for h in _COMPUTE_HINTS):
        return "compute"
    if any(h in blob for h in _POWER_HINTS):
        return "power"
    if any(h in blob for h in _COMM_HINTS):
        return "communication"
    if any(h in blob for h in _STORAGE_HINTS):
        return "storage"
    if any(h in blob for h in _INTERFACE_HINTS):
        return "interface"
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
    if category == "actuation":
        return f"Provide actuation for: {name}."
    if category == "interface":
        return f"Provide user/system interface hardware for: {name}."
    return f"Implement physical capabilities for: {name}."
