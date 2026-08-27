"""Artifact type registry tests."""

from __future__ import annotations

import pytest
from nexus_board.errors import DuplicateRegistrationError
from nexus_board.registries.artifact_types import (
    ArtifactTypeRegistry,
    default_artifact_type_registry,
)


def test_default_registry_has_core_artifacts() -> None:
    registry = default_artifact_type_registry()
    types = {item["artifactType"] for item in registry.list()}
    assert types == {
        "project-brief",
        "requirement-set",
        "functional-architecture",
        "next-action",
        "component-plan",
        "electrical-architecture",
        "physical-architecture",
        "code-scratch",
        "firmware",
        "analysis",
        "test-plan",
        "risk-register",
    }
    assert registry.get("code-scratch")["workspaceType"] == "code-workspace"
    assert registry.get("code-scratch")["boardVisibility"] == "hidden"
    assert registry.get("code-scratch")["requiredCapabilities"] == [
        "file-workspace",
        "sandbox-execution",
    ]
    assert registry.get("firmware")["workspaceType"] == "code-workspace"
    assert registry.get("firmware")["boardVisibility"] == "primary"
    assert registry.get("firmware")["requiredCapabilities"] == [
        "file-workspace",
        "sandbox-execution",
    ]
    assert registry.get("firmware")["phase"] == "BUILD"

    assert registry.get("analysis")["phase"] == "BUILD"
    assert registry.get("analysis")["workspaceType"] == "code-workspace"
    assert registry.get("analysis")["boardVisibility"] == "primary"
    assert registry.get("analysis")["requiredCapabilities"] == [
        "file-workspace",
        "sandbox-execution",
    ]


def test_dependency_rules() -> None:
    registry = default_artifact_type_registry()
    assert registry.get("project-brief")["dependencies"] == []
    assert registry.get("requirement-set")["dependencies"][0]["artifactType"] == "project-brief"
    assert (
        registry.get("functional-architecture")["dependencies"][0]["artifactType"]
        == "requirement-set"
    )
    assert registry.get("next-action")["boardVisibility"] == "global"
    next_deps = {d["artifactType"] for d in registry.get("next-action")["dependencies"]}
    assert "component-plan" in next_deps
    deps = {d["artifactType"] for d in registry.get("component-plan")["dependencies"]}
    assert deps == {"functional-architecture", "requirement-set"}
    electrical_deps = {
        d["artifactType"] for d in registry.get("electrical-architecture")["dependencies"]
    }
    assert electrical_deps == {"functional-architecture", "component-plan"}
    assert (
        registry.get("physical-architecture")["dependencies"][0]["artifactType"]
        == "electrical-architecture"
    )
    assert registry.get("electrical-architecture")["workspaceType"] == "graph-workspace"
    assert registry.get("physical-architecture")["workspaceType"] == "graph-workspace"


def test_duplicate_registration_fails() -> None:
    registry = ArtifactTypeRegistry()
    definition = default_artifact_type_registry().get("project-brief")
    registry.register(definition)
    with pytest.raises(DuplicateRegistrationError):
        registry.register(definition)


def test_executable_flags() -> None:
    registry = default_artifact_type_registry()
    assert registry.get("project-brief")["executable"] is False
    assert registry.get("requirement-set")["executable"] is True
    assert registry.get("component-plan")["workspaceType"] == "comparison-workspace"
    assert registry.get("next-action")["workspaceType"] == "focused-action"
