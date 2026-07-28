"""WorkflowRun ledger truthfulness for fixture-backed initialization."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from nexus_embedded_systems.workflows.project_initialization.repository import (
    InMemoryInitializationStore,
)
from nexus_embedded_systems.workflows.project_initialization.service import (
    InitializationService,
    InitializationValidationError,
)

ROOT = Path(__file__).resolve().parents[4]
FIXTURES = ROOT / "packages/contracts/examples/valid"
PROMPT = (
    "I want to build a wrist-worn device that measures hand tremors "
    "and records the motion data for later analysis."
)

# Fixed step order performed by FixtureInitializationProvider for a
# successful run. Kept here rather than imported because it is a test-time
# expectation, not a public contract of the provider.
WORKFLOW_STEPS: tuple[str, ...] = (
    "route-turn",
    "select-fixture-family",
    "create-project-context",
    "materialize-fixture-package",
    "validate-schema",
    "validate-project-package",
    "build-result",
    "complete-workflow",
)


def _timestamps(steps: list[dict[str, Any]]) -> list[str]:
    values: list[str] = []
    for step in steps:
        if "startedAt" in step:
            values.append(step["startedAt"])
        if "completedAt" in step:
            values.append(step["completedAt"])
    return values


@pytest.mark.asyncio
async def test_successful_workflow_is_chronological_and_complete() -> None:
    service = InitializationService(store=InMemoryInitializationStore(), fixtures_root=FIXTURES)
    result = await service.initialize_embedded_project(PROMPT, autonomy_mode="collaborate")
    workflow = result["workflowRun"]
    steps = workflow["stepRecords"]
    assert [s["stepType"] for s in steps] == list(WORKFLOW_STEPS)
    assert all(s["status"] == "completed" for s in steps)
    assert all(s["attempt"] == 1 for s in steps)
    assert workflow["runStatus"] in {"completed", "completed-with-warnings"}
    stamps = _timestamps(steps)
    assert stamps == sorted(stamps)
    assert workflow["startTime"] <= stamps[0]
    assert workflow["completionTime"] >= stamps[-1]

    artifact_ids = {a["artifactId"] for a in result["artifacts"]}
    for step in steps:
        if step["stepType"] in {
            "materialize-fixture-package",
            "build-result",
            "complete-workflow",
        }:
            refs = step.get("outputArtifactReferences") or []
            assert refs
            for ref in refs:
                assert ref["artifactId"] in artifact_ids
        else:
            assert "outputArtifactReferences" not in step

    forbidden = {
        "model-reasoning",
        "research",
        "chairman",
        "board",
        "curator",
        "generate-architecture",
        "llm",
    }
    for step in steps:
        lowered = step["stepType"].lower()
        assert not any(token in lowered for token in forbidden)


@pytest.mark.asyncio
async def test_schema_validation_failure_stops_later_steps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = InitializationService(store=InMemoryInitializationStore(), fixtures_root=FIXTURES)

    from nexus_embedded_systems.workflows.project_initialization.materializer import (
        materialize_fixture_package,
    )

    original = materialize_fixture_package

    def corrupt(*args: Any, **kwargs: Any) -> tuple[dict[str, Any], dict[str, str]]:
        result, id_map = original(*args, **kwargs)
        result["artifacts"] = result["artifacts"][:1]
        return result, id_map

    monkeypatch.setattr(
        "nexus_embedded_systems.workflows.project_initialization.providers."
        "fixture_provider.materialize_fixture_package",
        corrupt,
    )

    with pytest.raises(InitializationValidationError) as exc_info:
        await service.initialize_embedded_project(PROMPT, autonomy_mode="collaborate")

    assert "SCHEMA_VALIDATION_FAILED" in exc_info.value.codes
    workflow = exc_info.value.workflow_run
    assert workflow is not None
    assert workflow["runStatus"] == "failed"
    types = [s["stepType"] for s in workflow["stepRecords"]]
    assert types == [
        "route-turn",
        "select-fixture-family",
        "create-project-context",
        "materialize-fixture-package",
        "validate-schema",
    ]
    assert workflow["stepRecords"][-1]["status"] == "failed"
    assert all(s["status"] == "completed" for s in workflow["stepRecords"][:-1])
    assert "validate-project-package" not in types
    assert "build-result" not in types
    assert "complete-workflow" not in types
    stamps = _timestamps(workflow["stepRecords"])
    assert stamps == sorted(stamps)


@pytest.mark.asyncio
async def test_semantic_validation_failure_stops_later_steps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = InitializationService(store=InMemoryInitializationStore(), fixtures_root=FIXTURES)

    def boom(_bundle: dict[str, Any]) -> list[Any]:
        from nexus_contracts.validation.semantic_validators import SemanticValidationError

        return [
            SemanticValidationError(
                code="TEST_SEMANTIC_FAILURE",
                message="Injected semantic failure",
                path="project",
                blocking=True,
            )
        ]

    monkeypatch.setattr(
        "nexus_embedded_systems.workflows.project_initialization.providers."
        "fixture_provider.validate_initialization_package",
        boom,
    )

    with pytest.raises(InitializationValidationError) as exc_info:
        await service.initialize_embedded_project(PROMPT, autonomy_mode="collaborate")

    assert "TEST_SEMANTIC_FAILURE" in exc_info.value.codes
    workflow = exc_info.value.workflow_run
    assert workflow is not None
    assert workflow["runStatus"] == "failed"
    types = [s["stepType"] for s in workflow["stepRecords"]]
    assert types[-1] == "validate-project-package"
    assert workflow["stepRecords"][-1]["status"] == "failed"
    assert "build-result" not in types
    assert "complete-workflow" not in types
    assert all(s["status"] == "completed" for s in workflow["stepRecords"][:-1])
