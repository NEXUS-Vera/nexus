"""Artifact type registry for the Phase 11 kernel."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from nexus_board.errors import DuplicateRegistrationError, RegistryError

_WORKSPACE_COMMANDS = [
    "workspace.create",
    "workspace.update-draft",
    "workspace.acquire-edit-lease",
    "workspace.release-edit-lease",
    "workspace.discard-draft",
    "workspace.create-snapshot",
    "workspace.restore-snapshot",
    "artifact.validate-draft",
    "artifact.propose-revision",
    "artifact.accept-revision",
    "artifact.reject-revision",
    "artifact.inspect-deletion-impact",
]

_EXECUTABLE_COMMANDS = [*_WORKSPACE_COMMANDS, "artifact.execute"]


def _definition(
    *,
    artifact_type: str,
    display_name: str,
    phase: str,
    workspace_type: str,
    supported_command_types: list[str],
    required_capabilities: list[str],
    dependencies: list[dict[str, Any]],
    editable: bool,
    executable: bool,
    board_visibility: str,
    approval_policy_id: str = "default-collaborate",
) -> dict[str, Any]:
    return {
        "schemaVersion": "1.0.0",
        "artifactType": artifact_type,
        "displayName": display_name,
        "phase": phase,
        "workspaceType": workspace_type,
        "supportedCommandTypes": list(supported_command_types),
        "requiredCapabilities": list(required_capabilities),
        "dependencies": deepcopy(dependencies),
        "editable": editable,
        "executable": executable,
        "approvalPolicyId": approval_policy_id,
        "boardVisibility": board_visibility,
    }


DEFAULT_ARTIFACT_TYPE_DEFINITIONS: list[dict[str, Any]] = [
    _definition(
        artifact_type="project-brief",
        display_name="Project Brief",
        phase="DEFINE",
        workspace_type="structured-document",
        supported_command_types=_WORKSPACE_COMMANDS,
        required_capabilities=[],
        dependencies=[],
        editable=True,
        executable=False,
        board_visibility="primary",
    ),
    _definition(
        artifact_type="requirement-set",
        display_name="Requirements",
        phase="DEFINE",
        workspace_type="structured-document",
        supported_command_types=_EXECUTABLE_COMMANDS,
        required_capabilities=["structured-validation", "fake-execution"],
        dependencies=[
            {
                "artifactType": "project-brief",
                "relationship": "depends-on",
                "required": True,
            }
        ],
        editable=True,
        executable=True,
        board_visibility="primary",
    ),
    _definition(
        artifact_type="functional-architecture",
        display_name="Functional Architecture",
        phase="DESIGN",
        workspace_type="graph-workspace",
        supported_command_types=_EXECUTABLE_COMMANDS,
        required_capabilities=["fake-execution"],
        dependencies=[
            {
                "artifactType": "requirement-set",
                "relationship": "depends-on",
                "required": True,
            }
        ],
        editable=True,
        executable=True,
        board_visibility="primary",
    ),
    _definition(
        artifact_type="next-action",
        display_name="Next Action",
        phase="DEFINE",
        workspace_type="focused-action",
        supported_command_types=_WORKSPACE_COMMANDS,
        required_capabilities=[],
        dependencies=[
            {
                "artifactType": "component-plan",
                "relationship": "depends-on",
                "required": False,
            }
        ],
        editable=True,
        executable=False,
        board_visibility="global",
    ),
    _definition(
        artifact_type="component-plan",
        display_name="Component Plan",
        phase="DESIGN",
        workspace_type="comparison-workspace",
        supported_command_types=_EXECUTABLE_COMMANDS,
        required_capabilities=["fake-execution"],
        dependencies=[
            {
                "artifactType": "functional-architecture",
                "relationship": "depends-on",
                "required": True,
            },
            {
                "artifactType": "requirement-set",
                "relationship": "depends-on",
                "required": True,
            },
        ],
        editable=True,
        executable=True,
        board_visibility="primary",
    ),
    _definition(
        artifact_type="code-scratch",
        display_name="Code Scratch",
        phase="BUILD",
        workspace_type="code-workspace",
        supported_command_types=_EXECUTABLE_COMMANDS,
        required_capabilities=["file-workspace", "sandbox-execution"],
        dependencies=[],
        editable=True,
        executable=True,
        board_visibility="hidden",
    ),
    _definition(
        artifact_type="firmware",
        display_name="Firmware",
        phase="BUILD",
        workspace_type="code-workspace",
        supported_command_types=_EXECUTABLE_COMMANDS,
        required_capabilities=["file-workspace", "sandbox-execution"],
        dependencies=[
            {
                "artifactType": "functional-architecture",
                "relationship": "depends-on",
                "required": False,
            },
            {
                "artifactType": "component-plan",
                "relationship": "depends-on",
                "required": False,
            },
        ],
        editable=True,
        executable=True,
        board_visibility="primary",
    ),
    _definition(
        artifact_type="electrical-architecture",
        display_name="Electrical Architecture",
        phase="DESIGN",
        workspace_type="graph-workspace",
        supported_command_types=_EXECUTABLE_COMMANDS,
        required_capabilities=["circuit-simulation"],
        dependencies=[
            {
                "artifactType": "functional-architecture",
                "relationship": "depends-on",
                "required": True,
            },
            {
                "artifactType": "component-plan",
                "relationship": "depends-on",
                "required": True,
            },
        ],
        editable=True,
        executable=True,
        board_visibility="primary",
    ),
    _definition(
        artifact_type="physical-architecture",
        display_name="Physical Architecture",
        phase="DESIGN",
        workspace_type="graph-workspace",
        supported_command_types=_EXECUTABLE_COMMANDS,
        required_capabilities=["fake-execution"],
        dependencies=[
            {
                "artifactType": "electrical-architecture",
                "relationship": "depends-on",
                "required": True,
            }
        ],
        editable=True,
        executable=True,
        board_visibility="primary",
    ),
]


class ArtifactTypeRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, dict[str, Any]] = {}

    def register(self, definition: dict[str, Any]) -> None:
        artifact_type = definition.get("artifactType")
        if not isinstance(artifact_type, str) or not artifact_type:
            raise RegistryError("Artifact type definition missing artifactType.")
        if artifact_type in self._definitions:
            raise DuplicateRegistrationError(f"Artifact type already registered: {artifact_type}")
        self._definitions[artifact_type] = deepcopy(definition)

    def get(self, artifact_type: str) -> dict[str, Any]:
        definition = self._definitions.get(artifact_type)
        if definition is None:
            raise RegistryError(f"Unknown artifact type: {artifact_type}")
        return deepcopy(definition)

    def list(self) -> list[dict[str, Any]]:
        return [deepcopy(item) for item in self._definitions.values()]

    def known_types(self) -> set[str]:
        return set(self._definitions)

    def supports_command(self, artifact_type: str, command_type: str) -> bool:
        definition = self.get(artifact_type)
        return command_type in definition["supportedCommandTypes"]


def default_artifact_type_registry() -> ArtifactTypeRegistry:
    registry = ArtifactTypeRegistry()
    for definition in DEFAULT_ARTIFACT_TYPE_DEFINITIONS:
        registry.register(definition)
    return registry
