"""Conservative Physical Architecture composition from Electrical Architecture."""

from __future__ import annotations

from typing import Any

from nexus_embedded_systems.workflows.project_initialization.ids import (
    artifact_envelope,
    new_id,
    utc_now,
)

_ELECTRICAL_TO_PHYSICAL: dict[str, str] = {
    "component": "module",
    "power-source": "power-source",
    "power-regulator": "module",
    "connector": "connector",
    "protection": "module",
    "supporting-electronics": "module",
    "external-interface": "external-system",
    "junction": "board",
}

# Refine physical type from Component category when available via role name/notes.
_NAME_HINTS: list[tuple[tuple[str, ...], str]] = [
    (("sensor", "imu", "env", "soil", "temp"), "sensor"),
    (("servo", "motor", "actuator", "drv"), "actuator"),
    (("ble", "wifi", "radio", "uart"), "module"),
    (("button", "oled", "display", "hmi"), "module"),
]


def compose_physical_architecture_content(
    *,
    electrical_content: dict[str, Any],
    previous_content: dict[str, Any] | None = None,
    project_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create provisional physical topology from Electrical nodes.

    Placement stays unresolved unless enough qualitative context exists.
    Preserves Physical node IDs when prior content maps the same Electrical node.
    """

    prior_by_enode: dict[str, dict[str, Any]] = {}
    if previous_content:
        for prior_node in previous_content.get("nodes") or []:
            if not isinstance(prior_node, dict):
                continue
            for eid in prior_node.get("electricalNodeIds") or []:
                if isinstance(eid, str) and eid not in prior_by_enode:
                    prior_by_enode[eid] = prior_node

    enclosure_zone_id = new_id("pzone_")
    external_zone_id = new_id("pzone_")
    zones: list[dict[str, Any]] = [
        {
            "zoneId": enclosure_zone_id,
            "name": "Primary enclosure",
            "zoneKind": "enclosure",
            "memberNodeIds": [],
            "notes": "Default qualitative enclosure zone; precise placement unresolved.",
        },
        {
            "zoneId": external_zone_id,
            "name": "External sensing / environment",
            "zoneKind": "external-sensing",
            "memberNodeIds": [],
            "notes": "Optional external exposure zone when sensing is environmentally exposed.",
        },
    ]

    context_blob = " ".join(
        str(project_context.get(k) or "")
        for k in ("systemBoundary", "problemStatement", "summary")
        if project_context
    ).casefold()

    nodes: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    enode_to_pnode: dict[str, str] = {}
    unresolved_placement = 0

    electrical_nodes = [n for n in (electrical_content.get("nodes") or []) if isinstance(n, dict)]
    for enode in electrical_nodes:
        enode_id = enode.get("nodeId")
        if not isinstance(enode_id, str):
            continue
        prior = prior_by_enode.get(enode_id)
        pnode_id = (
            prior["nodeId"] if prior and isinstance(prior.get("nodeId"), str) else new_id("pnode_")
        )
        physical_type = _infer_physical_type(enode)
        placement_status = "provisional"
        zone_id = enclosure_zone_id
        qualitative = "Inside primary enclosure (provisional)."
        if physical_type == "sensor" and (
            "greenhouse" in context_blob
            or "outdoor" in context_blob
            or "environment" in context_blob
        ):
            zone_id = external_zone_id
            qualitative = "Environmentally exposed sensing (qualitative)."
        elif physical_type == "external-system":
            placement_status = "unresolved"
            qualitative = "External system placement not determined."
            zone_id = external_zone_id
            unresolved_placement += 1
        elif enode.get("implementationStatus") == "unresolved":
            placement_status = "unresolved"
            qualitative = "Physical placement unresolved until electrical implementation exists."
            unresolved_placement += 1
        else:
            # Known enough for a provisional enclosure assignment, but not CAD-precise.
            placement_status = "provisional"

        for zone in zones:
            if zone["zoneId"] == zone_id:
                zone["memberNodeIds"].append(pnode_id)

        node: dict[str, Any] = {
            "nodeId": pnode_id,
            "name": str(enode.get("name") or "Physical entity"),
            "nodeType": physical_type,
            "electricalNodeIds": [enode_id],
            "placementStatus": placement_status,
            "zoneId": zone_id,
            "qualitativePlacement": qualitative,
            "constraints": [],
            "notes": (
                "Fixture/provisional topology; not CAD geometry."
                if electrical_content.get("evidenceStatus") == "unverified"
                else None
            ),
            "provenance": {
                "schemaVersion": "1.0.0",
                "sourceType": "derived",
                "derivedFromIds": [enode_id],
            },
        }
        if node["notes"] is None:
            del node["notes"]
        nodes.append(node)
        enode_to_pnode[enode_id] = pnode_id

        if placement_status == "unresolved":
            warnings.append(
                {
                    "code": "PHYSICAL_PLACEMENT_UNRESOLVED",
                    "message": f"Placement unresolved for {node['name']}.",
                    "severity": "info",
                    "relatedNodeIds": [pnode_id],
                }
            )

    relationships = _propose_relationships(
        nodes=nodes,
        enclosure_zone_id=enclosure_zone_id,
        previous_content=previous_content,
    )
    provisional_rels = sum(1 for r in relationships if r.get("status") == "provisional")

    covered = sorted(enode_to_pnode)
    all_e = sorted(n["nodeId"] for n in electrical_nodes if isinstance(n.get("nodeId"), str))
    uncovered = [eid for eid in all_e if eid not in covered]

    return {
        "architectureId": (
            previous_content.get("architectureId")
            if previous_content and isinstance(previous_content.get("architectureId"), str)
            else new_id("parch_")
        ),
        "maturity": "provisional",
        "summary": (
            f"Physical Architecture with {len(nodes)} entity(ies) and {len(zones)} zone(s). "
            "Topology is qualitative/provisional; CAD geometry is out of scope."
        ),
        "nodes": nodes,
        "zones": zones,
        "relationships": relationships,
        "assumptions": [
            {
                "assumptionId": "PA1",
                "statement": (
                    "Physical Architecture represents containment and qualitative placement, "
                    "not mechanical CAD."
                ),
                "sourceType": "system-inferred",
                "confidence": "medium",
                "confirmationStatus": "proposed",
            }
        ],
        "unresolvedDecisions": [],
        "warnings": warnings,
        "coverageSummary": {
            "totalElectricalNodes": len(all_e),
            "coveredElectricalNodes": len(covered),
            "uncoveredElectricalNodeIds": uncovered,
            "unresolvedPlacementCount": unresolved_placement,
            "provisionalRelationshipCount": provisional_rels,
        },
        "evidenceStatus": electrical_content.get("evidenceStatus") or "unverified",
    }


def compose_physical_architecture_envelope(
    *,
    content: dict[str, Any],
    project_id: str,
    turn_id: str,
    workflow_run_id: str,
    created_by: dict[str, Any],
    now: str | None = None,
) -> dict[str, Any]:
    stamp = now or utc_now()
    return artifact_envelope(
        artifact_type="physical-architecture",
        content=content,
        project_id=project_id,
        turn_id=turn_id,
        workflow_run_id=workflow_run_id,
        created_by=created_by,
        now=stamp,
        lifecycle_status="drafted",
        evidence_status=content.get("evidenceStatus") or "unverified",
        approval_status="proposed",
    )


def _infer_physical_type(enode: dict[str, Any]) -> str:
    base = _ELECTRICAL_TO_PHYSICAL.get(str(enode.get("nodeType") or "component"), "module")
    blob = str(enode.get("name") or "").casefold()
    for hints, mapped in _NAME_HINTS:
        if any(h in blob for h in hints):
            return mapped
    if enode.get("nodeType") == "external-interface":
        return "external-system"
    return base


def _propose_relationships(
    *,
    nodes: list[dict[str, Any]],
    enclosure_zone_id: str,
    previous_content: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    prior_pairs: dict[tuple[str, str, str], dict[str, Any]] = {}
    if previous_content:
        for rel in previous_content.get("relationships") or []:
            if not isinstance(rel, dict):
                continue
            key = (
                str(rel.get("fromNodeId")),
                str(rel.get("toNodeId")),
                str(rel.get("relationshipType")),
            )
            prior_pairs[key] = rel

    # Create a synthetic enclosure assembly node only as relationships among members
    # sharing the enclosure zone — mounted-on is expressed via zone membership notes.
    # Explicit relationships: modules inside enclosure zone are "inside" relative to
    # the first board-like node if present, else adjacent-to each other is avoided.
    relationships: list[dict[str, Any]] = []
    enclosure_members = [n for n in nodes if n.get("zoneId") == enclosure_zone_id]
    board = next((n for n in enclosure_members if n.get("nodeType") == "board"), None)
    anchor = board or (enclosure_members[0] if enclosure_members else None)
    if anchor is None:
        return relationships
    for node in enclosure_members:
        if node["nodeId"] == anchor["nodeId"]:
            continue
        rel_type = "mounted-on" if anchor.get("nodeType") == "board" else "inside"
        key = (node["nodeId"], anchor["nodeId"], rel_type)
        prior = prior_pairs.get(key)
        relationships.append(
            {
                "relationshipId": (
                    prior["relationshipId"]
                    if prior and isinstance(prior.get("relationshipId"), str)
                    else new_id("prel_")
                ),
                "fromNodeId": node["nodeId"],
                "toNodeId": anchor["nodeId"],
                "relationshipType": rel_type,
                "status": "provisional",
            }
        )
    return relationships
