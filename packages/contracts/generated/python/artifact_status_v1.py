# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, TypeAlias

from typing_extensions import TypedDict

class ArtifactStatusV1(TypedDict, closed=True):
    approvalStatus: Literal[
        'not-required',
        'proposed',
        'awaiting-user',
        'user-approved',
        'agent-decided',
        'rejected',
    ]
    evidenceStatus: Literal[
        'unverified',
        'inferred',
        'partially-grounded',
        'grounded',
        'calculated',
        'tested',
    ]
    lifecycleStatus: Literal[
        'drafted', 'ready', 'affected', 'stale', 'blocked', 'superseded', 'archived'
    ]

ApprovalStatus: TypeAlias = Literal[
    'not-required',
    'proposed',
    'awaiting-user',
    'user-approved',
    'agent-decided',
    'rejected',
]

EvidenceStatus: TypeAlias = Literal[
    'unverified', 'inferred', 'partially-grounded', 'grounded', 'calculated', 'tested'
]

LifecycleStatus: TypeAlias = Literal[
    'drafted', 'ready', 'affected', 'stale', 'blocked', 'superseded', 'archived'
]
