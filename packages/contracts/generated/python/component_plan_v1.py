# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal

from typing_extensions import TypedDict

class ComponentPlanV1(TypedDict, closed=True):
    approvalStatus: Literal[
        'not-required',
        'proposed',
        'awaiting-user',
        'user-approved',
        'agent-decided',
        'rejected',
    ]
    candidateCount: int
    constraintSummary: str
    selectionState: Literal['draft', 'proposed', 'accepted', 'blocked']
    unresolvedCompatibilityChecks: list[str]
