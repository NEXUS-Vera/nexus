"""Deterministic Electrical Architecture composition from FA + Component Plan."""

from __future__ import annotations

from typing import Any

from nexus_embedded_systems.workflows.component_planning.derive_roles import is_i2c_bus
from nexus_embedded_systems.workflows.layered_architecture.normalize_specs import (
    get_normalized_interface,
    get_normalized_voltage,
    normalize_candidate_specifications,
    voltage_domain_key,
)
from nexus_embedded_systems.workflows.layered_architecture.validation import (
    electrical_validation_warnings,
)
from nexus_embedded_systems.workflows.project_initialization.ids import (
    artifact_envelope,
    new_id,
    utc_now,
)

_CATEGORY_TO_NODE_TYPE: dict[str, str] = {
    "sensor": "component",
    "compute": "component",
    "communication": "component",
    "storage": "component",
    "actuation": "component",
    "interface": "component",
    "power": "power-regulator",
    "protection": "protection",
    "mechanical": "supporting-electronics",
    "supporting-electronics": "supporting-electronics",
}

_FLOW_TO_CONNECTION: dict[str, str] = {
    "data": "signal",
    "control": "control",
    "power": "power",
    "user-input": "signal",
    "physical-output": "other",
}


def compose_electrical_architecture_content(
    *,
    architecture_content: dict[str, Any],
    component_plan_content: dict[str, Any],
    previous_content: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose Electrical Architecture from Functional Architecture + Component Plan.

    Does not invent hardware selections. Uses approved → preferred → unresolved.
    Preserves Electrical node IDs when prior content maps the same Component Role.
    """

    fa_nodes = {
        n["nodeId"]: n
        for n in (architecture_content.get("nodes") or [])
        if isinstance(n, dict) and isinstance(n.get("nodeId"), str)
    }
    fa_edges = [e for e in (architecture_content.get("edges") or []) if isinstance(e, dict)]
    roles = [r for r in (component_plan_content.get("componentRoles") or []) if isinstance(r, dict)]
    candidates = {
        c["candidateId"]: c
        for c in (component_plan_content.get("candidates") or [])
        if isinstance(c, dict) and isinstance(c.get("candidateId"), str)
    }
    selections = [
        s for s in (component_plan_content.get("selectionDecisions") or []) if isinstance(s, dict)
    ]

    prior_by_role: dict[str, dict[str, Any]] = {}
    if previous_content:
        for prior_node in previous_content.get("nodes") or []:
            if not isinstance(prior_node, dict):
                continue
            for role_id in prior_node.get("componentRoleIds") or []:
                if isinstance(role_id, str) and role_id not in prior_by_role:
                    prior_by_role[role_id] = prior_node

    nodes: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    role_to_enode: dict[str, str] = {}
    fa_to_enodes: dict[str, list[str]] = {}

    preferred_count = 0
    approved_count = 0
    unresolved_count = 0

    for role in roles:
        role_id = role.get("componentRoleId")
        if not isinstance(role_id, str):
            continue
        fa_ids = [
            i
            for i in (role.get("architectureNodeIds") or [])
            if isinstance(i, str) and i in fa_nodes
        ]
        impl = _resolve_implementation(role_id, selections, candidates)
        category = str(role.get("category") or "sensor")
        node_type = _CATEGORY_TO_NODE_TYPE.get(category, "component")
        if category == "power" and impl["candidate"] is not None:
            part = str(impl["candidate"].get("partNumber") or "").upper()
            display = str(impl["candidate"].get("displayName") or "").casefold()
            if "LIPO" in part or "batt" in display or "cell" in display:
                node_type = "power-source"

        prior = prior_by_role.get(role_id)
        node_id = (
            prior["nodeId"] if prior and isinstance(prior.get("nodeId"), str) else new_id("enode_")
        )

        specs = normalize_candidate_specifications(
            (impl["candidate"] or {}).get("specifications") if impl["candidate"] else None
        )
        interface_type = get_normalized_interface(specs)
        interfaces: list[dict[str, Any]] = []
        iface_provenance = _interface_provenance(impl["candidate"])
        if impl["candidate"] is not None:
            iface_status = (
                "resolved" if interface_type not in {"unknown", "other"} else "needs-resolution"
            )
            if interface_type == "unknown":
                iface_status = "unknown"
            interfaces.append(
                {
                    "interfaceId": new_id("eiface_"),
                    "interfaceType": interface_type,
                    "direction": "bidirectional",
                    "status": iface_status,
                    "label": f"{interface_type} interface",
                    "notes": (
                        "Derived from normalized candidate specification."
                        if iface_status == "resolved"
                        else "Interface unknown or ambiguous from candidate specifications."
                    ),
                    "provenance": iface_provenance,
                }
            )
            supply = get_normalized_voltage(specs, "supply-voltage")
            if supply is not None:
                interfaces.append(
                    {
                        "interfaceId": new_id("eiface_"),
                        "interfaceType": "power",
                        "direction": "in",
                        "status": "resolved",
                        "label": "supply",
                        "voltage": supply,
                        "provenance": iface_provenance,
                    }
                )
            elif (specs.get("specs") or {}).get("supply-voltage", {}).get("unknown"):
                warnings.append(
                    {
                        "code": "SUPPLY_VOLTAGE_UNKNOWN",
                        "message": (
                            f"Supply voltage unknown for role {role.get('name') or role_id}."
                        ),
                        "severity": "warning",
                        "relatedNodeIds": [node_id],
                    }
                )
        else:
            interfaces.append(
                {
                    "interfaceId": new_id("eiface_"),
                    "interfaceType": "unknown",
                    "direction": "unknown",
                    "status": "unresolved",
                    "label": "unimplemented",
                    "notes": "No preferred or approved candidate for this Component Role.",
                    "provenance": iface_provenance,
                }
            )
            unresolved_count += 1
            warnings.append(
                {
                    "code": "IMPLEMENTATION_UNRESOLVED",
                    "message": (
                        f"No concrete implementation for role {role.get('name') or role_id}."
                    ),
                    "severity": "warning",
                    "relatedNodeIds": [node_id],
                }
            )

        if impl["basis"] == "preferred":
            preferred_count += 1
            implementation_status = "preferred"
            selection_state = "preferred"
        elif impl["basis"] == "approved":
            approved_count += 1
            implementation_status = "approved"
            selection_state = "approved"
        else:
            implementation_status = "unresolved"
            selection_state = "unresolved"

        evidence = "unverified"
        if impl["candidate"] is not None:
            cand_evidence = impl["candidate"].get("evidenceStatus")
            if isinstance(cand_evidence, str):
                evidence = cand_evidence
            if impl["candidate"].get("source") == "fixture":
                implementation_status = "provisional" if impl["basis"] != "approved" else "approved"
                if impl["basis"] == "preferred":
                    implementation_status = "provisional"

        req_ids: list[str] = []
        for fa_id in fa_ids:
            req_ids.extend(
                rid
                for rid in (fa_nodes[fa_id].get("satisfiesRequirementIds") or [])
                if isinstance(rid, str)
            )
            fa_to_enodes.setdefault(fa_id, []).append(node_id)

        name = str(role.get("name") or "Electrical node")
        if impl["candidate"] is not None:
            name = str(impl["candidate"].get("displayName") or name)

        electrical_node: dict[str, Any] = {
            "nodeId": node_id,
            "name": name,
            "nodeType": node_type,
            "functionalArchitectureNodeIds": fa_ids,
            "componentRoleIds": [role_id],
            "implementationStatus": implementation_status,
            "evidenceStatus": evidence if evidence != "tested" else "unverified",
            "selectionState": selection_state,
            "interfaces": interfaces,
            "requirementIds": sorted(set(req_ids)),
            "notes": (
                "Provisional fixture-derived implementation; datasheet grounding deferred."
                if impl["candidate"] and impl["candidate"].get("source") == "fixture"
                else None
            ),
        }
        if impl["candidate"] is not None:
            electrical_node["componentCandidateId"] = impl["candidate"]["candidateId"]
        if electrical_node["notes"] is None:
            del electrical_node["notes"]
        nodes.append(electrical_node)
        role_to_enode[role_id] = node_id

    fa_edges = _resolve_i2c_bus_edges(fa_nodes, fa_edges)
    connections = _propose_connections(
        fa_edges=fa_edges,
        fa_to_enodes=fa_to_enodes,
        nodes_by_id={n["nodeId"]: n for n in nodes},
        candidates=candidates,
        previous_content=previous_content,
        warnings=warnings,
    )

    power_domains = _propose_power_domains(nodes)

    covered_fa = sorted({fid for fid, enodes in fa_to_enodes.items() if enodes})
    all_fa_ids = sorted(fa_nodes)
    uncovered = [fid for fid in all_fa_ids if fid not in covered_fa]

    unresolved_connections = sum(
        1 for c in connections if c.get("status") in {"unresolved", "needs-resolution"}
    )

    any_fixture = any(
        (candidates.get(n.get("componentCandidateId") or "") or {}).get("source") == "fixture"
        for n in nodes
        if n.get("componentCandidateId")
    )
    content_evidence = "unverified" if any_fixture or unresolved_count else "inferred"

    content = {
        "architectureId": (
            previous_content.get("architectureId")
            if previous_content and isinstance(previous_content.get("architectureId"), str)
            else new_id("earch_")
        ),
        "maturity": "provisional",
        "summary": (
            f"Electrical Architecture with {len(nodes)} implementation node(s), "
            f"{approved_count} approved, {preferred_count} preferred/provisional, "
            f"{unresolved_count} unresolved. Derived from Functional Architecture and "
            "Component Plan without independent hardware selection."
        ),
        "nodes": nodes,
        "connections": connections,
        "powerDomains": power_domains,
        "assumptions": [
            {
                "assumptionId": "EA1",
                "statement": (
                    "Electrical connections are proposed from Functional Architecture "
                    "flows and normalized candidate interfaces; they are not a pin netlist."
                ),
                "sourceType": "system-inferred",
                "confidence": "medium",
                "confirmationStatus": "proposed",
            }
        ],
        "unresolvedDecisions": [],
        "warnings": warnings,
        "coverageSummary": {
            "totalFunctionalNodes": len(all_fa_ids),
            "coveredFunctionalNodes": len(covered_fa),
            "uncoveredFunctionalNodeIds": uncovered,
            "preferredImplementationCount": preferred_count,
            "approvedImplementationCount": approved_count,
            "unresolvedImplementationCount": unresolved_count,
            "unresolvedConnectionCount": unresolved_connections,
        },
        "evidenceStatus": content_evidence,
        "selectionBasisSummary": (
            "Implementations bind approved selections first, then preferred candidates; "
            "remaining roles stay unresolved. Fixture candidates remain provisional/unverified."
        ),
    }
    content["warnings"] = [
        *warnings,
        *electrical_validation_warnings(content),
    ]
    return content


def compose_electrical_architecture_envelope(
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
        artifact_type="electrical-architecture",
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


def _resolve_implementation(
    role_id: str,
    selections: list[dict[str, Any]],
    candidates: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    approved = next(
        (
            s
            for s in selections
            if s.get("componentRoleId") == role_id and s.get("selectionState") == "approved"
        ),
        None,
    )
    if approved and isinstance(approved.get("selectedCandidateId"), str):
        cand = candidates.get(approved["selectedCandidateId"])
        if cand is not None and cand.get("candidateState") not in {"blocked", "rejected"}:
            return {"basis": "approved", "candidate": cand, "selection": approved}

    preferred = next(
        (
            c
            for c in candidates.values()
            if c.get("componentRoleId") == role_id and c.get("candidateState") == "preferred"
        ),
        None,
    )
    if preferred is not None:
        return {"basis": "preferred", "candidate": preferred, "selection": None}

    awaiting = next(
        (
            s
            for s in selections
            if s.get("componentRoleId") == role_id
            and s.get("selectionState") in {"awaiting-user", "proposed"}
        ),
        None,
    )
    if awaiting and isinstance(awaiting.get("selectedCandidateId"), str):
        cand = candidates.get(awaiting["selectedCandidateId"])
        if cand is not None:
            return {"basis": "preferred", "candidate": cand, "selection": awaiting}

    return {"basis": "unresolved", "candidate": None, "selection": None}


def _interface_provenance(candidate: dict[str, Any] | None) -> dict[str, Any]:
    if candidate is not None and candidate.get("source") == "fixture":
        provenance: dict[str, Any] = {
            "schemaVersion": "1.0.0",
            "sourceType": "fixture",
        }
        candidate_id = candidate.get("candidateId")
        if isinstance(candidate_id, str):
            provenance["derivedFromIds"] = [candidate_id]
        return provenance
    provenance = {
        "schemaVersion": "1.0.0",
        "sourceType": "component-plan",
    }
    if candidate is not None and isinstance(candidate.get("candidateId"), str):
        provenance["derivedFromIds"] = [candidate["candidateId"]]
    return provenance


def _connection_provenance(
    *,
    from_node: dict[str, Any],
    to_node: dict[str, Any],
    candidates: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    derived_ids: list[str] = []
    any_fixture = False
    for node in (from_node, to_node):
        candidate_id = node.get("componentCandidateId")
        if not isinstance(candidate_id, str):
            continue
        derived_ids.append(candidate_id)
        candidate = candidates.get(candidate_id) or {}
        if candidate.get("source") == "fixture":
            any_fixture = True
    provenance: dict[str, Any] = {
        "schemaVersion": "1.0.0",
        "sourceType": "fixture" if any_fixture else "component-plan",
    }
    if derived_ids:
        provenance["derivedFromIds"] = sorted(set(derived_ids))
    return provenance


def _resolve_i2c_bus_edges(
    nodes: dict[str, dict[str, Any]], edges: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Collapse directed flows through explicit I2C buses into one physical link.

    Only matching data/control paths are joined; power and unrelated transports
    cannot establish a signal binding. Preserve every contributing flow ID.
    """
    links: dict[tuple[str, str], dict[str, Any]] = {}
    for bus_id, node in nodes.items():
        if not is_i2c_bus(node, {"nodes": list(nodes.values()), "edges": edges}):
            continue
        for incoming in edges:
            if incoming.get("toNodeId") != bus_id or incoming.get("flowType") not in {
                "data",
                "control",
            }:
                continue
            for outgoing in edges:
                if outgoing.get("fromNodeId") != bus_id or outgoing.get("flowType") != incoming.get(
                    "flowType"
                ):
                    continue
                start, end = incoming.get("fromNodeId"), outgoing.get("toNodeId")
                if not isinstance(start, str) or not isinstance(end, str) or start == end:
                    continue
                pair = (start, end) if start < end else (end, start)
                link = links.setdefault(
                    pair,
                    {
                        "edgeId": incoming.get("edgeId"),
                        "fromNodeId": start,
                        "toNodeId": end,
                        "flowType": "data",
                        "description": "I2C binding through functional communication bus.",
                        "functionalArchitectureEdgeIds": [],
                    },
                )
                for edge in (incoming, outgoing):
                    edge_id = edge.get("edgeId")
                    if (
                        isinstance(edge_id, str)
                        and edge_id not in link["functionalArchitectureEdgeIds"]
                    ):
                        link["functionalArchitectureEdgeIds"].append(edge_id)
    resolved = [dict(edge) for edge in edges]
    for pair, link in links.items():
        direct = next(
            (
                edge
                for edge in resolved
                if edge.get("flowType") in {"data", "control"}
                and {edge.get("fromNodeId"), edge.get("toNodeId")} == set(pair)
            ),
            None,
        )
        if direct is None:
            resolved.append(link)
            continue
        provenance = list(direct.get("functionalArchitectureEdgeIds") or [])
        for edge_id in [direct.get("edgeId"), *link["functionalArchitectureEdgeIds"]]:
            if isinstance(edge_id, str) and edge_id not in provenance:
                provenance.append(edge_id)
        direct["functionalArchitectureEdgeIds"] = provenance
    return resolved


def _propose_connections(
    *,
    fa_edges: list[dict[str, Any]],
    fa_to_enodes: dict[str, list[str]],
    nodes_by_id: dict[str, dict[str, Any]],
    candidates: dict[str, dict[str, Any]],
    previous_content: dict[str, Any] | None,
    warnings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    prior_by_fa_edge: dict[str, dict[str, Any]] = {}
    if previous_content:
        for prior_conn in previous_content.get("connections") or []:
            if not isinstance(prior_conn, dict):
                continue
            for edge_id in prior_conn.get("functionalArchitectureEdgeIds") or []:
                if isinstance(edge_id, str):
                    prior_by_fa_edge[edge_id] = prior_conn

    connections: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str, str]] = set()
    for edge in fa_edges:
        edge_id = edge.get("edgeId")
        from_fa = edge.get("fromNodeId")
        to_fa = edge.get("toNodeId")
        if not isinstance(from_fa, str) or not isinstance(to_fa, str):
            continue
        from_enodes = fa_to_enodes.get(from_fa) or []
        to_enodes = fa_to_enodes.get(to_fa) or []
        if not from_enodes or not to_enodes:
            continue
        flow = str(edge.get("flowType") or "data")
        connection_type = _FLOW_TO_CONNECTION.get(flow, "other")
        for from_id in from_enodes:
            for to_id in to_enodes:
                if from_id == to_id:
                    continue
                pair = (from_id, to_id, connection_type)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                from_node = nodes_by_id[from_id]
                to_node = nodes_by_id[to_id]
                iface = _pick_compatible_interface(from_node, to_node, connection_type)
                status = iface["status"]
                # Connection schema does not allow status "unknown".
                if status == "unknown":
                    status = "needs-resolution"
                prior = prior_by_fa_edge.get(edge_id) if isinstance(edge_id, str) else None
                conn_id = (
                    prior["connectionId"]
                    if prior and isinstance(prior.get("connectionId"), str)
                    else new_id("econn_")
                )
                conn: dict[str, Any] = {
                    "connectionId": conn_id,
                    "fromNodeId": from_id,
                    "toNodeId": to_id,
                    "connectionType": connection_type,
                    "interfaceType": iface["interfaceType"],
                    "status": status,
                    "description": str(edge.get("description") or f"{flow} flow"),
                    "provenance": _connection_provenance(
                        from_node=from_node,
                        to_node=to_node,
                        candidates=candidates,
                    ),
                }
                if isinstance(edge_id, str):
                    conn["functionalArchitectureEdgeIds"] = edge.get(
                        "functionalArchitectureEdgeIds"
                    ) or [edge_id]
                if iface.get("fromInterfaceId"):
                    conn["fromInterfaceId"] = iface["fromInterfaceId"]
                if iface.get("toInterfaceId"):
                    conn["toInterfaceId"] = iface["toInterfaceId"]
                if status in {"provisional", "needs-resolution", "unresolved"}:
                    conn["provisionalReason"] = iface.get("reason") or (
                        "Interface compatibility not fully resolved."
                    )
                    warnings.append(
                        {
                            "code": "CONNECTION_NEEDS_RESOLUTION",
                            "message": conn["provisionalReason"],
                            "severity": "warning",
                            "relatedNodeIds": [from_id, to_id],
                        }
                    )
                connections.append(conn)
    return connections


def _pick_compatible_interface(
    from_node: dict[str, Any],
    to_node: dict[str, Any],
    connection_type: str,
) -> dict[str, Any]:
    if connection_type == "power":
        return {
            "interfaceType": "power",
            "status": "provisional",
            "reason": "Power connectivity inferred from Functional Architecture power flow.",
        }

    def primary_iface(node: dict[str, Any]) -> dict[str, Any] | None:
        for iface in node.get("interfaces") or []:
            if isinstance(iface, dict) and iface.get("interfaceType") not in {
                "power",
                "ground",
            }:
                return iface
        return None

    a = primary_iface(from_node)
    b = primary_iface(to_node)
    if a is None or b is None:
        return {
            "interfaceType": "unknown",
            "status": "needs-resolution",
            "reason": "One or both endpoints lack a resolved signal interface.",
        }
    a_type = str(a.get("interfaceType") or "unknown")
    b_type = str(b.get("interfaceType") or "unknown")
    if a_type == "unknown" or b_type == "unknown":
        return {
            "interfaceType": "unknown",
            "status": "unknown",
            "fromInterfaceId": a.get("interfaceId"),
            "toInterfaceId": b.get("interfaceId"),
            "reason": "Endpoint interface type unknown.",
        }
    if a_type != b_type and {a_type, b_type} != {"other"}:
        return {
            "interfaceType": "other",
            "status": "needs-resolution",
            "fromInterfaceId": a.get("interfaceId"),
            "toInterfaceId": b.get("interfaceId"),
            "reason": f"Interface mismatch between {a_type} and {b_type}.",
        }
    status = "resolved"
    if from_node.get("implementationStatus") in {"provisional", "preferred"} or to_node.get(
        "implementationStatus"
    ) in {"provisional", "preferred"}:
        status = "provisional"
    return {
        "interfaceType": a_type,
        "status": status,
        "fromInterfaceId": a.get("interfaceId"),
        "toInterfaceId": b.get("interfaceId"),
    }


def _propose_power_domains(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    domains: dict[str, dict[str, Any]] = {}
    for node in nodes:
        for iface in node.get("interfaces") or []:
            if not isinstance(iface, dict) or iface.get("interfaceType") != "power":
                continue
            voltage = iface.get("voltage")
            if not isinstance(voltage, dict) or not isinstance(voltage.get("value"), int | float):
                continue
            key = voltage_domain_key(voltage)
            domain = domains.get(key)
            if domain is None:
                domain = {
                    "powerDomainId": new_id("epwr_"),
                    "name": f"{voltage['value']} {voltage.get('unit') or 'V'} rail",
                    "status": "known",
                    "nominalVoltage": voltage,
                    "memberNodeIds": [],
                    "notes": "Derived from normalized supply-voltage specifications.",
                }
                domains[key] = domain
            domain["memberNodeIds"].append(node["nodeId"])
    if not domains:
        return [
            {
                "powerDomainId": new_id("epwr_"),
                "name": "Unspecified supply domain",
                "status": "unknown",
                "memberNodeIds": [n["nodeId"] for n in nodes],
                "notes": "Insufficient supply-voltage evidence to define rails.",
            }
        ]
    return list(domains.values())
