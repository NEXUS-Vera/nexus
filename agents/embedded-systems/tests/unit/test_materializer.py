from __future__ import annotations

import json
from pathlib import Path

from nexus_contracts.validation.project_package_validator import (
    validate_project_package_bundle,
)
from nexus_embedded_systems.workflows.project_initialization.materializer import (
    initialization_dict_to_package_bundle,
    materialize_fixture_package,
)
from nexus_embedded_systems.workflows.project_initialization.validation import (
    validate_initialization_result_schema,
)

ROOT = Path(__file__).resolve().parents[4]
FIXTURE = ROOT / "packages/contracts/examples/valid/wearable-tremor-monitor"
PROMPT = (
    "I want to build a wrist-worn device that measures hand tremors "
    "and records the motion data for later analysis."
)


def test_materialization_creates_fresh_ids_and_leaves_fixture_untouched() -> None:
    before = {
        path.name: path.read_text(encoding="utf-8") for path in sorted(FIXTURE.glob("*.json"))
    }
    first, map1 = materialize_fixture_package(FIXTURE, message=PROMPT, autonomy_mode="collaborate")
    second, map2 = materialize_fixture_package(FIXTURE, message=PROMPT, autonomy_mode="collaborate")
    after = {path.name: path.read_text(encoding="utf-8") for path in sorted(FIXTURE.glob("*.json"))}
    assert before == after
    assert first["project"]["projectId"] != second["project"]["projectId"]
    assert map1 != map2
    assert first["userTurn"]["rawUserMessage"] == PROMPT
    assert first["project"]["projectId"].startswith("proj_")
    # Fixture IDs must not leak into the materialized package.
    fixture_project = json.loads((FIXTURE / "project.json").read_text(encoding="utf-8"))
    assert first["project"]["projectId"] != fixture_project["projectId"]


def test_materialized_package_passes_schema_and_semantic_validation() -> None:
    result, _ = materialize_fixture_package(FIXTURE, message=PROMPT, autonomy_mode="delegate")
    schema_errors = validate_initialization_result_schema(result)
    assert schema_errors == []
    bundle = initialization_dict_to_package_bundle(result)
    semantic = validate_project_package_bundle(bundle)
    blocking = [e for e in semantic if getattr(e, "blocking", True)]
    assert blocking == []
    # Cross-object project IDs agree.
    project_id = result["project"]["projectId"]
    assert result["userTurn"]["projectId"] == project_id
    assert result["workflowRun"]["projectId"] == project_id
    assert result["veraResponse"]["projectId"] == project_id
    for art in result["artifacts"]:
        assert art["projectId"] == project_id
    # Vera next-action reference resolves.
    next_id = result["veraResponse"]["nextActionArtifactReference"]["artifactId"]
    assert any(
        a["artifactId"] == next_id and a["artifactType"] == "next-action"
        for a in result["artifacts"]
    )


def test_corrupted_materialized_package_fails_validation() -> None:
    result, _ = materialize_fixture_package(FIXTURE, message=PROMPT, autonomy_mode="collaborate")
    result["artifacts"] = result["artifacts"][:2]
    schema_errors = validate_initialization_result_schema(result)
    assert schema_errors
