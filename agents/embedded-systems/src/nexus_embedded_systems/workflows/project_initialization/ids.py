"""ID and envelope helpers owned by the backend (never by the model)."""

from __future__ import annotations

import secrets
import string
from datetime import UTC, datetime
from typing import Any, Literal

_ALPHABET = string.ascii_uppercase + string.digits

AutonomyMode = Literal["collaborate", "delegate"]


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_id(prefix: str, *, length: int = 24) -> str:
    return f"{prefix}{''.join(secrets.choice(_ALPHABET) for _ in range(length))}"


def default_actor(actor_type: str, *, display_name: str | None = None) -> dict[str, Any]:
    actor: dict[str, Any] = {
        "schemaVersion": "1.0.0",
        "actorId": new_id("actor_"),
        "actorType": actor_type,
    }
    if display_name:
        actor["displayName"] = display_name
    return actor


def artifact_envelope(
    *,
    artifact_type: str,
    content: dict[str, Any],
    project_id: str,
    turn_id: str,
    workflow_run_id: str,
    created_by: dict[str, Any],
    now: str,
    lifecycle_status: str = "drafted",
    evidence_status: str = "inferred",
    approval_status: str = "proposed",
) -> dict[str, Any]:
    return {
        "schemaVersion": "1.0.0",
        "artifactId": new_id("art_"),
        "projectId": project_id,
        "artifactType": artifact_type,
        "artifactVersion": 1,
        "contentSchemaVersion": "1.0.0",
        "lifecycleStatus": lifecycle_status,
        "evidenceStatus": evidence_status,
        "approvalStatus": approval_status,
        "createdBy": created_by,
        "createdAt": now,
        "updatedAt": now,
        "sourceTurnId": turn_id,
        "workflowRunId": workflow_run_id,
        "content": content,
    }
