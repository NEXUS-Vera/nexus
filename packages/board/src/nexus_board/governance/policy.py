"""Approval and authority policy (Phase 11 §21)."""

from __future__ import annotations

from typing import Any, Literal

ActorKind = Literal["user", "agent", "system", "execution", "external-provider"]
CommandType = str
ConsequenceLevel = Literal["low", "medium", "high", "safety-critical"]
AutonomyMode = Literal["collaborate", "delegate"]

_USER_AUTHORITIES = {
    "propose",
    "edit-draft",
    "execute",
    "validate",
    "approve",
    "reject",
    "supersede",
}
_AGENT_AUTHORITIES = {"propose", "edit-draft", "execute", "validate"}
_SYSTEM_AUTHORITIES = {"propose", "edit-draft", "execute", "validate", "supersede"}
_EXECUTION_AUTHORITIES = {"execute", "validate"}
_EXTERNAL_AUTHORITIES: set[str] = set()

_COMMAND_AUTHORITY: dict[str, str] = {
    "workspace.create": "edit-draft",
    "workspace.update-draft": "edit-draft",
    "workspace.create-snapshot": "edit-draft",
    "workspace.restore-snapshot": "edit-draft",
    "artifact.validate-draft": "validate",
    "artifact.propose-revision": "propose",
    "artifact.accept-revision": "approve",
    "artifact.reject-revision": "reject",
    "artifact.execute": "execute",
}

_ACTOR_TYPE_TO_KIND: dict[str, ActorKind] = {
    "user": "user",
    "vera": "agent",
    "embedded-systems-agent": "agent",
    "system": "system",
    "shared": "system",
}


def actor_kind_from_actor_type(actor_type: str) -> ActorKind:
    kind = _ACTOR_TYPE_TO_KIND.get(actor_type)
    if kind is None:
        if actor_type in {"execution", "external-provider"}:
            return actor_type  # type: ignore[return-value]
        return "system"
    return kind


def authorities_for(actor_kind: ActorKind) -> set[str]:
    if actor_kind == "user":
        return set(_USER_AUTHORITIES)
    if actor_kind == "agent":
        return set(_AGENT_AUTHORITIES)
    if actor_kind == "system":
        return set(_SYSTEM_AUTHORITIES)
    if actor_kind == "execution":
        return set(_EXECUTION_AUTHORITIES)
    return set(_EXTERNAL_AUTHORITIES)


def may_perform_command(actor_kind: ActorKind, command_type: CommandType) -> bool:
    authority = _COMMAND_AUTHORITY.get(command_type)
    if authority is None:
        return False
    return authority in authorities_for(actor_kind)


def evaluate_approval_requirement(
    actor_kind: ActorKind,
    command_type: CommandType,
    consequence_level: ConsequenceLevel,
    autonomy_mode: AutonomyMode,
    *,
    mutating_accepted_artifact: bool = False,
) -> dict[str, Any]:
    """Return an ApprovalRequirement-shaped dict."""
    if actor_kind == "external-provider" and mutating_accepted_artifact:
        return {
            "schemaVersion": "1.0.0",
            "required": True,
            "reason": "External providers may not mutate accepted artifacts",
            "consequenceLevel": consequence_level,
            "allowedApproverKinds": ["user"],
            "autoAcceptAllowed": False,
        }

    if command_type not in {"artifact.accept-revision", "artifact.propose-revision"}:
        return {
            "schemaVersion": "1.0.0",
            "required": False,
            "reason": "Command does not require approval gate",
            "consequenceLevel": consequence_level,
            "allowedApproverKinds": ["user"],
            "autoAcceptAllowed": True,
        }

    high_or_safety = consequence_level in {"high", "safety-critical"}

    if actor_kind == "user":
        # Users may approve/reject; auto-accept their own low/medium proposals optionally.
        if command_type == "artifact.accept-revision":
            return {
                "schemaVersion": "1.0.0",
                "required": False,
                "reason": "User may approve or reject",
                "consequenceLevel": consequence_level,
                "allowedApproverKinds": ["user"],
                "autoAcceptAllowed": True,
            }
        return {
            "schemaVersion": "1.0.0",
            "required": False,
            "reason": "User-proposed revision",
            "consequenceLevel": consequence_level,
            "allowedApproverKinds": ["user"],
            "autoAcceptAllowed": not high_or_safety,
        }

    if actor_kind == "execution":
        return {
            "schemaVersion": "1.0.0",
            "required": True,
            "reason": "Execution actors may not approve",
            "consequenceLevel": consequence_level,
            "allowedApproverKinds": ["user"],
            "autoAcceptAllowed": False,
        }

    # agent / system
    if high_or_safety:
        return {
            "schemaVersion": "1.0.0",
            "required": True,
            "reason": "High or safety-critical changes require user approval",
            "consequenceLevel": consequence_level,
            "allowedApproverKinds": ["user"],
            "autoAcceptAllowed": False,
        }

    if autonomy_mode == "collaborate":
        # Consequential (non-trivial) changes require user approval in collaborate mode.
        if consequence_level in {"medium", "high", "safety-critical"}:
            return {
                "schemaVersion": "1.0.0",
                "required": True,
                "reason": "Consequential revision in collaborate mode",
                "consequenceLevel": consequence_level,
                "allowedApproverKinds": ["user"],
                "autoAcceptAllowed": False,
            }
        return {
            "schemaVersion": "1.0.0",
            "required": False,
            "reason": "Low-consequence change in collaborate mode",
            "consequenceLevel": consequence_level,
            "allowedApproverKinds": ["user"],
            "autoAcceptAllowed": True,
        }

    # delegate: reversible low-consequence may auto-accept
    if consequence_level == "low":
        return {
            "schemaVersion": "1.0.0",
            "required": False,
            "reason": "Reversible low-consequence change in delegate mode",
            "consequenceLevel": consequence_level,
            "allowedApproverKinds": ["user", "agent"],
            "autoAcceptAllowed": True,
        }

    return {
        "schemaVersion": "1.0.0",
        "required": True,
        "reason": "Non-low consequence change requires user approval in delegate mode",
        "consequenceLevel": consequence_level,
        "allowedApproverKinds": ["user"],
        "autoAcceptAllowed": False,
    }
