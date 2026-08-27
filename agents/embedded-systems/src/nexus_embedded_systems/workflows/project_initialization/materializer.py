"""Structured materialization of golden fixture packages into fresh project runs.

Golden fixtures are immutable templates. This module deep-copies fixture JSON,
allocates fresh IDs/timestamps, and remaps every cross-reference via a deliberate
ID map — never via raw string replacement over serialized JSON.
"""

from __future__ import annotations

import copy
import secrets
import string
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nexus_contracts.validation.project_package_validator import load_project_package_bundle

ID_PREFIXES: tuple[str, ...] = (
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
    "actor_",
    "event_",
    "act_",
    "role_",
    "cand_",
    "sel_",
    "cstr_",
    "cchk_",
    "cplan_",
    "q_",
    # Optional Phase 13 layered-architecture IDs (when present in fixtures).
    "enode_",
    "econn_",
    "eiface_",
    "epwr_",
    "earch_",
    "pnode_",
    "pzone_",
    "prel_",
    "parch_",
    "test_",
    "risk_",
    "tplan_",
    "rreg_",
    "evi_",
)

# Longest prefix first so "question_" wins over shorter accidental matches.
_SORTED_PREFIXES = tuple(sorted(ID_PREFIXES, key=len, reverse=True))

_ALPHABET = string.ascii_uppercase + string.digits

IdFactory = Callable[[str], str]


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def default_id_factory(prefix: str) -> str:
    if prefix not in ID_PREFIXES:
        raise ValueError(f"Unsupported id prefix: {prefix}")
    # Patterns require prefix + at least 16 alnum chars.
    return f"{prefix}{''.join(secrets.choice(_ALPHABET) for _ in range(24))}"


def _looks_like_id(value: str) -> str | None:
    for prefix in _SORTED_PREFIXES:
        if value.startswith(prefix) and len(value) > len(prefix) + 15:
            remainder = value[len(prefix) :]
            if remainder.isalnum():
                return prefix
    return None


def _collect_ids(node: Any, found: set[str]) -> None:
    if isinstance(node, dict):
        for value in node.values():
            _collect_ids(value, found)
    elif isinstance(node, list):
        for item in node:
            _collect_ids(item, found)
    elif isinstance(node, str) and _looks_like_id(node):
        found.add(node)


def build_id_map(root: Any, id_factory: IdFactory = default_id_factory) -> dict[str, str]:
    found: set[str] = set()
    _collect_ids(root, found)
    mapping: dict[str, str] = {}
    for old_id in sorted(found):
        prefix = _looks_like_id(old_id)
        assert prefix is not None
        mapping[old_id] = id_factory(prefix)
    return mapping


def remap_ids(node: Any, id_map: dict[str, str]) -> Any:
    if isinstance(node, dict):
        return {key: remap_ids(value, id_map) for key, value in node.items()}
    if isinstance(node, list):
        return [remap_ids(item, id_map) for item in node]
    if isinstance(node, str) and node in id_map:
        return id_map[node]
    return node


_TIMESTAMP_KEYS = frozenset(
    {
        "createdAt",
        "updatedAt",
        "timestamp",
        "startedAt",
        "completedAt",
        "routedAt",
        "startTime",
        "completionTime",
    }
)


def remap_timestamps(node: Any, now: str) -> Any:
    if isinstance(node, dict):
        out: dict[str, Any] = {}
        for key, value in node.items():
            if key in _TIMESTAMP_KEYS and isinstance(value, str):
                out[key] = now
            else:
                out[key] = remap_timestamps(value, now)
        return out
    if isinstance(node, list):
        return [remap_timestamps(item, now) for item in node]
    return node


def package_bundle_to_initialization_dict(bundle: dict[str, Any]) -> dict[str, Any]:
    artifacts = list(bundle.get("artifact_envelopes") or [])
    return {
        "schemaVersion": "1.0.0",
        "project": bundle["project"],
        "userTurn": bundle["user_turn"],
        "turnRoute": bundle["turn_route"],
        "workflowRun": bundle["workflow_run"],
        "artifacts": artifacts,
        "validationIssues": list(bundle.get("validation_issues") or []),
        "openQuestions": list(bundle.get("open_questions") or []),
        "veraResponse": bundle["vera_response"],
    }


def initialization_dict_to_package_bundle(result: dict[str, Any]) -> dict[str, Any]:
    artifacts = list(result.get("artifacts") or [])
    requirement_set_content = None
    functional_architecture_content = None
    next_action_content = None
    component_plan_content = None
    electrical_architecture_content = None
    physical_architecture_content = None
    test_plan_content = None
    risk_register_content = None
    for art in artifacts:
        if not isinstance(art, dict):
            continue
        content = art.get("content")
        artifact_type = art.get("artifactType")
        if artifact_type == "requirement-set" and isinstance(content, dict):
            requirement_set_content = content
        elif artifact_type == "functional-architecture" and isinstance(content, dict):
            functional_architecture_content = content
        elif artifact_type == "next-action" and isinstance(content, dict):
            next_action_content = content
        elif artifact_type == "component-plan" and isinstance(content, dict):
            component_plan_content = content
        elif artifact_type == "electrical-architecture" and isinstance(content, dict):
            electrical_architecture_content = content
        elif artifact_type == "physical-architecture" and isinstance(content, dict):
            physical_architecture_content = content
        elif artifact_type == "test-plan" and isinstance(content, dict):
            test_plan_content = content
        elif artifact_type == "risk-register" and isinstance(content, dict):
            risk_register_content = content

    return {
        "artifact_envelopes": artifacts,
        "project": result.get("project"),
        "user_turn": result.get("userTurn"),
        "turn_route": result.get("turnRoute"),
        "workflow_run": result.get("workflowRun"),
        "requirement_set_content": requirement_set_content,
        "functional_architecture_content": functional_architecture_content,
        "next_action_content": next_action_content,
        "component_plan_content": component_plan_content,
        "electrical_architecture_content": electrical_architecture_content,
        "physical_architecture_content": physical_architecture_content,
        "test_plan_content": test_plan_content,
        "risk_register_content": risk_register_content,
        "validation_issues": list(result.get("validationIssues") or []),
        "open_questions": list(result.get("openQuestions") or []),
        "vera_response": result.get("veraResponse"),
    }


def materialize_fixture_package(
    fixture_folder: Path,
    *,
    message: str,
    autonomy_mode: str,
    now: str | None = None,
    id_factory: IdFactory = default_id_factory,
) -> tuple[dict[str, Any], dict[str, str]]:
    """Load a golden fixture folder and materialize a fresh initialization package.

    Returns (initialization_result_dict, id_map).
    """

    bundle = load_project_package_bundle(fixture_folder)
    package = copy.deepcopy(package_bundle_to_initialization_dict(bundle))
    id_map = build_id_map(package, id_factory=id_factory)
    remapped = remap_ids(package, id_map)
    stamp = now or utc_now()
    remapped = remap_timestamps(remapped, stamp)

    # Apply request-specific fields after remapping.
    if isinstance(remapped.get("userTurn"), dict):
        remapped["userTurn"]["rawUserMessage"] = message
    if isinstance(remapped.get("project"), dict):
        remapped["project"]["autonomyMode"] = autonomy_mode
    if isinstance(remapped.get("veraResponse"), dict):
        summary = remapped["veraResponse"].get("projectStateSummary")
        if isinstance(summary, dict):
            summary["autonomyMode"] = autonomy_mode

    return remapped, id_map
