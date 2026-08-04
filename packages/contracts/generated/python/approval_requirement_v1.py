# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

class ApprovalRequirementV1(TypedDict, closed=True):
    allowedApproverKinds: list[Literal['user', 'agent', 'system']]
    autoAcceptAllowed: NotRequired[bool]
    consequenceLevel: Literal['low', 'medium', 'high', 'safety-critical']
    reason: str
    required: bool
    schemaVersion: Literal['1.0.0']
