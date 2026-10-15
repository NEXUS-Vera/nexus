"""Layered Architecture composition unit tests (Phase 13A)."""

from __future__ import annotations

from copy import deepcopy

import pytest
from nexus_embedded_systems.workflows.component_planning import (
    apply_component_plan_operation,
    compose_component_plan_content,
)
from nexus_embedded_systems.workflows.component_planning.reconcile import (
    reconcile_component_plan_after_architecture_change,
)
from nexus_embedded_systems.workflows.layered_architecture import (
    apply_functional_node_removal,
    compose_electrical_architecture_content,
    compose_physical_architecture_content,
    inspect_functional_node_deletion_impact,
    normalize_candidate_specifications,
)
from nexus_embedded_systems.workflows.layered_architecture.normalize_specs import (
    normalize_interface_value,
)


def _greenhouse_architecture() -> dict:
    return {
        "systemBoundary": "Greenhouse enclosure and local sensing environment",
        "summary": "Greenhouse environmental sensing node",
        "nodes": [
            {
                "nodeId": "node_SENSINGNODE0000000001",
                "name": "Environmental sensing",
                "functionalType": "sensing",
                "description": "Acquire temperature and humidity",
                "responsibilities": ["Measure ambient temperature", "Measure humidity"],
                "satisfiesRequirementIds": ["req_TEMPREQUIREMENT00001"],
            },
            {
                "nodeId": "node_COMPUTENODE0000000001",
                "name": "Local compute",
                "functionalType": "compute",
                "description": "Process and store readings",
                "responsibilities": ["Sample sensors", "Buffer readings"],
                "satisfiesRequirementIds": [],
            },
        ],
        "edges": [
            {
                "edgeId": "edge_SENSINGTOCOMPUTE00001",
                "fromNodeId": "node_SENSINGNODE0000000001",
                "toNodeId": "node_COMPUTENODE0000000001",
                "flowType": "data",
                "description": "Sensor readings to MCU",
            }
        ],
    }


def _greenhouse_requirements() -> dict:
    return {
        "requirements": [
            {
                "requirementId": "req_TEMPREQUIREMENT00001",
                "statement": "Measure greenhouse temperature accurately",
                "category": "performance",
                "confirmationStatus": "confirmed",
            }
        ]
    }


def test_compose_electrical_from_fa_and_plan() -> None:
    architecture = _greenhouse_architecture()
    plan = compose_component_plan_content(
        architecture_content=architecture,
        requirement_set_content=_greenhouse_requirements(),
        include_candidates=True,
    )
    electrical = compose_electrical_architecture_content(
        architecture_content=architecture,
        component_plan_content=plan,
    )
    assert electrical["nodes"]
    assert electrical["coverageSummary"]["totalFunctionalNodes"] == 2
    assert electrical["coverageSummary"]["preferredImplementationCount"] >= 1
    assert all(n["nodeId"].startswith("enode_") for n in electrical["nodes"])


def test_preferred_vs_approved_implementation_status() -> None:
    architecture = _greenhouse_architecture()
    plan = compose_component_plan_content(
        architecture_content=architecture,
        requirement_set_content=_greenhouse_requirements(),
        include_candidates=True,
    )
    preferred = compose_electrical_architecture_content(
        architecture_content=architecture,
        component_plan_content=plan,
    )
    assert preferred["coverageSummary"]["preferredImplementationCount"] >= 1

    candidate_id = plan["candidates"][0]["candidateId"]
    approved_plan = apply_component_plan_operation(
        plan,
        operation="approve-component-selection",
        message="Approve the fixture candidate",
        architecture_content=architecture,
        target_candidate_id=candidate_id,
    )
    approved = compose_electrical_architecture_content(
        architecture_content=architecture,
        component_plan_content=approved_plan,
    )
    assert approved["coverageSummary"]["approvedImplementationCount"] >= 1
    assert any(n.get("implementationStatus") == "approved" for n in approved["nodes"])


def test_electrical_identity_preservation_on_recompose() -> None:
    architecture = _greenhouse_architecture()
    plan = compose_component_plan_content(
        architecture_content=architecture,
        requirement_set_content=_greenhouse_requirements(),
        include_candidates=True,
    )
    first = compose_electrical_architecture_content(
        architecture_content=architecture,
        component_plan_content=plan,
    )
    prior_ids = {
        (n["componentRoleIds"][0], n["nodeId"]) for n in first["nodes"] if n.get("componentRoleIds")
    }
    second = compose_electrical_architecture_content(
        architecture_content=architecture,
        component_plan_content=plan,
        previous_content=first,
    )
    assert second["architectureId"] == first["architectureId"]
    for role_id, node_id in prior_ids:
        match = next(n for n in second["nodes"] if role_id in (n.get("componentRoleIds") or []))
        assert match["nodeId"] == node_id


def test_physical_from_electrical_preserves_identity() -> None:
    architecture = _greenhouse_architecture()
    plan = compose_component_plan_content(
        architecture_content=architecture,
        requirement_set_content=_greenhouse_requirements(),
        include_candidates=True,
    )
    electrical = compose_electrical_architecture_content(
        architecture_content=architecture,
        component_plan_content=plan,
    )
    physical = compose_physical_architecture_content(
        electrical_content=electrical,
        project_context={
            "systemBoundary": architecture["systemBoundary"],
            "summary": architecture["summary"],
        },
    )
    assert physical["nodes"]
    assert physical["coverageSummary"]["totalElectricalNodes"] == len(electrical["nodes"])
    prior = {n["electricalNodeIds"][0]: n["nodeId"] for n in physical["nodes"]}
    recomposed = compose_physical_architecture_content(
        electrical_content=electrical,
        previous_content=physical,
        project_context={"systemBoundary": architecture["systemBoundary"]},
    )
    assert recomposed["architectureId"] == physical["architectureId"]
    for eid, pid in prior.items():
        match = next(n for n in recomposed["nodes"] if eid in (n.get("electricalNodeIds") or []))
        assert match["nodeId"] == pid


def test_normalize_specs_interface_aliases() -> None:
    specs = normalize_candidate_specifications(
        [
            {"specKey": "Interface", "value": "I2C"},
            {"specKey": "Supply Voltage", "value": 3.3, "unit": "V"},
            {"specKey": "unknown-key", "value": "x"},
        ]
    )
    assert normalize_interface_value(specs["specs"]["interface"]["value"]) == "i2c"
    assert normalize_interface_value("I²C") == "i2c"
    assert normalize_interface_value("SPI") == "spi"
    assert specs["otherSpecs"]


def test_fixture_derived_interfaces_include_provenance() -> None:
    architecture = _greenhouse_architecture()
    plan = compose_component_plan_content(
        architecture_content=architecture,
        requirement_set_content=_greenhouse_requirements(),
        include_candidates=True,
    )
    assert any(c.get("source") == "fixture" for c in plan["candidates"])
    electrical = compose_electrical_architecture_content(
        architecture_content=architecture,
        component_plan_content=plan,
    )
    fixture_ifaces = [
        iface
        for node in electrical["nodes"]
        for iface in (node.get("interfaces") or [])
        if (iface.get("provenance") or {}).get("sourceType") == "fixture"
    ]
    assert fixture_ifaces
    for iface in fixture_ifaces:
        provenance = iface["provenance"]
        assert provenance["schemaVersion"] == "1.0.0"
        assert provenance["derivedFromIds"]
        assert all(isinstance(i, str) and i for i in provenance["derivedFromIds"])

    assert electrical["connections"]
    for conn in electrical["connections"]:
        assert "provenance" in conn
        assert conn["provenance"]["sourceType"] in {"fixture", "component-plan"}

    validation_codes = {
        w["code"] for w in electrical["warnings"] if str(w["code"]).startswith("elec.")
    }
    assert validation_codes

    physical = compose_physical_architecture_content(electrical_content=electrical)
    for node in physical["nodes"]:
        provenance = node["provenance"]
        assert provenance["sourceType"] == "derived"
        assert provenance["derivedFromIds"] == node["electricalNodeIds"]


def test_inspect_functional_node_deletion_reports_dependents() -> None:
    architecture = _greenhouse_architecture()
    architecture["requirementCoverage"] = {"coveredRequirementIds": ["req_TEMPREQUIREMENT00001"]}
    plan = compose_component_plan_content(
        architecture_content=architecture,
        requirement_set_content=_greenhouse_requirements(),
        include_candidates=True,
    )
    electrical = compose_electrical_architecture_content(
        architecture_content=architecture,
        component_plan_content=plan,
    )
    physical = compose_physical_architecture_content(electrical_content=electrical)
    target = "node_SENSINGNODE0000000001"
    unrelated_roles = [
        r["componentRoleId"]
        for r in plan["componentRoles"]
        if target not in (r.get("architectureNodeIds") or [])
    ]
    assert unrelated_roles

    impact = inspect_functional_node_deletion_impact(
        node_id=target,
        functional_content=architecture,
        component_plan_content=plan,
        electrical_content=electrical,
        physical_content=physical,
    )
    assert impact["blocking"] is True
    assert impact["targetEntityId"] == target
    assert impact["affectedComponentRoleIds"]
    assert impact["affectedElectricalNodeIds"]
    assert impact["affectedRequirementIds"] == ["req_TEMPREQUIREMENT00001"]
    for role_id in unrelated_roles:
        assert role_id not in impact["affectedComponentRoleIds"]

    removed = apply_functional_node_removal(architecture, target)
    assert all(n["nodeId"] != target for n in removed["nodes"])
    assert all(
        e.get("fromNodeId") != target and e.get("toNodeId") != target for e in removed["edges"]
    )
    assert "req_TEMPREQUIREMENT00001" not in (removed.get("requirementCoverage") or {}).get(
        "coveredRequirementIds", []
    )
    surviving = {n["nodeId"] for n in removed["nodes"]}
    assert "node_COMPUTENODE0000000001" in surviving

    # Inspect / draft removal must not cascade-mutate downstream artifacts.
    electrical_snapshot = deepcopy(electrical)
    physical_snapshot = deepcopy(physical)
    plan_snapshot = deepcopy(plan)
    _ = inspect_functional_node_deletion_impact(
        node_id=target,
        functional_content=architecture,
        component_plan_content=plan,
        electrical_content=electrical,
        physical_content=physical,
    )
    assert electrical == electrical_snapshot
    assert physical == physical_snapshot
    assert plan == plan_snapshot
    # apply_functional_node_removal is FA-only (no silent downstream cascade).
    assert electrical == electrical_snapshot

    # Explicit remove-and-reconcile: recompose after FA removal preserves
    # unrelated Electrical / Physical identities via previous_content.
    recomposed_plan = reconcile_component_plan_after_architecture_change(
        plan,
        architecture_content=removed,
        requirement_set_content=_greenhouse_requirements(),
    )
    assert recomposed_plan["componentRoles"]
    assert all(
        target not in (r.get("architectureNodeIds") or [])
        for r in recomposed_plan["componentRoles"]
    )
    for role_id in unrelated_roles:
        assert any(r["componentRoleId"] == role_id for r in recomposed_plan["componentRoles"])

    recomposed_electrical = compose_electrical_architecture_content(
        architecture_content=removed,
        component_plan_content=recomposed_plan,
        previous_content=electrical,
    )
    kept_electrical_ids = {
        n["nodeId"]
        for n in electrical["nodes"]
        if target not in (n.get("functionalArchitectureNodeIds") or [])
        and not any(
            r in (n.get("componentRoleIds") or []) for r in impact["affectedComponentRoleIds"]
        )
    }
    recomposed_ids = {n["nodeId"] for n in recomposed_electrical["nodes"]}
    assert kept_electrical_ids.issubset(recomposed_ids)

    recomposed_physical = compose_physical_architecture_content(
        electrical_content=recomposed_electrical,
        previous_content=physical,
    )
    kept_physical_ids = {
        p["nodeId"]
        for p in physical["nodes"]
        if not set(p.get("electricalNodeIds") or []) & set(impact["affectedElectricalNodeIds"])
    }
    assert kept_physical_ids.issubset({n["nodeId"] for n in recomposed_physical["nodes"]})


@pytest.mark.parametrize("values", [((3.3, "V"), (3300, "mV")), ((3, "V"), (3.0, "V"))])
def test_voltage_domain_compatibility_normalizes_units(values) -> None:
    from nexus_embedded_systems.workflows.layered_architecture.compose_electrical import (
        _propose_power_domains,
    )
    from nexus_embedded_systems.workflows.layered_architecture.validation.electrical_rules import (
        _VoltageDomainCompatibilityRule,
    )

    nodes = [
        {
            "nodeId": f"node_{i}",
            "interfaces": [
                {
                    "interfaceType": "power",
                    "voltage": {"value": value, "unit": unit},
                }
            ],
        }
        for i, (value, unit) in enumerate(values)
    ]
    content = {
        "nodes": nodes,
        "powerDomains": [
            {
                "powerDomainId": "domain",
                "memberNodeIds": ["node_0", "node_1"],
            }
        ],
    }
    assert all(r["status"] == "pass" for r in _VoltageDomainCompatibilityRule().evaluate(content))
    assert len(_propose_power_domains(nodes)) == 1
    nodes[1]["interfaces"][0]["voltage"] = {"value": 5, "unit": "V"}
    assert any(
        r["status"] == "warning" for r in _VoltageDomainCompatibilityRule().evaluate(content)
    )
    assert len(_propose_power_domains(nodes)) == 2


def test_delete_supporting_node_removes_member_from_power_domains() -> None:
    from nexus_embedded_systems.workflows.layered_architecture.semantic_ops import (
        apply_electrical_semantic_op,
    )

    content = {
        "nodes": [
            {"nodeId": "support", "componentRoleIds": []},
            {"nodeId": "mcu", "componentRoleIds": ["role_mcu"]},
        ],
        "connections": [{"fromNodeId": "support", "toNodeId": "mcu"}],
        "powerDomains": [{"memberNodeIds": ["support", "mcu"]}],
    }
    updated = apply_electrical_semantic_op(
        content, {"type": "delete-supporting-node", "nodeId": "support"}
    )
    assert updated["powerDomains"][0]["memberNodeIds"] == ["mcu"]
    assert updated["connections"] == []
    assert content["powerDomains"][0]["memberNodeIds"] == ["support", "mcu"]
