"""Materialization remapping, freshness, leakage, and fixture immutability."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from nexus_contracts.validation.project_package_validator import (
    validate_project_package_bundle,
)
from nexus_embedded_systems.workflows.project_initialization.fixture_router import (
    SUPPORTED_FAMILIES,
)
from nexus_embedded_systems.workflows.project_initialization.materializer import (
    ID_PREFIXES,
    initialization_dict_to_package_bundle,
    materialize_fixture_package,
)
from nexus_embedded_systems.workflows.project_initialization.repository import (
    InMemoryInitializationStore,
)
from nexus_embedded_systems.workflows.project_initialization.service import (
    InitializationService,
)
from nexus_embedded_systems.workflows.project_initialization.validation import (
    validate_initialization_result_schema,
)

ROOT = Path(__file__).resolve().parents[4]
FIXTURES_ROOT = ROOT / "packages/contracts/examples/valid"

# Intentionally stable identifiers that must NOT be treated as remapped runtime IDs:
# - schemaVersion values (e.g. "1.0.0")
# - enum / const contract values (artifactType, statuses, domains, units)
# - human-readable display IDs (R1, Q1, A1, FA1 assumption labels)
# - free-text source statements and messages
# - quantity units
RUNTIME_ID_PREFIXES = ID_PREFIXES

PROMPTS = {
    "indoor-environmental-rover": (
        "I want to build a small indoor rover that drives around a room and maps "
        "temperature, humidity, and air quality."
    ),
    "wearable-tremor-monitor": (
        "I want to build a wrist-worn device that measures hand tremors "
        "and records the motion data for later analysis."
    ),
    "greenhouse-sensing-node": (
        "I want to build a greenhouse monitoring node that measures temperature, "
        "humidity, soil moisture, and light, and reports the readings remotely."
    ),
    "vibration-monitoring-device": (
        "I want to build a device that attaches to a machine and records vibration "
        "so I can detect changes in how the machine is operating."
    ),
    "robot-obstacle-detection-module": (
        "I want to build an obstacle-detection module for a small indoor robot "
        "so it can detect objects in front of it and react before it hits them."
    ),
}


def _hash_fixture_dir(folder: Path) -> dict[str, str]:
    digest: dict[str, str] = {}
    for path in sorted(folder.glob("*.json")):
        digest[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest


def _collect_runtime_ids(node: Any, found: set[str]) -> None:
    if isinstance(node, dict):
        for value in node.values():
            _collect_runtime_ids(value, found)
    elif isinstance(node, list):
        for item in node:
            _collect_runtime_ids(item, found)
    elif isinstance(node, str):
        for prefix in RUNTIME_ID_PREFIXES:
            if node.startswith(prefix) and len(node) > len(prefix) + 15:
                remainder = node[len(prefix) :]
                if remainder.isalnum():
                    found.add(node)
                    break


def _action_ids(result: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for art in result.get("artifacts") or []:
        if art.get("artifactType") != "next-action":
            continue
        content = art.get("content") or {}
        action_id = content.get("actionId")
        if isinstance(action_id, str):
            ids.add(action_id)
    return ids


def _collect_ids_by_prefix(result: dict[str, Any], prefix: str) -> set[str]:
    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, str) and node.startswith(prefix):
            found.add(node)

    walk(result)
    return found


@pytest.mark.parametrize("family", list(SUPPORTED_FAMILIES))
def test_no_original_fixture_runtime_ids_survive(family: str) -> None:
    folder = FIXTURES_ROOT / family
    before_hashes = _hash_fixture_dir(folder)
    source = json.loads(
        json.dumps(
            {
                path.stem.replace("-", "_"): json.loads(path.read_text(encoding="utf-8"))
                for path in sorted(folder.glob("*.json"))
            }
        )
    )
    # Prefer loading via materializer's own loader path for identity collection.
    from nexus_contracts.validation.project_package_validator import load_project_package_bundle
    from nexus_embedded_systems.workflows.project_initialization.materializer import (
        package_bundle_to_initialization_dict,
    )

    original_package = package_bundle_to_initialization_dict(load_project_package_bundle(folder))
    original_ids: set[str] = set()
    _collect_runtime_ids(original_package, original_ids)
    assert original_ids, f"expected runtime ids in fixture {family}"
    assert any(i.startswith("act_") for i in original_ids), f"expected act_ ids in {family}"

    result, id_map = materialize_fixture_package(
        folder,
        message=PROMPTS[family],
        autonomy_mode="collaborate",
    )
    after_hashes = _hash_fixture_dir(folder)
    assert before_hashes == after_hashes

    surviving: set[str] = set()
    _collect_runtime_ids(result, surviving)
    leaked = original_ids & surviving
    assert leaked == set(), f"fixture runtime ids leaked for {family}: {sorted(leaked)[:20]}"
    assert set(id_map) == original_ids
    assert _action_ids(result).isdisjoint({i for i in original_ids if i.startswith("act_")})
    _ = source  # retained for clarity that fixtures are the identity source


@pytest.mark.parametrize("family", list(SUPPORTED_FAMILIES))
def test_action_ids_are_fresh_across_families(family: str) -> None:
    folder = FIXTURES_ROOT / family
    first, _ = materialize_fixture_package(
        folder, message=PROMPTS[family], autonomy_mode="collaborate"
    )
    second, _ = materialize_fixture_package(
        folder, message=PROMPTS[family], autonomy_mode="collaborate"
    )
    assert _action_ids(first)
    assert _action_ids(first).isdisjoint(_action_ids(second))
    for action_id in _action_ids(first):
        assert action_id.startswith("act_")


@pytest.mark.asyncio
async def test_repeated_service_initialization_produces_fresh_ids() -> None:
    service = InitializationService(
        store=InMemoryInitializationStore(), fixtures_root=FIXTURES_ROOT
    )
    family = "wearable-tremor-monitor"
    first = await service.initialize_embedded_project(PROMPTS[family], "collaborate")
    second = await service.initialize_embedded_project(PROMPTS[family], "collaborate")

    for result in (first, second):
        assert validate_initialization_result_schema(result) == []
        blocking = [
            e
            for e in validate_project_package_bundle(initialization_dict_to_package_bundle(result))
            if getattr(e, "blocking", True)
        ]
        assert blocking == []

    prefixes = [
        "proj_",
        "turn_",
        "route_",
        "run_",
        "art_",
        "req_",
        "arch_",
        "node_",
        "edge_",
        "issue_",
        "question_",
        "act_",
        "actor_",
    ]
    for prefix in prefixes:
        left = _collect_ids_by_prefix(first, prefix)
        right = _collect_ids_by_prefix(second, prefix)
        if not left and not right:
            continue
        assert left
        assert right
        assert left.isdisjoint(right), f"overlapping {prefix} ids across requests"


def test_fixture_hashes_unchanged_across_materialization_of_all_families() -> None:
    before = {family: _hash_fixture_dir(FIXTURES_ROOT / family) for family in SUPPORTED_FAMILIES}
    for family in SUPPORTED_FAMILIES:
        materialize_fixture_package(
            FIXTURES_ROOT / family,
            message=PROMPTS[family],
            autonomy_mode="collaborate",
        )
    after = {family: _hash_fixture_dir(FIXTURES_ROOT / family) for family in SUPPORTED_FAMILIES}
    assert before == after


def test_shuffled_artifacts_still_validate() -> None:
    folder = FIXTURES_ROOT / "wearable-tremor-monitor"
    result, _ = materialize_fixture_package(
        folder, message=PROMPTS["wearable-tremor-monitor"], autonomy_mode="collaborate"
    )
    # Put next-action first; brief last.
    by_type = {a["artifactType"]: a for a in result["artifacts"]}
    result["artifacts"] = [
        by_type["next-action"],
        by_type["functional-architecture"],
        by_type["requirement-set"],
        by_type["project-brief"],
    ]
    # Rebuild project current refs order independently of artifact array order.
    assert validate_initialization_result_schema(result) == []
