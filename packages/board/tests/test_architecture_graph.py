"""Layered architecture graph materialization tests."""

from __future__ import annotations

from helpers import build_test_kernel
from nexus_board.ids import new_id
from nexus_board.services.architecture_graph import materialize_layered_architecture_graph


def test_traversal_requirement_to_physical() -> None:
    kernel, project_store, kernel_store, project_id = build_test_kernel()

    req_id = new_id("req")
    fa_id = new_id("node")
    role_id = new_id("role")
    enode_id = new_id("enode")
    pnode_id = new_id("pnode")

    artifacts = [
        {
            "artifactType": "requirement-set",
            "content": {
                "requirements": [
                    {
                        "requirementId": req_id,
                        "displayId": "R1",
                        "statement": "Measure temperature",
                    }
                ]
            },
        },
        {
            "artifactType": "functional-architecture",
            "content": {
                "nodes": [
                    {
                        "nodeId": fa_id,
                        "name": "Sensing",
                        "satisfiesRequirementIds": [req_id],
                    }
                ]
            },
        },
        {
            "artifactType": "component-plan",
            "content": {
                "componentRoles": [
                    {
                        "componentRoleId": role_id,
                        "name": "Temp sensor",
                        "architectureNodeIds": [fa_id],
                    }
                ]
            },
        },
        {
            "artifactType": "electrical-architecture",
            "content": {
                "nodes": [
                    {
                        "nodeId": enode_id,
                        "name": "BME280",
                        "componentRoleIds": [role_id],
                    }
                ]
            },
        },
        {
            "artifactType": "physical-architecture",
            "content": {
                "nodes": [
                    {
                        "nodeId": pnode_id,
                        "name": "Env sensor module",
                        "electricalNodeIds": [enode_id],
                    }
                ]
            },
        },
    ]

    result = materialize_layered_architecture_graph(
        kernel_store,
        project_id,
        artifacts,
        new_id("evt"),
    )
    assert result["createdNodes"] >= 5
    assert result["createdEdges"] >= 4

    nodes = {(n["nodeType"], n["refId"]): n for n in kernel_store.list_graph_nodes(project_id)}
    req_node = nodes[("requirement", req_id)]
    fa_node = nodes[("architecture-node", fa_id)]
    role_node = nodes[("component-role", role_id)]
    e_node = nodes[("electrical-node", enode_id)]
    p_node = nodes[("physical-node", pnode_id)]

    downstream = kernel.graph.reader.get_downstream(
        project_id,
        req_node["nodeId"],
        max_depth=5,
        max_nodes=50,
        max_edges=50,
    )
    visited = {n["nodeId"] for n in downstream["nodes"]}
    # covers is req → FA, so FA is outbound from requirement
    assert fa_node["nodeId"] in visited

    # Walk role → FA (derives-from), electrical → role (supports), physical → electrical
    role_up = kernel.graph.reader.get_downstream(
        project_id, role_node["nodeId"], max_depth=2, max_nodes=20, max_edges=20
    )
    assert fa_node["nodeId"] in {n["nodeId"] for n in role_up["nodes"]}

    e_down = kernel.graph.reader.get_downstream(
        project_id, e_node["nodeId"], max_depth=2, max_nodes=20, max_edges=20
    )
    assert role_node["nodeId"] in {n["nodeId"] for n in e_down["nodes"]}

    p_down = kernel.graph.reader.get_downstream(
        project_id, p_node["nodeId"], max_depth=2, max_nodes=20, max_edges=20
    )
    assert e_node["nodeId"] in {n["nodeId"] for n in p_down["nodes"]}

    # Idempotent upsert
    again = materialize_layered_architecture_graph(
        kernel_store,
        project_id,
        artifacts,
        new_id("evt"),
    )
    assert again["createdNodes"] == 0
    assert again["createdEdges"] == 0
    _ = project_store  # keep fixture store referenced for clarity
