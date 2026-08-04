"""Graph traversal bound tests."""

from __future__ import annotations

from helpers import build_test_kernel
from nexus_board.ids import new_id, utc_now_iso


def test_graph_cycle_and_depth_bounds() -> None:
    kernel, _, kernel_store, project_id = build_test_kernel()
    now = utc_now_iso()
    nodes = []
    for i in range(4):
        node = {
            "schemaVersion": "1.0.0",
            "nodeId": new_id("gnode"),
            "projectId": project_id,
            "nodeType": "artifact",
            "refId": new_id("art"),
            "label": f"n{i}",
            "createdByEventId": new_id("evt"),
            "createdAt": now,
        }
        kernel_store.create_graph_node(node)
        nodes.append(node)

    # A -> B -> C -> A cycle, plus A -> D
    edges = [
        (nodes[0], nodes[1]),
        (nodes[1], nodes[2]),
        (nodes[2], nodes[0]),
        (nodes[0], nodes[3]),
    ]
    for src, dst in edges:
        kernel_store.create_graph_edge(
            {
                "schemaVersion": "1.0.0",
                "edgeId": new_id("gedge"),
                "projectId": project_id,
                "sourceNodeId": src["nodeId"],
                "targetNodeId": dst["nodeId"],
                "edgeType": "depends-on",
                "createdByEventId": new_id("evt"),
                "validFrom": now,
            }
        )

    result = kernel.graph.reader.get_downstream(
        project_id,
        nodes[0]["nodeId"],
        max_depth=2,
        max_nodes=10,
        max_edges=10,
    )
    assert result["cycleDetected"] is True
    assert result["maxDepth"] == 2
    assert len(result["nodes"]) <= 10

    shallow = kernel.graph.reader.get_downstream(
        project_id,
        nodes[0]["nodeId"],
        max_depth=1,
        max_nodes=10,
        max_edges=10,
    )
    assert all(n["nodeId"] != nodes[2]["nodeId"] for n in shallow["nodes"])
