"""Built-in Electrical Architecture validation rules."""

from __future__ import annotations

from typing import Any, Literal

from nexus_embedded_systems.workflows.layered_architecture.normalize_specs import voltage_domain_key
from nexus_embedded_systems.workflows.layered_architecture.validation.registry import (
    ElectricalValidationRegistry,
    rule_results_to_warnings,
)
from nexus_embedded_systems.workflows.layered_architecture.validation.rules import (
    RuleResult,
    make_rule_result,
)

RULE_INTERFACE_COMPATIBILITY = "elec.interface-compatibility"
RULE_VOLTAGE_DOMAIN_COMPATIBILITY = "elec.voltage-domain-compatibility"
RULE_UNRESOLVED_INTERFACE = "elec.unresolved-interface"
RULE_MISSING_POWER_SOURCE = "elec.missing-power-source"
RULE_UNRESOLVED_POWER_DOMAIN = "elec.unresolved-power-domain"
RULE_PROVISIONAL_SELECTION = "elec.provisional-selection"


class _InterfaceCompatibilityRule:
    rule_id = RULE_INTERFACE_COMPATIBILITY

    def evaluate(self, content: dict[str, Any]) -> list[RuleResult]:
        nodes_by_id = {
            n["nodeId"]: n
            for n in (content.get("nodes") or [])
            if isinstance(n, dict) and isinstance(n.get("nodeId"), str)
        }
        results: list[RuleResult] = []
        for conn in content.get("connections") or []:
            if not isinstance(conn, dict):
                continue
            from_node = nodes_by_id.get(str(conn.get("fromNodeId") or ""))
            to_node = nodes_by_id.get(str(conn.get("toNodeId") or ""))
            if from_node is None or to_node is None:
                continue
            from_iface = _find_interface(from_node, conn.get("fromInterfaceId"))
            to_iface = _find_interface(to_node, conn.get("toInterfaceId"))
            if from_iface is None or to_iface is None:
                continue
            from_type = str(from_iface.get("interfaceType") or "unknown")
            to_type = str(to_iface.get("interfaceType") or "unknown")
            if from_type in {"unknown", "other"} or to_type in {"unknown", "other"}:
                continue
            if from_type == to_type:
                continue
            conn_id = str(conn.get("connectionId") or "")
            results.append(
                make_rule_result(
                    rule_id=self.rule_id,
                    status=("fail" if conn.get("status") == "needs-resolution" else "warning"),
                    severity=(
                        "blocking" if conn.get("status") == "needs-resolution" else "warning"
                    ),
                    message=(
                        f"Connection endpoints have incompatible interfaces "
                        f"({from_type} vs {to_type})."
                    ),
                    subject_entity_ids=[
                        str(conn.get("fromNodeId")),
                        str(conn.get("toNodeId")),
                        *([conn_id] if conn_id else []),
                    ],
                    details={
                        "fromInterfaceType": from_type,
                        "toInterfaceType": to_type,
                        "connectionId": conn_id or None,
                    },
                )
            )
        if not results:
            results.append(
                make_rule_result(
                    rule_id=self.rule_id,
                    status="pass",
                    severity="info",
                    message="No interface mismatches detected on connected endpoints.",
                )
            )
        return results


class _VoltageDomainCompatibilityRule:
    rule_id = RULE_VOLTAGE_DOMAIN_COMPATIBILITY

    def evaluate(self, content: dict[str, Any]) -> list[RuleResult]:
        nodes_by_id = {
            n["nodeId"]: n
            for n in (content.get("nodes") or [])
            if isinstance(n, dict) and isinstance(n.get("nodeId"), str)
        }
        results: list[RuleResult] = []
        for domain in content.get("powerDomains") or []:
            if not isinstance(domain, dict):
                continue
            voltages: dict[str, list[str]] = {}
            for member_id in domain.get("memberNodeIds") or []:
                if not isinstance(member_id, str):
                    continue
                node = nodes_by_id.get(member_id)
                if node is None:
                    continue
                for iface in node.get("interfaces") or []:
                    if not isinstance(iface, dict) or iface.get("interfaceType") != "power":
                        continue
                    voltage = iface.get("voltage")
                    if not isinstance(voltage, dict) or not isinstance(
                        voltage.get("value"), int | float
                    ):
                        continue
                    key = voltage_domain_key(voltage)
                    voltages.setdefault(key, []).append(member_id)
            if len(voltages) <= 1:
                continue
            domain_id = str(domain.get("powerDomainId") or "")
            subject = sorted({nid for nids in voltages.values() for nid in nids})
            if domain_id:
                subject.append(domain_id)
            results.append(
                make_rule_result(
                    rule_id=self.rule_id,
                    status="warning",
                    severity="warning",
                    message=(
                        f"Power domain '{domain.get('name') or domain_id}' contains "
                        f"conflicting supply voltages: {', '.join(sorted(voltages))}."
                    ),
                    subject_entity_ids=subject,
                    details={"voltages": voltages, "powerDomainId": domain_id or None},
                )
            )
        if not results:
            results.append(
                make_rule_result(
                    rule_id=self.rule_id,
                    status="pass",
                    severity="info",
                    message="No conflicting voltages detected within power domains.",
                )
            )
        return results


class _UnresolvedInterfaceRule:
    rule_id = RULE_UNRESOLVED_INTERFACE

    def evaluate(self, content: dict[str, Any]) -> list[RuleResult]:
        results: list[RuleResult] = []
        for node in content.get("nodes") or []:
            if not isinstance(node, dict):
                continue
            node_id = str(node.get("nodeId") or "")
            for iface in node.get("interfaces") or []:
                if not isinstance(iface, dict):
                    continue
                status = iface.get("status")
                if status not in {"unknown", "needs-resolution"}:
                    continue
                iface_id = str(iface.get("interfaceId") or "")
                results.append(
                    make_rule_result(
                        rule_id=self.rule_id,
                        status="warning",
                        severity="warning",
                        message=(
                            f"Interface '{iface.get('label') or iface_id}' on "
                            f"{node.get('name') or node_id} is {status}."
                        ),
                        subject_entity_ids=[
                            *([node_id] if node_id else []),
                            *([iface_id] if iface_id else []),
                        ],
                        details={"interfaceStatus": status},
                    )
                )
        if not results:
            results.append(
                make_rule_result(
                    rule_id=self.rule_id,
                    status="pass",
                    severity="info",
                    message="No unresolved interfaces.",
                )
            )
        return results


class _MissingPowerSourceRule:
    rule_id = RULE_MISSING_POWER_SOURCE

    def evaluate(self, content: dict[str, Any]) -> list[RuleResult]:
        domains = [d for d in (content.get("powerDomains") or []) if isinstance(d, dict)]
        unknown_domains = [d for d in domains if d.get("status") in {"unknown", "needs-resolution"}]
        if not unknown_domains:
            return [
                make_rule_result(
                    rule_id=self.rule_id,
                    status="not-applicable",
                    severity="info",
                    message="No unknown power domains; power-source check not applicable.",
                )
            ]
        nodes = [n for n in (content.get("nodes") or []) if isinstance(n, dict)]
        has_source = any(n.get("nodeType") in {"power-source", "power-regulator"} for n in nodes)
        if has_source:
            return [
                make_rule_result(
                    rule_id=self.rule_id,
                    status="pass",
                    severity="info",
                    message="Power source or regulator present for unknown power domain(s).",
                )
            ]
        subject = [
            str(d.get("powerDomainId"))
            for d in unknown_domains
            if isinstance(d.get("powerDomainId"), str)
        ]
        return [
            make_rule_result(
                rule_id=self.rule_id,
                status="warning",
                severity="warning",
                message=(
                    "Power domain(s) are unknown/needs-resolution and no "
                    "power-source or power-regulator node is present."
                ),
                subject_entity_ids=subject,
            )
        ]


class _UnresolvedPowerDomainRule:
    rule_id = RULE_UNRESOLVED_POWER_DOMAIN

    def evaluate(self, content: dict[str, Any]) -> list[RuleResult]:
        results: list[RuleResult] = []
        for domain in content.get("powerDomains") or []:
            if not isinstance(domain, dict):
                continue
            status = domain.get("status")
            if status not in {"unknown", "needs-resolution"}:
                continue
            domain_id = str(domain.get("powerDomainId") or "")
            members = [mid for mid in (domain.get("memberNodeIds") or []) if isinstance(mid, str)]
            results.append(
                make_rule_result(
                    rule_id=self.rule_id,
                    status="warning",
                    severity="warning",
                    message=(
                        f"Power domain '{domain.get('name') or domain_id}' status is {status}."
                    ),
                    subject_entity_ids=[*members, *([domain_id] if domain_id else [])],
                    details={"powerDomainStatus": status},
                )
            )
        if not results:
            results.append(
                make_rule_result(
                    rule_id=self.rule_id,
                    status="pass",
                    severity="info",
                    message="All power domains are resolved.",
                )
            )
        return results


class _ProvisionalSelectionRule:
    rule_id = RULE_PROVISIONAL_SELECTION

    def evaluate(self, content: dict[str, Any]) -> list[RuleResult]:
        results: list[RuleResult] = []
        for node in content.get("nodes") or []:
            if not isinstance(node, dict):
                continue
            status = node.get("implementationStatus")
            if status not in {"provisional", "preferred"}:
                continue
            node_id = str(node.get("nodeId") or "")
            severity: Literal["info", "warning"] = "warning" if status == "provisional" else "info"
            results.append(
                make_rule_result(
                    rule_id=self.rule_id,
                    status="warning",
                    severity=severity,
                    message=(f"Implementation for {node.get('name') or node_id} is {status}."),
                    subject_entity_ids=[node_id] if node_id else [],
                    details={"implementationStatus": status},
                )
            )
        if not results:
            results.append(
                make_rule_result(
                    rule_id=self.rule_id,
                    status="pass",
                    severity="info",
                    message="No provisional or preferred selections.",
                )
            )
        return results


def build_default_electrical_validation_registry() -> ElectricalValidationRegistry:
    registry = ElectricalValidationRegistry()
    for rule in (
        _InterfaceCompatibilityRule(),
        _VoltageDomainCompatibilityRule(),
        _UnresolvedInterfaceRule(),
        _MissingPowerSourceRule(),
        _UnresolvedPowerDomainRule(),
        _ProvisionalSelectionRule(),
    ):
        registry.register(rule)
    return registry


_DEFAULT_REGISTRY = build_default_electrical_validation_registry()


def run_electrical_validation(content: dict[str, Any]) -> list[RuleResult]:
    """Run all registered Electrical Architecture validation rules."""

    return _DEFAULT_REGISTRY.run_all(content)


def electrical_validation_warnings(content: dict[str, Any]) -> list[dict[str, Any]]:
    """Run validation and map non-pass results into warning objects."""

    return rule_results_to_warnings(run_electrical_validation(content))


def _find_interface(node: dict[str, Any], interface_id: Any) -> dict[str, Any] | None:
    if not isinstance(interface_id, str):
        return None
    for iface in node.get("interfaces") or []:
        if isinstance(iface, dict) and iface.get("interfaceId") == interface_id:
            return iface
    return None
