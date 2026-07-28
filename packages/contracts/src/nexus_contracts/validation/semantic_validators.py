from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SemanticValidationError:
    code: str
    message: str
    path: str | None = None


_FORBIDDEN_VERA_REASONING_KEYS = {
    "hiddenReasoning",
    "chainOfThought",
    "chain_of_thought",
    "hiddenReasoningText",
    "internalReasoning",
}


def find_hidden_reasoning_fields(value: Any) -> list[str]:
    """
    Deterministically find forbidden reasoning-related keys inside a payload.

    This is stricter than JSON Schema because some hidden reasoning fields can be
    accidentally nested under allowed objects.
    """

    hits: list[str] = []

    def _walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                next_path = f"{path}.{k}" if path else k
                k_lower = k.lower()
                if k in _FORBIDDEN_VERA_REASONING_KEYS or (
                    "reasoning" in k_lower and k_lower not in {"reason"}
                ):
                    hits.append(next_path)
                _walk(v, next_path)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                _walk(v, f"{path}[{i}]")

    _walk(value, "")
    # Deterministic ordering for stable test assertions.
    return sorted(set(hits))


def _contains_component_selection(text: str) -> bool:
    """
    Heuristic checks for component/part identifiers that should not appear at
    functional architecture maturity.
    """

    forbidden_tokens = [
        "ESP32",
        "STM32",
        "BME280",
        "BME",
        "ATMEGA",
        "ARDUINO",
        "RASPBERRY",
        "RPI",
        "NRF",
        "Nrf",
        "nRF",
    ]

    # Stronger heuristic for part numbers like BME280 / STM32F4 / nRF52 etc.
    forbidden_part_patterns = [
        r"\bESP32\b",
        r"\bSTM32\b",
        r"\bBME\d+\b",
        r"\bnRF\d+\b",
        r"\bATMEGA\d+\b",
    ]

    upper = text.upper()
    if any(tok.upper() in upper for tok in forbidden_tokens if tok not in {"BME"}):
        return True
    for pattern in forbidden_part_patterns:
        import re

        if re.search(pattern, text):
            return True
    return False


def semantic_validate_bundle(bundle: dict[str, Any]) -> list[SemanticValidationError]:
    errors: list[SemanticValidationError] = []

    requirement_set = bundle.get("requirement_set_content")
    functional_arch = bundle.get("functional_architecture_content")
    vera_response = bundle.get("vera_response")
    artifact_envelopes: list[dict[str, Any]] = bundle.get("artifact_envelopes", []) or []

    # --- Artifact envelope status dimensions stay separate ---
    for artifact in artifact_envelopes:
        if isinstance(artifact, dict) and "status" in artifact:
            errors.append(
                SemanticValidationError(
                    code="ARTIFACT_STATUS_DIMENSIONS_COMBINED",
                    message="Found forbidden combined artifact status field 'status'.",
                    path="artifact.status",
                )
            )

        # Defensive: ensure the schemaVersion and artifactVersion are separate types.
        if isinstance(artifact, dict):
            schema_version = artifact.get("schemaVersion")
            artifact_version = artifact.get("artifactVersion")
            if schema_version is not None and not isinstance(schema_version, str):
                errors.append(
                    SemanticValidationError(
                        code="ARTIFACT_SCHEMA_VERSION_WRONG_TYPE",
                        message="artifact.schemaVersion must be a string.",
                        path="artifact.schemaVersion",
                    )
                )
            if artifact_version is not None and not isinstance(artifact_version, int):
                errors.append(
                    SemanticValidationError(
                        code="ARTIFACT_VERSION_WRONG_TYPE",
                        message="artifact.artifactVersion must be an integer.",
                        path="artifact.artifactVersion",
                    )
                )

    # --- Requirement semantic invariants ---
    if isinstance(requirement_set, dict):
        requirements: list[dict[str, Any]] = requirement_set.get("requirements", []) or []

        display_ids: list[str] = []
        for req in requirements:
            display_id = req.get("displayId")
            if isinstance(display_id, str):
                display_ids.append(display_id)
        counts = Counter(display_ids)
        duplicates = sorted([d for d, c in counts.items() if c > 1])
        if duplicates:
            errors.append(
                SemanticValidationError(
                    code="REQ_DUPLICATE_DISPLAY_ID",
                    message=(f"Duplicate requirement displayId values detected: {duplicates}."),
                    path="requirementSet.requirements.displayId",
                )
            )

        for req in requirements:
            source_type = req.get("sourceType")
            source_reference = req.get("sourceReference") or {}
            evidence_strength = source_reference.get("evidenceStrength")

            # In this slice, user-explicit requirements must not be backed only by
            # inferred evidence.
            if source_type == "user-explicit" and evidence_strength == "inferred":
                errors.append(
                    SemanticValidationError(
                        code="REQ_SOURCE_INFERRED_MISLABELED",
                        message=(
                            "Requirement marked user-explicit is backed by "
                            "inferred evidenceStrength."
                        ),
                        path=f"requirementSet.requirements[{req.get('requirementId')}]",
                    )
                )

    # --- Architecture semantic invariants ---
    if isinstance(functional_arch, dict):
        nodes = functional_arch.get("nodes", []) or []
        node_ids = {
            n.get("nodeId")
            for n in nodes
            if isinstance(n, dict) and isinstance(n.get("nodeId"), str)
        }

        edges = functional_arch.get("edges", []) or []
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            from_id = edge.get("fromNodeId")
            to_id = edge.get("toNodeId")
            if isinstance(from_id, str) and from_id not in node_ids:
                errors.append(
                    SemanticValidationError(
                        code="ARCH_EDGE_REFERENCES_MISSING_NODE",
                        message=f"Edge fromNodeId '{from_id}' does not exist in nodes.",
                        path="functionalArchitecture.edges",
                    )
                )
            if isinstance(to_id, str) and to_id not in node_ids:
                errors.append(
                    SemanticValidationError(
                        code="ARCH_EDGE_REFERENCES_MISSING_NODE",
                        message=f"Edge toNodeId '{to_id}' does not exist in nodes.",
                        path="functionalArchitecture.edges",
                    )
                )

        # Component/part identifiers must not appear at functional maturity.
        if functional_arch.get("architectureMaturity") == "functional":
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                name = node.get("name", "")
                if isinstance(name, str) and _contains_component_selection(name):
                    errors.append(
                        SemanticValidationError(
                            code="ARCH_COMPONENT_SELECTION_IN_FUNCTIONAL",
                            message=(
                                "Component/part identifier found in functional "
                                "architecture node name."
                            ),
                            path=f"functionalArchitecture.nodes[{node.get('nodeId')}].name",
                        )
                    )

                for resp in node.get("responsibilities", []) or []:
                    if isinstance(resp, str) and _contains_component_selection(resp):
                        errors.append(
                            SemanticValidationError(
                                code="ARCH_COMPONENT_SELECTION_IN_FUNCTIONAL",
                                message=(
                                    "Component/part identifier found in functional "
                                    "architecture responsibilities."
                                ),
                                path=f"functionalArchitecture.nodes[{node.get('nodeId')}].responsibilities",
                            )
                        )

    # --- Cross-object semantic invariants (Requirement coverage) ---
    if isinstance(functional_arch, dict) and isinstance(requirement_set, dict):
        req_ids = {
            r.get("requirementId")
            for r in (requirement_set.get("requirements", []) or [])
            if isinstance(r, dict) and isinstance(r.get("requirementId"), str)
        }

        covered = (functional_arch.get("requirementCoverage", {}) or {}).get(
            "coveredRequirementIds", []
        ) or []
        missing = [rid for rid in covered if isinstance(rid, str) and rid not in req_ids]
        if missing:
            missing_sorted = sorted(set(missing))
            errors.append(
                SemanticValidationError(
                    code="ARCH_REQUIREMENT_COVERAGE_MISSING_REQUIREMENTS",
                    message=(
                        f"requirementCoverage references missing requirementIds: {missing_sorted}."
                    ),
                    path="functionalArchitecture.requirementCoverage.coveredRequirementIds",
                )
            )

    # --- Vera response semantic invariants ---
    if isinstance(vera_response, dict):
        hits = find_hidden_reasoning_fields(vera_response)
        if hits:
            errors.append(
                SemanticValidationError(
                    code="VERA_HIDDEN_REASONING_FORBIDDEN",
                    message=f"Hidden reasoning fields are forbidden: {hits}.",
                    path="veraResponse",
                )
            )

    return errors
