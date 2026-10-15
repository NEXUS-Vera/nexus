"""Artifact type registry tests."""

from __future__ import annotations

import pytest
from nexus_board.errors import DuplicateRegistrationError
from nexus_board.registries.artifact_types import (
    ArtifactTypeRegistry,
    default_artifact_type_registry,
)


def test_default_registry_has_runtime_artifacts() -> None:
    registry = default_artifact_type_registry()
    types = {item["artifactType"] for item in registry.list()}
    assert types == {
        "project-brief",
        "requirement-set",
        "functional-architecture",
        "next-action",
        "component-plan",
        "code-scratch",
        "analysis",
        "test-plan",
        "risk-register",
        "firmware",
        "electrical-architecture",
        "physical-architecture",
    }


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
