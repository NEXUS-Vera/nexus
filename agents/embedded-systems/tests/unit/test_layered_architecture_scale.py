"""Synthetic medium/large layered-architecture scale fixture and envelope tests."""

from __future__ import annotations

from nexus_board.services.architecture_graph import materialize_layered_architecture_graph
from nexus_embedded_systems.workflows.component_planning.compose import (
    compose_component_plan_content,
)
from nexus_embedded_systems.workflows.layered_architecture import (
    compose_electrical_architecture_content,
    compose_physical_architecture_content,
)
from nexus_embedded_systems.workflows.project_initialization.ids import new_id

# Documented Phase 13A operating envelope (engineering/test targets, not hard product limits).
SCALE_ENVELOPE = {
    "system": {"max_nodes": 50, "max_edges": 100},
    "electrical": {"max_nodes": 150, "max_connections": 300},
    "physical": {"max_nodes": 100, "max_relationships": 200},
    "project_graph": {"max_entities_and_edges": 1000},
}


def _build_scale_functional_architecture(*, node_count: int = 40) -> dict:
    """Build a synthetic functional architecture near the System envelope."""

    nodes = []
    edges = []
    req_ids = []
    for i in range(node_count):
        req_id = f"req_SCALE{i:020d}"
        req_ids.append(req_id)
        functional_type = (
            "sensing",
            "processing",
            "storage",
            "communication",
            "power",
            "control",
            "actuation",
            "user-interface",
        )[i % 8]
        node_id = f"node_SCALE{i:020d}"
        nodes.append(
            {
                "nodeId": node_id,
                "name": f"Block {i} ({functional_type})",
                "functionalType": functional_type,
                "responsibilities": [f"Responsibility for block {i}"],
                "satisfiesRequirementIds": [req_id],
            }
        )
        if i > 0:
            edges.append(
                {
                    "edgeId": f"edge_SCALE{i:020d}",
                    "fromNodeId": f"node_SCALE{i - 1:020d}",
                    "toNodeId": node_id,
                    "flowType": "data" if i % 3 else "control",
                    "description": f"Flow {i - 1}->{i}",
                }
            )
    return {
        "architectureId": "arch_SCALEFIXTURE00000001",
        "architectureMaturity": "functional",
        "systemBoundary": "Synthetic medium embedded sensing/control system for scale tests.",
        "nodes": nodes,
        "edges": edges,
        "assumptions": [],
        "unresolvedDecisions": [],
        "requirementCoverage": {"coveredRequirementIds": req_ids},
    }


def _requirement_set(fa: dict) -> dict:
    requirements = []
    for node in fa["nodes"]:
        for req_id in node["satisfiesRequirementIds"]:
            requirements.append(
                {
                    "requirementId": req_id,
                    "displayId": req_id[-4:],
                    "statement": f"Requirement for {node['name']}",
                    "category": "functional",
                    "priority": "must",
                    "sourceType": "system-inferred",
                    "sourceReference": {
                        "schemaVersion": "1.0.0",
                        "evidenceId": new_id("evi_"),
                        "sourceType": "agent-inference",
                        "sourceId": "turn_SCALE000000000001",
                        "evidenceStrength": "inferred",
                    },
                    "confidence": "medium",
                    "confirmationStatus": "proposed",
                    "verificationMethod": "Synthetic verification placeholder.",
                }
            )
    return {
        "requirements": requirements,
        "requirementSummary": "Synthetic scale requirement set.",
    }


class _MemoryGraphStore:
    def __init__(self) -> None:
        self.nodes: list[dict] = []
        self.edges: list[dict] = []

    def list_graph_nodes(self, project_id: str) -> list[dict]:
        return [n for n in self.nodes if n.get("projectId") == project_id]

    def list_graph_edges(self, project_id: str) -> list[dict]:
        return [e for e in self.edges if e.get("projectId") == project_id]

    def create_graph_node(self, node: dict) -> None:
        self.nodes.append(node)

    def create_graph_edge(self, edge: dict) -> None:
        self.edges.append(edge)


def test_scale_envelope_constants_documented() -> None:
    assert SCALE_ENVELOPE["system"]["max_nodes"] == 50
    assert SCALE_ENVELOPE["electrical"]["max_nodes"] == 150
    assert SCALE_ENVELOPE["project_graph"]["max_entities_and_edges"] == 1000


def test_synthetic_medium_project_composes_and_materializes() -> None:
    fa = _build_scale_functional_architecture(node_count=40)
    assert len(fa["nodes"]) <= SCALE_ENVELOPE["system"]["max_nodes"]
    assert len(fa["edges"]) <= SCALE_ENVELOPE["system"]["max_edges"]

    reqs = _requirement_set(fa)
    plan = compose_component_plan_content(
        architecture_content=fa,
        requirement_set_content=reqs,
        include_candidates=True,
        source="fixture",
    )
    electrical = compose_electrical_architecture_content(
        architecture_content=fa,
        component_plan_content=plan,
    )
    physical = compose_physical_architecture_content(
        electrical_content=electrical,
        project_context={"systemBoundary": fa["systemBoundary"]},
    )

    assert len(electrical["nodes"]) <= SCALE_ENVELOPE["electrical"]["max_nodes"]
    assert len(electrical["connections"]) <= SCALE_ENVELOPE["electrical"]["max_connections"]
    assert len(physical["nodes"]) <= SCALE_ENVELOPE["physical"]["max_nodes"]
    assert len(physical["relationships"]) <= SCALE_ENVELOPE["physical"]["max_relationships"]

    # Identity preservation on recompose
    electrical2 = compose_electrical_architecture_content(
        architecture_content=fa,
        component_plan_content=plan,
        previous_content=electrical,
    )
    by_role = {
        (n["componentRoleIds"] or [None])[0]: n["nodeId"]
        for n in electrical["nodes"]
        if n.get("componentRoleIds")
    }
    for node in electrical2["nodes"]:
        role_ids = node.get("componentRoleIds") or []
        if role_ids and role_ids[0] in by_role:
            assert node["nodeId"] == by_role[role_ids[0]]

    project_id = "proj_SCALEFIXTURE0000001"
    artifacts = [
        {
            "artifactId": "art_SCALEFA0000000000001",
            "artifactType": "functional-architecture",
            "artifactVersion": 1,
            "content": fa,
        },
        {
            "artifactId": "art_SCALECP0000000000001",
            "artifactType": "component-plan",
            "artifactVersion": 1,
            "content": plan,
        },
        {
            "artifactId": "art_SCALEEA0000000000001",
            "artifactType": "electrical-architecture",
            "artifactVersion": 1,
            "content": electrical,
        },
        {
            "artifactId": "art_SCALEPA0000000000001",
            "artifactType": "physical-architecture",
            "artifactVersion": 1,
            "content": physical,
        },
    ]
    # Attach requirement artifacts lightly for coverage edges if materializer needs them —
    # architecture_graph reads FA/plan/electrical/physical primarily.
    store = _MemoryGraphStore()
    materialize_layered_architecture_graph(
        store,
        project_id,
        artifacts,
        "evt_SCALE00000000000001",
    )
    total = len(store.nodes) + len(store.edges)
    assert total <= SCALE_ENVELOPE["project_graph"]["max_entities_and_edges"]
    assert store.nodes
    assert store.edges
