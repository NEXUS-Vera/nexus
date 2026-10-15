"""Idempotent ensure of Electrical/Physical artifacts for existing projects."""

from __future__ import annotations

from typing import Any

from nexus_embedded_systems.workflows.layered_architecture.compose_electrical import (
    compose_electrical_architecture_content,
    compose_electrical_architecture_envelope,
)
from nexus_embedded_systems.workflows.layered_architecture.compose_physical import (
    compose_physical_architecture_content,
    compose_physical_architecture_envelope,
)
from nexus_embedded_systems.workflows.project_initialization.ids import new_id, utc_now


def ensure_layered_architecture_artifacts(
    *,
    project_id: str,
    artifacts: list[dict[str, Any]],
    actor: dict[str, Any] | None = None,
    turn_id: str | None = None,
    workflow_run_id: str | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Compose missing Electrical/Physical artifacts from FA + Component Plan.

    Idempotent: existing electrical/physical artifacts are left unchanged.
    Does not persist — caller applies revisions / updates project refs.

    Returns:
      {
        "created": [artifact, ...],  # newly composed envelopes only
        "artifacts": [artifact, ...],  # full set with ensures applied in-memory
        "skippedReason": str | None,
      }
    """
    by_type: dict[str, dict[str, Any]] = {}
    for art in artifacts:
        if isinstance(art, dict) and isinstance(art.get("artifactType"), str):
            by_type[art["artifactType"]] = art

    fa = by_type.get("functional-architecture")
    plan = by_type.get("component-plan")
    if not isinstance(fa, dict) or not isinstance(plan, dict):
        return {
            "created": [],
            "artifacts": list(artifacts),
            "skippedReason": "functional-architecture and component-plan are required",
        }

    stamp = now or utc_now()
    created_by = (
        actor
        or fa.get("createdBy")
        or {
            "schemaVersion": "1.0.0",
            "actorId": "actor_systemensure0001",
            "actorType": "system",
            "displayName": "System",
        }
    )
    tid = turn_id or new_id("turn")
    rid = workflow_run_id or new_id("run")
    created: list[dict[str, Any]] = []

    if "electrical-architecture" not in by_type:
        content = compose_electrical_architecture_content(
            architecture_content=fa.get("content") or {},
            component_plan_content=plan.get("content") or {},
        )
        electrical = compose_electrical_architecture_envelope(
            content=content,
            project_id=project_id,
            turn_id=tid,
            workflow_run_id=rid,
            created_by=created_by,
            now=stamp,
        )
        by_type["electrical-architecture"] = electrical
        created.append(electrical)
    else:
        electrical = by_type["electrical-architecture"]

    if "physical-architecture" not in by_type:
        fa_content = fa.get("content") or {}
        content = compose_physical_architecture_content(
            electrical_content=electrical.get("content") or {},
            project_context={
                "systemBoundary": fa_content.get("systemBoundary"),
                "summary": (electrical.get("content") or {}).get("summary"),
            },
        )
        physical = compose_physical_architecture_envelope(
            content=content,
            project_id=project_id,
            turn_id=tid,
            workflow_run_id=rid,
            created_by=created_by,
            now=stamp,
        )
        by_type["physical-architecture"] = physical
        created.append(physical)

    order = [
        "project-brief",
        "requirement-set",
        "functional-architecture",
        "component-plan",
        "electrical-architecture",
        "physical-architecture",
        "next-action",
    ]
    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()
    for key in order:
        candidate = by_type.get(key)
        if candidate is not None:
            ordered.append(candidate)
            seen.add(key)
    for key, candidate in by_type.items():
        if key not in seen:
            ordered.append(candidate)

    return {"created": created, "artifacts": ordered, "skippedReason": None}
