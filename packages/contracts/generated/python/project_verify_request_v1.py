# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

class RequestedBy(TypedDict, closed=True):
    actorId: str
    actorType: Literal['user']
    displayName: NotRequired[str]
    schemaVersion: Literal['1.0.0']

class ProjectVerifyRequestV1(TypedDict, closed=True):
    executionRunId: NotRequired[str]
    requestedBy: RequestedBy
    requireReal: Literal[True]
    schemaVersion: NotRequired[Literal['1.0.0']]
