"""Materialize layered-architecture graph nodes and edges from artifacts."""

from __future__ import annotations

from typing import Any, Protocol

from nexus_board.ids import new_id, utc_now_iso

_LAYERED_ARTIFACT_TYPES = frozenset(
    {
        "requirement-set",
        "functional-architecture",
        "component-plan",
        "electrical-architecture",
        "physical-architecture",
    }
)


class _GraphMaterializationStore(Protocol):
    def list_graph_nodes(self, project_id: str) -> list[dict[str, Any]]: ...

    def list_graph_edges(self, project_id: str) -> list[dict[str, Any]]: ...

    def create_graph_node(self, node: dict[str, Any]) -> None: ...

    def create_graph_edge(self, edge: dict[str, Any]) -> None: ...


def materialize_layered_architecture_graph(
    store: _GraphMaterializationStore,
    project_id: str,
    artifacts: list[dict[str, Any]],
    event_id: str,
) -> dict[str, Any]:
    """Upsert requirement → FA → role → electrical → physical graph slice.

    Edges:
      - requirement --covers--> FA node
      - component-role --derives-from--> FA node
      - electrical-node --supports--> component-role
      - physical-node --derives-from--> electrical-node
    """

    by_type = {
        a["artifactType"]: a
        for a in artifacts
        if isinstance(a, dict) and isinstance(a.get("artifactType"), str)
    }
    now = utc_now_iso()
    existing_nodes = store.list_graph_nodes(project_id)
    existing_edges = store.list_graph_edges(project_id)

    nodes_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for node in existing_nodes:
        ref = node.get("refId")
        ntype = node.get("nodeType")
        if isinstance(ref, str) and isinstance(ntype, str):
            nodes_by_key[(ntype, ref)] = node

    edge_keys: set[tuple[str, str, str]] = set()
    for edge in existing_edges:
        edge_keys.add(
            (
                str(edge.get("sourceNodeId")),
                str(edge.get("targetNodeId")),
                str(edge.get("edgeType")),
            )
        )

    created_nodes = 0
    created_edges = 0

    def upsert_node(*, node_type: str, ref_id: str, label: str) -> dict[str, Any]:
        nonlocal created_nodes
        key = (node_type, ref_id)
        existing = nodes_by_key.get(key)
        if existing is not None:
            return existing
        node = {
            "schemaVersion": "1.0.0",
            "nodeId": new_id("gnode"),
            "projectId": project_id,
            "nodeType": node_type,
            "refId": ref_id,
            "label": label,
            "createdByEventId": event_id,
            "createdAt": now,
        }
        store.create_graph_node(node)
        nodes_by_key[key] = node
        created_nodes += 1
        return node

    def upsert_edge(*, source: dict[str, Any], target: dict[str, Any], edge_type: str) -> None:
        nonlocal created_edges
        key = (source["nodeId"], target["nodeId"], edge_type)
        if key in edge_keys:
            return
        edge = {
            "schemaVersion": "1.0.0",
            "edgeId": new_id("gedge"),
            "projectId": project_id,
            "sourceNodeId": source["nodeId"],
            "targetNodeId": target["nodeId"],
            "edgeType": edge_type,
            "createdByEventId": event_id,
            "validFrom": now,
        }
        store.create_graph_edge(edge)
        edge_keys.add(key)
        created_edges += 1

    req_set = by_type.get("requirement-set")
    if isinstance(req_set, dict):
        for req in (req_set.get("content") or {}).get("requirements") or []:
            if not isinstance(req, dict):
                continue
            rid = req.get("requirementId")
            if not isinstance(rid, str):
                continue
            upsert_node(
                node_type="requirement",
                ref_id=rid,
                label=str(req.get("displayId") or req.get("statement") or rid)[:120],
            )

    fa = by_type.get("functional-architecture")
    fa_nodes: dict[str, dict[str, Any]] = {}
    if isinstance(fa, dict):
        for node in (fa.get("content") or {}).get("nodes") or []:
            if not isinstance(node, dict):
                continue
            nid = node.get("nodeId")
            if not isinstance(nid, str):
                continue
            gnode = upsert_node(
                node_type="architecture-node",
                ref_id=nid,
                label=str(node.get("name") or nid),
            )
            fa_nodes[nid] = gnode
            for rid in node.get("satisfiesRequirementIds") or []:
                if not isinstance(rid, str):
                    continue
                req_node = nodes_by_key.get(("requirement", rid))
                if req_node is None:
                    req_node = upsert_node(node_type="requirement", ref_id=rid, label=rid)
                upsert_edge(source=req_node, target=gnode, edge_type="covers")

    plan = by_type.get("component-plan")
    role_nodes: dict[str, dict[str, Any]] = {}
    if isinstance(plan, dict):
        for role in (plan.get("content") or {}).get("componentRoles") or []:
            if not isinstance(role, dict):
                continue
            role_id = role.get("componentRoleId")
            if not isinstance(role_id, str):
                continue
            role_node = upsert_node(
                node_type="component-role",
                ref_id=role_id,
                label=str(role.get("name") or role_id),
            )
            role_nodes[role_id] = role_node
            for fa_id in role.get("architectureNodeIds") or []:
                if not isinstance(fa_id, str):
                    continue
                fa_node = fa_nodes.get(fa_id) or nodes_by_key.get(("architecture-node", fa_id))
                if fa_node is None:
                    continue
                upsert_edge(source=role_node, target=fa_node, edge_type="derives-from")

    electrical = by_type.get("electrical-architecture")
    electrical_nodes: dict[str, dict[str, Any]] = {}
    if isinstance(electrical, dict):
        for enode in (electrical.get("content") or {}).get("nodes") or []:
            if not isinstance(enode, dict):
                continue
            eid = enode.get("nodeId")
            if not isinstance(eid, str):
                continue
            e_gnode = upsert_node(
                node_type="electrical-node",
                ref_id=eid,
                label=str(enode.get("name") or eid),
            )
            electrical_nodes[eid] = e_gnode
            for role_id in enode.get("componentRoleIds") or []:
                if not isinstance(role_id, str):
                    continue
                linked_role = role_nodes.get(role_id) or nodes_by_key.get(
                    ("component-role", role_id)
                )
                if linked_role is None:
                    continue
                upsert_edge(source=e_gnode, target=linked_role, edge_type="supports")

    physical = by_type.get("physical-architecture")
    if isinstance(physical, dict):
        for pnode in (physical.get("content") or {}).get("nodes") or []:
            if not isinstance(pnode, dict):
                continue
            pid = pnode.get("nodeId")
            if not isinstance(pid, str):
                continue
            p_gnode = upsert_node(
                node_type="physical-node",
                ref_id=pid,
                label=str(pnode.get("name") or pid),
            )
            for eid in pnode.get("electricalNodeIds") or []:
                if not isinstance(eid, str):
                    continue
                linked_electrical = electrical_nodes.get(eid) or nodes_by_key.get(
                    ("electrical-node", eid)
                )
                if linked_electrical is None:
                    continue
                upsert_edge(source=p_gnode, target=linked_electrical, edge_type="derives-from")

    return {
        "createdNodes": created_nodes,
        "createdEdges": created_edges,
        "artifactTypesPresent": sorted(set(by_type) & _LAYERED_ARTIFACT_TYPES),
    }


def should_materialize_for_artifact_type(artifact_type: str) -> bool:
    return artifact_type in _LAYERED_ARTIFACT_TYPES
