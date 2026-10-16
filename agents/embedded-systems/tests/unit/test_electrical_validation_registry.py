"""Electrical Architecture validation registry unit tests."""

from __future__ import annotations

from nexus_embedded_systems.workflows.layered_architecture.validation.electrical_rules import (
    RULE_INTERFACE_COMPATIBILITY,
    RULE_MISSING_POWER_SOURCE,
    RULE_PROVISIONAL_SELECTION,
    RULE_UNRESOLVED_INTERFACE,
    RULE_UNRESOLVED_POWER_DOMAIN,
    RULE_VOLTAGE_DOMAIN_COMPATIBILITY,
    build_default_electrical_validation_registry,
    run_electrical_validation,
)
from nexus_embedded_systems.workflows.layered_architecture.validation.registry import (
    ElectricalValidationRegistry,
    rule_results_to_warnings,
)
from nexus_embedded_systems.workflows.layered_architecture.validation.rules import (
    make_rule_result,
)


def _base_content() -> dict:
    return {
        "nodes": [
            {
                "nodeId": "enode_AAAAAAAAAAAAAAAA",
                "name": "MCU",
                "nodeType": "component",
                "implementationStatus": "approved",
                "interfaces": [
                    {
                        "interfaceId": "eiface_AAAAAAAAAAAAAAAA",
                        "interfaceType": "i2c",
                        "direction": "bidirectional",
                        "status": "resolved",
                        "label": "I2C",
                    },
                    {
                        "interfaceId": "eiface_BBBBBBBBBBBBBBBB",
                        "interfaceType": "power",
                        "direction": "in",
                        "status": "resolved",
                        "label": "supply",
                        "voltage": {"schemaVersion": "1.0.0", "value": 3.3, "unit": "V"},
                    },
                ],
            },
            {
                "nodeId": "enode_BBBBBBBBBBBBBBBB",
                "name": "Sensor",
                "nodeType": "component",
                "implementationStatus": "approved",
                "interfaces": [
                    {
                        "interfaceId": "eiface_CCCCCCCCCCCCCCCC",
                        "interfaceType": "i2c",
                        "direction": "bidirectional",
                        "status": "resolved",
                        "label": "I2C",
                    },
                    {
                        "interfaceId": "eiface_DDDDDDDDDDDDDDDD",
                        "interfaceType": "power",
                        "direction": "in",
                        "status": "resolved",
                        "label": "supply",
                        "voltage": {"schemaVersion": "1.0.0", "value": 3.3, "unit": "V"},
                    },
                ],
            },
        ],
        "connections": [
            {
                "connectionId": "econn_AAAAAAAAAAAAAAAA",
                "fromNodeId": "enode_AAAAAAAAAAAAAAAA",
                "toNodeId": "enode_BBBBBBBBBBBBBBBB",
                "connectionType": "signal",
                "interfaceType": "i2c",
                "status": "resolved",
                "fromInterfaceId": "eiface_AAAAAAAAAAAAAAAA",
                "toInterfaceId": "eiface_CCCCCCCCCCCCCCCC",
            }
        ],
        "powerDomains": [
            {
                "powerDomainId": "epwr_AAAAAAAAAAAAAAAA",
                "name": "3.3 V rail",
                "status": "known",
                "nominalVoltage": {"schemaVersion": "1.0.0", "value": 3.3, "unit": "V"},
                "memberNodeIds": ["enode_AAAAAAAAAAAAAAAA", "enode_BBBBBBBBBBBBBBBB"],
            }
        ],
    }


def test_registry_dispatches_all_default_rules() -> None:
    registry = build_default_electrical_validation_registry()
    assert registry.rule_ids == [
        RULE_INTERFACE_COMPATIBILITY,
        RULE_VOLTAGE_DOMAIN_COMPATIBILITY,
        RULE_UNRESOLVED_INTERFACE,
        RULE_MISSING_POWER_SOURCE,
        RULE_UNRESOLVED_POWER_DOMAIN,
        RULE_PROVISIONAL_SELECTION,
    ]
    results = registry.run_all(_base_content())
    rule_ids = {r["ruleId"] for r in results}
    assert rule_ids == set(registry.rule_ids)
    assert all(r["status"] in {"pass", "not-applicable"} for r in results)


def test_interface_compatibility_mismatch_is_deterministic() -> None:
    content = _base_content()
    content["nodes"][1]["interfaces"][0]["interfaceType"] = "spi"
    content["connections"][0]["status"] = "needs-resolution"
    first = run_electrical_validation(content)
    second = run_electrical_validation(content)
    mismatches = [r for r in first if r["ruleId"] == RULE_INTERFACE_COMPATIBILITY]
    assert len(mismatches) == 1
    assert mismatches[0]["status"] == "fail"
    assert mismatches[0]["severity"] == "blocking"
    assert first == second


def test_voltage_domain_conflict_warning() -> None:
    content = _base_content()
    content["nodes"][1]["interfaces"][1]["voltage"]["value"] = 5.0
    results = run_electrical_validation(content)
    voltage = [r for r in results if r["ruleId"] == RULE_VOLTAGE_DOMAIN_COMPATIBILITY]
    assert len(voltage) == 1
    assert voltage[0]["status"] == "warning"
    assert "5.0" in voltage[0]["message"]


def test_unresolved_interface_and_power_domain_rules() -> None:
    content = _base_content()
    content["nodes"][0]["interfaces"][0]["status"] = "needs-resolution"
    content["powerDomains"][0]["status"] = "unknown"
    results = run_electrical_validation(content)
    unresolved_ifaces = [r for r in results if r["ruleId"] == RULE_UNRESOLVED_INTERFACE]
    unresolved_domains = [r for r in results if r["ruleId"] == RULE_UNRESOLVED_POWER_DOMAIN]
    missing_source = [r for r in results if r["ruleId"] == RULE_MISSING_POWER_SOURCE]
    assert unresolved_ifaces[0]["status"] == "warning"
    assert unresolved_domains[0]["status"] == "warning"
    assert missing_source[0]["status"] == "warning"


def test_provisional_selection_severity() -> None:
    content = _base_content()
    content["nodes"][0]["implementationStatus"] = "provisional"
    content["nodes"][1]["implementationStatus"] = "preferred"
    results = [
        r for r in run_electrical_validation(content) if r["ruleId"] == RULE_PROVISIONAL_SELECTION
    ]
    by_node = {r["subjectEntityIds"][0]: r for r in results}
    assert by_node["enode_AAAAAAAAAAAAAAAA"]["severity"] == "warning"
    assert by_node["enode_BBBBBBBBBBBBBBBB"]["severity"] == "info"


def test_rule_results_map_to_warnings() -> None:
    warnings = rule_results_to_warnings(
        [
            make_rule_result(
                rule_id=RULE_PROVISIONAL_SELECTION,
                status="warning",
                severity="info",
                message="preferred",
                subject_entity_ids=["enode_AAAAAAAAAAAAAAAA", "eiface_AAAAAAAAAAAAAAAA"],
            ),
            make_rule_result(
                rule_id=RULE_INTERFACE_COMPATIBILITY,
                status="pass",
                severity="info",
                message="ok",
            ),
        ]
    )
    assert warnings == [
        {
            "code": RULE_PROVISIONAL_SELECTION,
            "message": "preferred",
            "severity": "info",
            "relatedNodeIds": ["enode_AAAAAAAAAAAAAAAA"],
        }
    ]


def test_registry_rejects_duplicate_registration() -> None:
    registry = ElectricalValidationRegistry()

    class _Rule:
        rule_id = "elec.test"

        def evaluate(self, content: dict) -> list:
            return []

    registry.register(_Rule())
    try:
        registry.register(_Rule())
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "already registered" in str(exc)
