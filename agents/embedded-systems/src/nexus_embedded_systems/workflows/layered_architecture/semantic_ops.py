"""Electrical / Physical Architecture semantic draft operations (Phase 13A)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from nexus_embedded_systems.workflows.project_initialization.ids import new_id


def apply_electrical_semantic_op(content: dict[str, Any], op: dict[str, Any]) -> dict[str, Any]:
    """Apply a draft-only Electrical semantic operation. Does not touch Component Plan."""

    next_content = deepcopy(content)
    nodes = list(next_content.get("nodes") or [])
    connections = list(next_content.get("connections") or [])
    op_type = op.get("type")

    if op_type == "add-supporting-node":
        node = {
            "nodeId": new_id("enode_"),
            "name": str(op.get("name") or "Supporting electronics"),
            "nodeType": op.get("nodeType") or "supporting-electronics",
            "functionalArchitectureNodeIds": [],
            "componentRoleIds": [],
            "implementationStatus": "unresolved",
            "evidenceStatus": "unverified",
            "selectionState": "none",
            "interfaces": [
                {
                    "interfaceId": new_id("eiface_"),
                    "interfaceType": "unknown",
                    "direction": "unknown",
                    "status": "unresolved",
                    "label": "unimplemented",
                    "provenance": {
                        "schemaVersion": "1.0.0",
                        "sourceType": "user",
                        "notes": "User-authored supporting Electrical node.",
                    },
                }
            ],
            "requirementIds": [],
            "notes": "User-authored supporting node; not a Component selection.",
        }
        nodes.append(node)
    elif op_type == "delete-supporting-node":
        node_id = op.get("nodeId")
        target = next((n for n in nodes if n.get("nodeId") == node_id), None)
        if target is None:
            return content
        # Only allow deleting nodes without component role binding (supporting).
        if target.get("componentRoleIds"):
            raise ValueError(
                "Cannot delete Electrical implementation bound to a Component Role; "
                "change selection in Component Plan instead."
            )
        nodes = [n for n in nodes if n.get("nodeId") != node_id]
        connections = [
            c
            for c in connections
            if c.get("fromNodeId") != node_id and c.get("toNodeId") != node_id
        ]
        for domain in next_content.get("powerDomains") or []:
            domain["memberNodeIds"] = [
                member for member in domain.get("memberNodeIds") or [] if member != node_id
            ]
    elif op_type == "add-connection":
        connections.append(
            {
                "connectionId": new_id("econn_"),
                "fromNodeId": op["fromNodeId"],
                "toNodeId": op["toNodeId"],
                "connectionType": op.get("connectionType") or "signal",
                "interfaceType": op.get("interfaceType") or "unknown",
                "status": op.get("status") or "needs-resolution",
                "description": op.get("description") or "User-authored Electrical connection",
                "provisionalReason": "User-proposed; verify interface compatibility.",
                "provenance": {
                    "schemaVersion": "1.0.0",
                    "sourceType": "user",
                },
            }
        )
    elif op_type == "delete-connection":
        conn_id = op.get("connectionId")
        connections = [c for c in connections if c.get("connectionId") != conn_id]
    elif op_type == "change-connection":
        conn_id = op.get("connectionId")
        for conn in connections:
            if conn.get("connectionId") != conn_id:
                continue
            if "connectionType" in op:
                conn["connectionType"] = op["connectionType"]
            if "interfaceType" in op:
                conn["interfaceType"] = op["interfaceType"]
            if "status" in op:
                conn["status"] = op["status"]
            conn["provenance"] = {
                "schemaVersion": "1.0.0",
                "sourceType": "user",
                "notes": "User edited connection semantics.",
            }
    elif op_type == "mark-connection-status":
        conn_id = op.get("connectionId")
        status = op.get("status")
        for conn in connections:
            if conn.get("connectionId") == conn_id and status:
                conn["status"] = status
    else:
        raise ValueError(f"Unknown Electrical semantic op: {op_type}")

    next_content["nodes"] = nodes
    next_content["connections"] = connections
    coverage = dict(next_content.get("coverageSummary") or {})
    coverage["unresolvedConnectionCount"] = sum(
        1 for c in connections if c.get("status") in {"unresolved", "needs-resolution", "unknown"}
    )
    next_content["coverageSummary"] = coverage
    return next_content


def apply_physical_semantic_op(content: dict[str, Any], op: dict[str, Any]) -> dict[str, Any]:
    """Apply a draft-only Physical semantic operation."""

    next_content = deepcopy(content)
    nodes = list(next_content.get("nodes") or [])
    zones = list(next_content.get("zones") or [])
    relationships = list(next_content.get("relationships") or [])
    op_type = op.get("type")

    if op_type == "add-entity":
        nodes.append(
            {
                "nodeId": new_id("pnode_"),
                "name": str(op.get("name") or "Physical entity"),
                "nodeType": op.get("nodeType") or "module",
                "electricalNodeIds": list(op.get("electricalNodeIds") or []),
                "placementStatus": op.get("placementStatus") or "unresolved",
                "zoneId": op.get("zoneId"),
                "qualitativePlacement": op.get("qualitativePlacement") or "Placement unresolved.",
                "constraints": list(op.get("constraints") or []),
                "provenance": {"schemaVersion": "1.0.0", "sourceType": "user"},
            }
        )
    elif op_type == "delete-entity":
        node_id = op.get("nodeId")
        nodes = [n for n in nodes if n.get("nodeId") != node_id]
        relationships = [
            r
            for r in relationships
            if r.get("fromNodeId") != node_id and r.get("toNodeId") != node_id
        ]
        for zone in zones:
            members = [m for m in (zone.get("memberNodeIds") or []) if m != node_id]
            zone["memberNodeIds"] = members
    elif op_type == "add-zone":
        zones.append(
            {
                "zoneId": new_id("pzone_"),
                "name": str(op.get("name") or "Zone"),
                "zoneKind": op.get("zoneKind") or "other",
                "memberNodeIds": [],
                "notes": op.get("notes") or "User-authored zone.",
            }
        )
    elif op_type == "delete-zone":
        zone_id = op.get("zoneId")
        zones = [z for z in zones if z.get("zoneId") != zone_id]
        for node in nodes:
            if node.get("zoneId") == zone_id:
                node["zoneId"] = None
                node["placementStatus"] = "unresolved"
                node["qualitativePlacement"] = "Zone removed; placement unresolved."
    elif op_type == "assign-zone":
        node_id = op.get("nodeId")
        zone_id = op.get("zoneId")
        for node in nodes:
            if node.get("nodeId") == node_id:
                node["zoneId"] = zone_id
                node["placementStatus"] = "provisional"
                node["qualitativePlacement"] = op.get("qualitativePlacement") or (
                    f"Assigned to zone {zone_id}."
                )
                node["provenance"] = {"schemaVersion": "1.0.0", "sourceType": "user"}
        for zone in zones:
            members = [m for m in (zone.get("memberNodeIds") or []) if m != node_id]
            if zone.get("zoneId") == zone_id:
                members.append(node_id)
            zone["memberNodeIds"] = members
    elif op_type == "add-relationship":
        relationships.append(
            {
                "relationshipId": new_id("prel_"),
                "fromNodeId": op["fromNodeId"],
                "toNodeId": op["toNodeId"],
                "relationshipType": op.get("relationshipType") or "adjacent-to",
                "status": op.get("status") or "provisional",
                "provenance": {"schemaVersion": "1.0.0", "sourceType": "user"},
            }
        )
    elif op_type == "delete-relationship":
        rel_id = op.get("relationshipId")
        relationships = [r for r in relationships if r.get("relationshipId") != rel_id]
    elif op_type == "change-relationship":
        rel_id = op.get("relationshipId")
        for rel in relationships:
            if rel.get("relationshipId") != rel_id:
                continue
            if "relationshipType" in op:
                rel["relationshipType"] = op["relationshipType"]
            if "status" in op:
                rel["status"] = op["status"]
            rel["provenance"] = {"schemaVersion": "1.0.0", "sourceType": "user"}
    elif op_type == "edit-placement":
        node_id = op.get("nodeId")
        for node in nodes:
            if node.get("nodeId") != node_id:
                continue
            if "qualitativePlacement" in op:
                node["qualitativePlacement"] = op["qualitativePlacement"]
            if "constraints" in op:
                node["constraints"] = list(op["constraints"])
            if "placementStatus" in op:
                node["placementStatus"] = op["placementStatus"]
            node["provenance"] = {"schemaVersion": "1.0.0", "sourceType": "user"}
    else:
        raise ValueError(f"Unknown Physical semantic op: {op_type}")

    next_content["nodes"] = nodes
    next_content["zones"] = zones
    next_content["relationships"] = relationships
    coverage = dict(next_content.get("coverageSummary") or {})
    coverage["unresolvedPlacementCount"] = sum(
        1 for n in nodes if n.get("placementStatus") in {"unresolved", "unknown"}
    )
    coverage["provisionalRelationshipCount"] = sum(
        1 for r in relationships if r.get("status") == "provisional"
    )
    next_content["coverageSummary"] = coverage
    return next_content
