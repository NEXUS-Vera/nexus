"""Deterministic translation into a Wokwi provider workspace."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from .mappings import (
    WOKWI_ESP32_PROVIDER_PART,
    esp32_serial_monitor_connections,
    find_mapping,
)
from .types import (
    ArtifactEntityReference,
    ComponentMapping,
    Finding,
    FindingSeverity,
    MappingType,
    MaterializationRequest,
    ProviderWorkspace,
    SupportAssessment,
    SupportStatus,
)

_COORDINATES = {
    WOKWI_ESP32_PROVIDER_PART: (0, 0),
    "wokwi-mpu6050": (0, 320),
}


def _object(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _objects(value: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _content(artifact: Mapping[str, object]) -> Mapping[str, object]:
    nested = artifact.get("content")
    return _object(nested) if isinstance(nested, Mapping) else artifact


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def _reference(
    artifact: Mapping[str, object],
    *,
    entity_type: str,
    entity_id: str,
    display_label: str | None = None,
) -> ArtifactEntityReference:
    version = artifact.get("artifactVersion")
    return ArtifactEntityReference(
        artifact_id=_text(artifact.get("artifactId")) or "art_unknown",
        artifact_type=_text(artifact.get("artifactType")) or "other",
        artifact_version=version if isinstance(version, int) else None,
        entity_type=entity_type,
        entity_id=entity_id,
        display_label=display_label,
    )


def _selected_candidates(
    request: MaterializationRequest,
) -> tuple[
    list[tuple[Mapping[str, object], Mapping[str, object], Mapping[str, object]]],
    list[Finding],
]:
    plan = _content(request.component_plan)
    candidates = {
        _text(candidate.get("candidateId")): candidate
        for candidate in _objects(plan.get("candidates"))
        if _text(candidate.get("candidateId"))
    }
    decisions_by_role: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for decision in _objects(plan.get("selectionDecisions")):
        decisions_by_role[_text(decision.get("componentRoleId"))].append(decision)

    selected: list[tuple[Mapping[str, object], Mapping[str, object], Mapping[str, object]]] = []
    findings: list[Finding] = []
    for role in sorted(
        _objects(plan.get("componentRoles")),
        key=lambda item: _text(item.get("componentRoleId")),
    ):
        role_id = _text(role.get("componentRoleId"))
        refs = (
            _reference(
                request.component_plan,
                entity_type="component-role",
                entity_id=role_id or "unknown",
                display_label=_text(role.get("name")) or None,
            ),
        )
        decisions = decisions_by_role.get(role_id, [])
        candidate_ids = {
            _text(item.get("selectedCandidateId"))
            for item in decisions
            if _text(item.get("selectedCandidateId"))
        }
        if not candidate_ids:
            findings.append(
                Finding(
                    code="COMPONENT_UNSELECTED",
                    message=f"Component role {role_id or 'unknown'} has no selected candidate",
                    severity=FindingSeverity.WARNING,
                    references=refs,
                )
            )
            continue
        if len(candidate_ids) != 1 or len(decisions) != 1:
            findings.append(
                Finding(
                    code="COMPONENT_SELECTION_AMBIGUOUS",
                    message=f"Component role {role_id or 'unknown'} has ambiguous selections",
                    severity=FindingSeverity.ERROR,
                    references=refs,
                )
            )
            continue
        candidate_id = next(iter(candidate_ids))
        candidate = candidates.get(candidate_id)
        if candidate is None:
            findings.append(
                Finding(
                    code="SELECTED_COMPONENT_MISSING",
                    message=(
                        f"Selected candidate {candidate_id} is not present in the component plan"
                    ),
                    severity=FindingSeverity.ERROR,
                    references=refs,
                )
            )
            continue
        selected.append((role, candidate, decisions[0]))
    return selected, findings


def assess_support(request: MaterializationRequest) -> SupportAssessment:
    selected, findings = _selected_candidates(request)
    mappings: list[ComponentMapping] = []
    for _role, candidate, _decision in selected:
        mapping = find_mapping(
            source=_text(candidate.get("source")),
            manufacturer=_text(candidate.get("manufacturer")),
            part_number=_text(candidate.get("partNumber")),
        )
        if mapping is None:
            candidate_id = _text(candidate.get("candidateId")) or "unknown"
            findings.append(
                Finding(
                    code="COMPONENT_UNSUPPORTED",
                    message=f"Selected candidate {candidate_id} has no exact provider mapping",
                    severity=FindingSeverity.ERROR,
                    references=(
                        _reference(
                            request.component_plan,
                            entity_type="component-candidate",
                            entity_id=candidate_id,
                            display_label=_text(candidate.get("displayName")) or None,
                        ),
                    ),
                )
            )
            continue
        mappings.append(mapping)

    findings.extend(_validate_golden_interfaces(request, selected, mappings))
    has_errors = any(item.severity is FindingSeverity.ERROR for item in findings)
    if not mappings:
        status = SupportStatus.UNSUPPORTED
    elif has_errors or len(mappings) != len(selected):
        status = SupportStatus.PARTIALLY_SUPPORTED
    elif any(item.mapping_type is MappingType.SURROGATE for item in mappings):
        status = SupportStatus.SURROGATE_REQUIRED
    else:
        status = SupportStatus.SUPPORTED
    return SupportAssessment(status, tuple(mappings), tuple(findings))


def materialize_workspace(request: MaterializationRequest) -> ProviderWorkspace:
    selected, selection_findings = _selected_candidates(request)
    findings = list(selection_findings)
    architecture = _content(request.electrical_architecture)
    nodes = _objects(architecture.get("nodes"))
    diagram_parts: list[dict[str, object]] = []
    manifest_mappings: list[dict[str, object]] = []
    part_counts: dict[str, int] = defaultdict(int)
    part_ids_by_type: dict[str, list[str]] = defaultdict(list)
    provider_pin_profiles: dict[str, dict[str, str]] = {}

    for role, candidate, decision in sorted(
        selected, key=lambda item: _text(item[1].get("candidateId"))
    ):
        candidate_id = _text(candidate.get("candidateId"))
        role_id = _text(role.get("componentRoleId"))
        mapping = find_mapping(
            source=_text(candidate.get("source")),
            manufacturer=_text(candidate.get("manufacturer")),
            part_number=_text(candidate.get("partNumber")),
        )
        candidate_ref = _reference(
            request.component_plan,
            entity_type="component-candidate",
            entity_id=candidate_id or "unknown",
            display_label=_text(candidate.get("displayName")) or None,
        )
        if mapping is None or mapping.provider_part is None:
            findings.append(
                Finding(
                    code="COMPONENT_UNSUPPORTED",
                    message=(
                        f"Selected candidate {candidate_id or 'unknown'} "
                        "has no exact provider mapping"
                    ),
                    severity=FindingSeverity.ERROR,
                    references=(candidate_ref,),
                )
            )
            continue

        provider_pin_profiles[mapping.provider_part] = {
            pin.source_pin: pin.provider_pin for pin in mapping.pins
        }
        matching_nodes = [
            node
            for node in nodes
            if _text(node.get("componentCandidateId")) == candidate_id
            or (
                not _text(node.get("componentCandidateId"))
                and role_id in _strings(node.get("componentRoleIds"))
            )
        ]
        if len(matching_nodes) != 1:
            code = (
                "ELECTRICAL_NODE_UNSELECTED" if not matching_nodes else "ELECTRICAL_NODE_AMBIGUOUS"
            )
            findings.append(
                Finding(
                    code=code,
                    message=(
                        f"Selected candidate {candidate_id or 'unknown'} must map to "
                        "exactly one electrical node"
                    ),
                    severity=FindingSeverity.ERROR,
                    references=(candidate_ref,),
                )
            )
            continue

        node = matching_nodes[0]
        prefix = "mcu" if mapping.provider_part == WOKWI_ESP32_PROVIDER_PART else "imu"
        part_counts[prefix] += 1
        part_id = f"{prefix}{part_counts[prefix]}"
        part_ids_by_type[prefix].append(part_id)
        top, left = _COORDINATES[mapping.provider_part]
        diagram_parts.append(
            {
                "id": part_id,
                "type": mapping.provider_part,
                "top": top,
                "left": left,
                "attrs": {},
            }
        )
        node_ref = _reference(
            request.electrical_architecture,
            entity_type="electrical-node",
            entity_id=_text(node.get("nodeId")) or "unknown",
            display_label=_text(node.get("name")) or None,
        )
        decision_ref = _reference(
            request.component_plan,
            entity_type="selection-decision",
            entity_id=_text(decision.get("selectionDecisionId")) or "unknown",
        )
        manifest_mappings.append(
            {
                "providerPartId": part_id,
                "providerPartType": mapping.provider_part,
                "mappingType": mapping.mapping_type.value,
                "sourceReferences": [
                    candidate_ref.as_dict(),
                    decision_ref.as_dict(),
                    node_ref.as_dict(),
                ],
                "pinProfile": [
                    {
                        "sourcePin": pin.source_pin,
                        "providerPin": pin.provider_pin,
                    }
                    for pin in mapping.pins
                ],
            }
        )

    interface_findings = _validate_golden_interfaces(
        request,
        selected,
        [
            mapping
            for _role, candidate, _decision in selected
            if (
                mapping := find_mapping(
                    source=_text(candidate.get("source")),
                    manufacturer=_text(candidate.get("manufacturer")),
                    part_number=_text(candidate.get("partNumber")),
                )
            )
            is not None
        ],
    )
    findings.extend(interface_findings)
    connections: list[list[object]] = []
    if (
        not interface_findings
        and len(part_ids_by_type["mcu"]) == 1
        and len(part_ids_by_type["imu"]) == 1
    ):
        mcu = part_ids_by_type["mcu"][0]
        imu = part_ids_by_type["imu"][0]
        mcu_pins = provider_pin_profiles[WOKWI_ESP32_PROVIDER_PART]
        connections = [
            [f"{mcu}:{mcu_pins['3V3']}", f"{imu}:VCC", "red", []],
            [f"{mcu}:{mcu_pins['GND']}", f"{imu}:GND", "black", []],
            [f"{mcu}:{mcu_pins['21']}", f"{imu}:SDA", "green", []],
            [f"{mcu}:{mcu_pins['22']}", f"{imu}:SCL", "blue", []],
        ]
    if request.include_serial_monitor and len(part_ids_by_type["mcu"]) == 1:
        connections.extend(esp32_serial_monitor_connections(part_ids_by_type["mcu"][0]))

    diagram = {
        "version": 1,
        "author": "Nexus",
        "editor": "nexus",
        "parts": diagram_parts,
        "connections": connections,
        "dependencies": {},
    }
    manifest: dict[str, Any] = {
        "schemaVersion": "1.0.0",
        "capabilityId": "circuit-simulation",
        "providerId": "wokwi",
        "translatorVersion": "1.0.0",
        "canonicalSource": "nexus-electrical-architecture",
        "fidelity": "surrogate",
        "realComponentCompatibilityVerified": False,
        "mappings": manifest_mappings,
    }
    files = {
        "diagram.json": _json_bytes(diagram),
        "mapping-manifest.json": _json_bytes(manifest),
    }
    if request.include_wokwi_toml:
        files["wokwi.toml"] = (
            b'[wokwi]\nversion = 1\nfirmware = "firmware.elf"\nelf = "firmware.elf"\n'
        )
    return ProviderWorkspace(files=files, manifest=manifest, findings=tuple(findings))


def _validate_golden_interfaces(
    request: MaterializationRequest,
    selected: Sequence[tuple[Mapping[str, object], Mapping[str, object], Mapping[str, object]]],
    mappings: Sequence[ComponentMapping],
) -> list[Finding]:
    provider_parts = {mapping.provider_part for mapping in mappings}
    if not {
        "wokwi-esp32-devkit-v1",
        "wokwi-mpu6050",
    }.issubset(provider_parts):
        return []
    architecture = _content(request.electrical_architecture)
    nodes = _objects(architecture.get("nodes"))
    node_by_candidate = {
        _text(node.get("componentCandidateId")): node
        for node in nodes
        if _text(node.get("componentCandidateId"))
    }
    candidate_by_part: dict[str, Mapping[str, object]] = {}
    for _role, candidate, _decision in selected:
        mapping = find_mapping(
            source=_text(candidate.get("source")),
            manufacturer=_text(candidate.get("manufacturer")),
            part_number=_text(candidate.get("partNumber")),
        )
        if mapping and mapping.provider_part:
            candidate_by_part[mapping.provider_part] = candidate
    mcu = node_by_candidate.get(
        _text(candidate_by_part.get("wokwi-esp32-devkit-v1", {}).get("candidateId"))
    )
    imu = node_by_candidate.get(
        _text(candidate_by_part.get("wokwi-mpu6050", {}).get("candidateId"))
    )
    mcu_id = _text(mcu.get("nodeId")) if mcu else ""
    imu_id = _text(imu.get("nodeId")) if imu else ""
    node_interfaces_ok = _node_has_interface(mcu, "i2c") and _node_has_interface(imu, "i2c")
    connection_ok = any(
        _text(connection.get("interfaceType")).lower() == "i2c"
        and {
            _text(connection.get("fromNodeId")),
            _text(connection.get("toNodeId")),
        }
        == {mcu_id, imu_id}
        for connection in _objects(architecture.get("connections"))
    )
    if node_interfaces_ok and connection_ok:
        return []
    return [
        Finding(
            code="ELECTRICAL_INTERFACE_MISMATCH",
            message=(
                "Golden simulation requires an explicit I2C interface and connection "
                "between the selected FX-MCU-32 and FX-IMU-200 electrical nodes"
            ),
            severity=FindingSeverity.ERROR,
            references=(
                _reference(
                    request.electrical_architecture,
                    entity_type="electrical-architecture",
                    entity_id=_text(architecture.get("architectureId")) or "root",
                ),
            ),
        )
    ]


def _node_has_interface(
    node: Mapping[str, object] | None,
    interface_type: str,
) -> bool:
    if node is None:
        return False
    return any(
        _text(interface.get("interfaceType")).lower() == interface_type
        for interface in _objects(node.get("interfaces"))
    )


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
