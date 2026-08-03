"""Default artifact dependency seeds for embedded project packages."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Any

ARTIFACT_TYPES = (
    "project-brief",
    "requirement-set",
    "functional-architecture",
    "next-action",
)

_DEFAULT_EDGES: tuple[tuple[str, str, str, str], ...] = (
    (
        "project-brief",
        "requirement-set",
        "derives-from",
        "Requirements are derived from the project brief.",
    ),
    (
        "requirement-set",
        "functional-architecture",
        "derives-from",
        "Architecture covers the requirement set.",
    ),
    (
        "project-brief",
        "functional-architecture",
        "constrains",
        "Architecture is constrained by the project brief scope.",
    ),
    (
        "requirement-set",
        "next-action",
        "constrains",
        "Next action is constrained by open requirements.",
    ),
    (
        "functional-architecture",
        "next-action",
        "derives-from",
        "Next action follows from architecture readiness.",
    ),
)


def _new_dep_id() -> str:
    return "dep_" + secrets.token_hex(12)


def seed_default_dependencies(project_id: str) -> list[dict[str, Any]]:
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    deps: list[dict[str, Any]] = []
    for source, target, kind, reason in _DEFAULT_EDGES:
        deps.append(
            {
                "schemaVersion": "1.0.0",
                "dependencyId": _new_dep_id(),
                "projectId": project_id,
                "sourceArtifactType": source,
                "targetArtifactType": target,
                "dependencyKind": kind,
                "reason": reason,
                "createdAt": now,
            }
        )
    return deps
