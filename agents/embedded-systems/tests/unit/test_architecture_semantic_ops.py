"""Unit tests for Electrical/Physical draft semantic ops."""

from __future__ import annotations

from typing import Any, cast

import pytest
from nexus_embedded_systems.workflows.layered_architecture.semantic_ops import (
    apply_electrical_semantic_op,
    apply_physical_semantic_op,
)


def _electrical_base() -> dict:
    return {
        "architectureId": "earch_TESTELECTRICAL0001",
        "maturity": "provisional",
        "summary": "test",
        "nodes": [
            {
                "nodeId": "enode_BOUNDROLE0000000001",
                "name": "Bound sensor",
                "nodeType": "component",
                "functionalArchitectureNodeIds": ["node_FA0000000000000001"],
                "componentRoleIds": ["role_BOUND0000000000001"],
                "implementationStatus": "provisional",
                "evidenceStatus": "unverified",
                "interfaces": [],
                "requirementIds": [],
            }
        ],
        "connections": [],
        "powerDomains": [],
        "assumptions": [],
        "unresolvedDecisions": [],
        "warnings": [],
        "coverageSummary": {
            "totalFunctionalNodes": 1,
            "coveredFunctionalNodes": 1,
            "uncoveredFunctionalNodeIds": [],
            "preferredImplementationCount": 1,
            "approvedImplementationCount": 0,
            "unresolvedImplementationCount": 0,
            "unresolvedConnectionCount": 0,
        },
        "evidenceStatus": "unverified",
        "selectionBasisSummary": "test",
    }


def test_add_and_delete_supporting_electrical_node() -> None:
    base = _electrical_base()
    with_support = apply_electrical_semantic_op(
        base, {"type": "add-supporting-node", "name": "TVS diode"}
    )
    assert len(with_support["nodes"]) == 2
    support = next(n for n in with_support["nodes"] if n["name"] == "TVS diode")
    assert support["componentRoleIds"] == []
    cleaned = apply_electrical_semantic_op(
        with_support, {"type": "delete-supporting-node", "nodeId": support["nodeId"]}
    )
    assert len(cleaned["nodes"]) == 1


def test_cannot_delete_role_bound_electrical_node() -> None:
    base = _electrical_base()
    with pytest.raises(ValueError, match="Component Plan"):
        apply_electrical_semantic_op(
            base,
            {"type": "delete-supporting-node", "nodeId": "enode_BOUNDROLE0000000001"},
        )


def test_electrical_connection_ops() -> None:
    base = _electrical_base()
    base = apply_electrical_semantic_op(base, {"type": "add-supporting-node", "name": "MCU"})
    support_id = next(n["nodeId"] for n in base["nodes"] if n["name"] == "MCU")
    with_conn = apply_electrical_semantic_op(
        base,
        {
            "type": "add-connection",
            "fromNodeId": "enode_BOUNDROLE0000000001",
            "toNodeId": support_id,
            "connectionType": "bus",
            "interfaceType": "i2c",
        },
    )
    assert len(with_conn["connections"]) == 1
    conn_id = with_conn["connections"][0]["connectionId"]
    changed = apply_electrical_semantic_op(
        with_conn,
        {
            "type": "change-connection",
            "connectionId": conn_id,
            "interfaceType": "spi",
            "status": "provisional",
        },
    )
    assert changed["connections"][0]["interfaceType"] == "spi"
    deleted = apply_electrical_semantic_op(
        changed, {"type": "delete-connection", "connectionId": conn_id}
    )
    assert deleted["connections"] == []


def test_physical_zone_and_relationship_ops() -> None:
    content: dict[str, Any] = {
        "architectureId": "parch_TESTPHYSICAL000001",
        "maturity": "provisional",
        "summary": "test",
        "nodes": [],
        "zones": [],
        "relationships": [],
        "assumptions": [],
        "unresolvedDecisions": [],
        "warnings": [],
        "coverageSummary": {
            "totalElectricalNodes": 0,
            "coveredElectricalNodes": 0,
            "uncoveredElectricalNodeIds": [],
            "unresolvedPlacementCount": 0,
            "provisionalRelationshipCount": 0,
        },
        "evidenceStatus": "unverified",
    }
    content = apply_physical_semantic_op(content, {"type": "add-zone", "name": "Enclosure"})
    zones = cast(list[dict[str, Any]], content["zones"])
    zone_id = cast(str, zones[0]["zoneId"])
    content = apply_physical_semantic_op(
        content, {"type": "add-entity", "name": "Board", "nodeType": "board"}
    )
    nodes = cast(list[dict[str, Any]], content["nodes"])
    board_id = cast(str, nodes[0]["nodeId"])
    content = apply_physical_semantic_op(
        content,
        {
            "type": "assign-zone",
            "nodeId": board_id,
            "zoneId": zone_id,
            "qualitativePlacement": "Inside enclosure",
        },
    )
    nodes = cast(list[dict[str, Any]], content["nodes"])
    assert nodes[0]["zoneId"] == zone_id
    content = apply_physical_semantic_op(
        content,
        {
            "type": "add-entity",
            "name": "Sensor module",
            "nodeType": "sensor",
        },
    )
    nodes = cast(list[dict[str, Any]], content["nodes"])
    sensor_id = next(cast(str, n["nodeId"]) for n in nodes if n["name"] == "Sensor module")
    content = apply_physical_semantic_op(
        content,
        {
            "type": "add-relationship",
            "fromNodeId": sensor_id,
            "toNodeId": board_id,
            "relationshipType": "mounted-on",
        },
    )
    assert len(cast(list[Any], content["relationships"])) == 1
    content = apply_physical_semantic_op(
        content,
        {
            "type": "edit-placement",
            "nodeId": sensor_id,
            "qualitativePlacement": "External sensing face",
            "constraints": ["keep vents clear"],
            "placementStatus": "provisional",
        },
    )
    nodes = cast(list[dict[str, Any]], content["nodes"])
    sensor = next(n for n in nodes if n["nodeId"] == sensor_id)
    assert sensor["constraints"] == ["keep vents clear"]
