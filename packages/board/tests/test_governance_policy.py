"""Governance policy tests."""

from __future__ import annotations

from nexus_board.governance.policy import (
    actor_kind_from_actor_type,
    evaluate_approval_requirement,
    may_perform_command,
)


def test_actor_kind_mapping() -> None:
    assert actor_kind_from_actor_type("user") == "user"
    assert actor_kind_from_actor_type("vera") == "agent"
    assert actor_kind_from_actor_type("embedded-systems-agent") == "agent"
    assert actor_kind_from_actor_type("system") == "system"
    assert actor_kind_from_actor_type("shared") == "system"


def test_user_may_approve_reject() -> None:
    assert may_perform_command("user", "artifact.accept-revision")
    assert may_perform_command("user", "artifact.reject-revision")
    assert not may_perform_command("agent", "artifact.accept-revision")
    assert not may_perform_command("execution", "artifact.accept-revision")


def test_collaborate_medium_requires_user_approval() -> None:
    req = evaluate_approval_requirement(
        "agent",
        "artifact.propose-revision",
        "medium",
        "collaborate",
    )
    assert req["required"] is True
    assert req["autoAcceptAllowed"] is False
    assert "user" in req["allowedApproverKinds"]


def test_delegate_low_may_auto_accept() -> None:
    req = evaluate_approval_requirement(
        "agent",
        "artifact.propose-revision",
        "low",
        "delegate",
    )
    assert req["required"] is False
    assert req["autoAcceptAllowed"] is True


def test_high_requires_user_even_in_delegate() -> None:
    req = evaluate_approval_requirement(
        "agent",
        "artifact.accept-revision",
        "high",
        "delegate",
    )
    assert req["required"] is True
    assert req["autoAcceptAllowed"] is False
    assert req["allowedApproverKinds"] == ["user"]


def test_external_provider_cannot_mutate_accepted() -> None:
    req = evaluate_approval_requirement(
        "external-provider",
        "artifact.accept-revision",
        "low",
        "delegate",
        mutating_accepted_artifact=True,
    )
    assert req["required"] is True
    assert req["autoAcceptAllowed"] is False
