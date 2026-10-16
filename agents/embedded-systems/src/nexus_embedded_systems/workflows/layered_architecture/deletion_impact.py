"""Functional-node deletion impact for Layered Architecture workflows."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def inspect_functional_node_deletion_impact(
    *,
    node_id: str,
    functional_content: dict[str, Any],
    component_plan_content: dict[str, Any] | None,
    electrical_content: dict[str, Any] | None,
    physical_content: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return structured impact of deleting a functional architecture node."""
    affected_role_ids: list[str] = []
    if isinstance(component_plan_content, dict):
        for role in component_plan_content.get("componentRoles") or []:
            if not isinstance(role, dict):
                continue
            arch_ids = role.get("architectureNodeIds") or []
            if node_id in arch_ids:
                role_id = role.get("componentRoleId")
                if isinstance(role_id, str) and role_id:
                    affected_role_ids.append(role_id)
    affected_role_ids = sorted(set(affected_role_ids))

    affected_electrical_node_ids: list[str] = []
    if isinstance(electrical_content, dict):
        for enode in electrical_content.get("nodes") or []:
            if not isinstance(enode, dict):
                continue
            fa_ids = enode.get("functionalArchitectureNodeIds") or []
            role_ids = enode.get("componentRoleIds") or []
            if node_id in fa_ids or any(r in affected_role_ids for r in role_ids):
                eid = enode.get("nodeId")
                if isinstance(eid, str) and eid:
                    affected_electrical_node_ids.append(eid)
    affected_electrical_node_ids = sorted(set(affected_electrical_node_ids))

    affected_electrical_connection_ids: list[str] = []
    if isinstance(electrical_content, dict):
        affected_set = set(affected_electrical_node_ids)
        for conn in electrical_content.get("connections") or []:
            if not isinstance(conn, dict):
                continue
            if conn.get("fromNodeId") in affected_set or conn.get("toNodeId") in affected_set:
                cid = conn.get("connectionId")
                if isinstance(cid, str) and cid:
                    affected_electrical_connection_ids.append(cid)
    affected_electrical_connection_ids = sorted(set(affected_electrical_connection_ids))

    affected_physical_node_ids: list[str] = []
    if isinstance(physical_content, dict):
        electrical_set = set(affected_electrical_node_ids)
        for pnode in physical_content.get("nodes") or []:
            if not isinstance(pnode, dict):
                continue
            eids = pnode.get("electricalNodeIds") or []
            if any(eid in electrical_set for eid in eids):
                pid = pnode.get("nodeId")
                if isinstance(pid, str) and pid:
                    affected_physical_node_ids.append(pid)
    affected_physical_node_ids = sorted(set(affected_physical_node_ids))

    affected_physical_relationship_ids: list[str] = []
    if isinstance(physical_content, dict):
        physical_set = set(affected_physical_node_ids)
        for rel in physical_content.get("relationships") or []:
            if not isinstance(rel, dict):
                continue
            if rel.get("fromNodeId") in physical_set or rel.get("toNodeId") in physical_set:
                rid = rel.get("relationshipId")
                if isinstance(rid, str) and rid:
                    affected_physical_relationship_ids.append(rid)
    affected_physical_relationship_ids = sorted(set(affected_physical_relationship_ids))

    affected_requirement_ids: list[str] = []
    for node in functional_content.get("nodes") or []:
        if not isinstance(node, dict) or node.get("nodeId") != node_id:
            continue
        for req_id in node.get("satisfiesRequirementIds") or []:
            if isinstance(req_id, str) and req_id:
                affected_requirement_ids.append(req_id)
    affected_requirement_ids = sorted(set(affected_requirement_ids))

    blocking = bool(
        affected_role_ids
        or affected_electrical_node_ids
        or affected_electrical_connection_ids
        or affected_physical_node_ids
        or affected_physical_relationship_ids
    )
    parts: list[str] = []
    if affected_role_ids:
        parts.append(f"{len(affected_role_ids)} component role(s)")
    if affected_electrical_node_ids:
        parts.append(f"{len(affected_electrical_node_ids)} electrical node(s)")
    if affected_physical_node_ids:
        parts.append(f"{len(affected_physical_node_ids)} physical node(s)")
    if affected_requirement_ids:
        parts.append(f"{len(affected_requirement_ids)} requirement link(s)")
    if parts:
        summary = f"Deleting functional node {node_id} affects " + ", ".join(parts) + "."
    else:
        summary = f"Deleting functional node {node_id} has no downstream dependents."

    return {
        "schemaVersion": "1.0.0",
        "targetEntityType": "functional-node",
        "targetEntityId": node_id,
        "blocking": blocking,
        "affectedComponentRoleIds": affected_role_ids,
        "affectedElectricalNodeIds": affected_electrical_node_ids,
        "affectedElectricalConnectionIds": affected_electrical_connection_ids,
        "affectedPhysicalNodeIds": affected_physical_node_ids,
        "affectedPhysicalRelationshipIds": affected_physical_relationship_ids,
        "affectedRequirementIds": affected_requirement_ids,
        "summary": summary,
    }


def apply_functional_node_removal(
    content: dict[str, Any],
    node_id: str,
) -> dict[str, Any]:
    """Remove a functional node, incident edges, and refresh requirementCoverage.

    Downstream reconciliation stays in existing regenerate/impact machinery when
    a revision is accepted / via the project modification path. Draft-only
    ``remove-and-reconcile`` may call this helper before accept.
    """
    result = deepcopy(content)
    nodes = [n for n in (result.get("nodes") or []) if isinstance(n, dict)]
    remaining_nodes = [n for n in nodes if n.get("nodeId") != node_id]
    result["nodes"] = remaining_nodes

    edges = [e for e in (result.get("edges") or []) if isinstance(e, dict)]
    result["edges"] = [
        e for e in edges if e.get("fromNodeId") != node_id and e.get("toNodeId") != node_id
    ]

    covered: list[str] = []
    for node in remaining_nodes:
        for req_id in node.get("satisfiesRequirementIds") or []:
            if isinstance(req_id, str) and req_id:
                covered.append(req_id)
    unique_covered = sorted(set(covered))
    if unique_covered:
        result["requirementCoverage"] = {"coveredRequirementIds": unique_covered}
    elif "requirementCoverage" in result:
        result["requirementCoverage"] = {"coveredRequirementIds": []}

    return result
