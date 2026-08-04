"""Project graph readers with traversal bounds."""

from __future__ import annotations

from collections import deque
from typing import Any, Literal, Protocol

from nexus_board.errors import GraphBoundExceededError
from nexus_board.ids import new_id, utc_now_iso


class ProjectGraphReader(Protocol):
    def get_neighbors(
        self,
        project_id: str,
        node_id: str,
        *,
        direction: Literal["outbound", "inbound", "both"] = "both",
        max_nodes: int = 100,
        max_edges: int = 200,
    ) -> dict[str, Any]: ...

    def get_downstream(
        self,
        project_id: str,
        root_node_id: str,
        *,
        max_depth: int = 5,
        max_nodes: int = 100,
        max_edges: int = 200,
    ) -> dict[str, Any]: ...

    def get_upstream(
        self,
        project_id: str,
        root_node_id: str,
        *,
        max_depth: int = 5,
        max_nodes: int = 100,
        max_edges: int = 200,
    ) -> dict[str, Any]: ...

    def get_subgraph(
        self,
        project_id: str,
        root_node_id: str,
        *,
        direction: Literal["outbound", "inbound", "both"] = "both",
        max_depth: int = 5,
        max_nodes: int = 100,
        max_edges: int = 200,
    ) -> dict[str, Any]: ...


class _GraphStore(Protocol):
    def list_graph_nodes(self, project_id: str) -> list[dict[str, Any]]: ...

    def list_graph_edges(self, project_id: str) -> list[dict[str, Any]]: ...

    def get_graph_node(self, node_id: str) -> dict[str, Any] | None: ...

    def create_graph_node(self, node: dict[str, Any]) -> None: ...

    def create_graph_edge(self, edge: dict[str, Any]) -> None: ...


class InMemoryProjectGraphReader:
    def __init__(self, store: _GraphStore) -> None:
        self._store = store

    def get_neighbors(
        self,
        project_id: str,
        node_id: str,
        *,
        direction: Literal["outbound", "inbound", "both"] = "both",
        max_nodes: int = 100,
        max_edges: int = 200,
    ) -> dict[str, Any]:
        return self.get_subgraph(
            project_id,
            node_id,
            direction=direction,
            max_depth=1,
            max_nodes=max_nodes,
            max_edges=max_edges,
        )

    def get_downstream(
        self,
        project_id: str,
        root_node_id: str,
        *,
        max_depth: int = 5,
        max_nodes: int = 100,
        max_edges: int = 200,
    ) -> dict[str, Any]:
        return self.get_subgraph(
            project_id,
            root_node_id,
            direction="outbound",
            max_depth=max_depth,
            max_nodes=max_nodes,
            max_edges=max_edges,
        )

    def get_upstream(
        self,
        project_id: str,
        root_node_id: str,
        *,
        max_depth: int = 5,
        max_nodes: int = 100,
        max_edges: int = 200,
    ) -> dict[str, Any]:
        return self.get_subgraph(
            project_id,
            root_node_id,
            direction="inbound",
            max_depth=max_depth,
            max_nodes=max_nodes,
            max_edges=max_edges,
        )

    def get_subgraph(
        self,
        project_id: str,
        root_node_id: str,
        *,
        direction: Literal["outbound", "inbound", "both"] = "both",
        max_depth: int = 5,
        max_nodes: int = 100,
        max_edges: int = 200,
    ) -> dict[str, Any]:
        nodes = {n["nodeId"]: n for n in self._store.list_graph_nodes(project_id)}
        edges = self._store.list_graph_edges(project_id)
        if root_node_id not in nodes:
            return {
                "schemaVersion": "1.0.0",
                "projectId": project_id,
                "rootNodeId": root_node_id,
                "direction": direction,
                "maxDepth": max_depth,
                "nodes": [],
                "edges": [],
                "truncated": False,
                "cycleDetected": False,
            }

        outbound: dict[str, list[dict[str, Any]]] = {}
        inbound: dict[str, list[dict[str, Any]]] = {}
        for edge in edges:
            outbound.setdefault(edge["sourceNodeId"], []).append(edge)
            inbound.setdefault(edge["targetNodeId"], []).append(edge)

        visited: set[str] = set()
        result_nodes: list[dict[str, Any]] = []
        result_edges: list[dict[str, Any]] = []
        truncated = False
        cycle_detected = False
        queue: deque[tuple[str, int]] = deque([(root_node_id, 0)])
        visited.add(root_node_id)
        result_nodes.append(nodes[root_node_id])

        while queue:
            current, depth = queue.popleft()
            candidates: list[dict[str, Any]] = []
            if direction in {"outbound", "both"}:
                candidates.extend(outbound.get(current, []))
            if direction in {"inbound", "both"}:
                candidates.extend(inbound.get(current, []))
            for edge in candidates:
                nxt = (
                    edge["targetNodeId"]
                    if edge["sourceNodeId"] == current
                    else edge["sourceNodeId"]
                )
                if nxt in visited:
                    cycle_detected = True
                    continue
                if depth >= max_depth:
                    truncated = truncated or bool(candidates)
                    continue
                if len(result_edges) >= max_edges:
                    truncated = True
                    break
                if nxt not in nodes:
                    continue
                if len(result_nodes) >= max_nodes:
                    truncated = True
                    break
                visited.add(nxt)
                result_nodes.append(nodes[nxt])
                result_edges.append(edge)
                queue.append((nxt, depth + 1))
            if truncated and len(result_edges) >= max_edges:
                break

        if truncated and (len(result_nodes) > max_nodes or len(result_edges) > max_edges):
            raise GraphBoundExceededError("Graph traversal exceeded configured bounds.")

        return {
            "schemaVersion": "1.0.0",
            "projectId": project_id,
            "rootNodeId": root_node_id,
            "direction": direction,
            "maxDepth": max_depth,
            "nodes": result_nodes,
            "edges": result_edges,
            "truncated": truncated,
            "cycleDetected": cycle_detected,
        }


PostgresProjectGraphReader = InMemoryProjectGraphReader


class ProjectGraphService:
    def __init__(self, store: _GraphStore, reader: ProjectGraphReader | None = None) -> None:
        self._store = store
        self.reader = reader or InMemoryProjectGraphReader(store)

    def ensure_artifact_node(
        self,
        *,
        project_id: str,
        artifact_id: str,
        artifact_type: str,
        created_by_event_id: str,
    ) -> dict[str, Any]:
        for node in self._store.list_graph_nodes(project_id):
            if node.get("refId") == artifact_id and node.get("nodeType") == "artifact":
                return node
        node = {
            "schemaVersion": "1.0.0",
            "nodeId": new_id("gnode"),
            "projectId": project_id,
            "nodeType": "artifact",
            "refId": artifact_id,
            "label": artifact_type,
            "createdByEventId": created_by_event_id,
            "createdAt": utc_now_iso(),
        }
        self._store.create_graph_node(node)
        return node

    def link_supersedes(
        self,
        *,
        project_id: str,
        from_artifact_id: str,
        to_artifact_id: str,
        created_by_event_id: str,
    ) -> dict[str, Any] | None:
        nodes = {n.get("refId"): n for n in self._store.list_graph_nodes(project_id)}
        source = nodes.get(from_artifact_id)
        target = nodes.get(to_artifact_id)
        if source is None or target is None:
            return None
        edge = {
            "schemaVersion": "1.0.0",
            "edgeId": new_id("gedge"),
            "projectId": project_id,
            "sourceNodeId": source["nodeId"],
            "targetNodeId": target["nodeId"],
            "edgeType": "supersedes",
            "createdByEventId": created_by_event_id,
            "validFrom": utc_now_iso(),
        }
        self._store.create_graph_edge(edge)
        return edge
