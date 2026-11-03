"""Requested actor IDs share the artifact pattern without restricting runtime kinds."""

from typing import Any

import pytest
from nexus_board.errors import CommandValidationError
from nexus_board.services.command_service import validate_requested_actor_id


@pytest.mark.parametrize("actor", [None, [], "actor_0123456789abcdef", 42])
def test_requested_actor_must_be_object(actor: Any) -> None:
    with pytest.raises(CommandValidationError, match="requestedBy: must be an object"):
        validate_requested_actor_id(actor)


@pytest.mark.parametrize(
    "actor_id",
    [
        None,
        42,
        "",
        "actor_" + "a" * 15,
        "other_" + "a" * 16,
        "actor_" + "a" * 16 + "_",
        "actor_" + "é" * 16,
        " actor_" + "a" * 16,
    ],
)
def test_requested_actor_rejects_invalid_id(actor_id: Any) -> None:
    with pytest.raises(CommandValidationError, match=r"requestedBy\.actorId"):
        validate_requested_actor_id({"actorId": actor_id})


def test_requested_actor_requires_id() -> None:
    with pytest.raises(CommandValidationError, match=r"requestedBy\.actorId"):
        validate_requested_actor_id({})


@pytest.mark.parametrize("actor_id", ["actor_aB0123456789CdEf", "actor_" + "Z" * 17])
@pytest.mark.parametrize("kind", [None, "user", "execution", "external-provider"])
def test_requested_actor_accepts_pattern_and_runtime_kinds(actor_id: str, kind: str | None) -> None:
    actor = {"actorId": actor_id}
    if kind is not None:
        actor["actorType"] = kind
    validate_requested_actor_id(actor)
