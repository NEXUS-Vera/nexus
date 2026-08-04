# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal

from typing_extensions import TypedDict

class ArtifactAuthorityV1(TypedDict, closed=True):
    actorKind: Literal['user', 'agent', 'system', 'execution', 'external-provider']
    authorities: list[
        Literal[
            'propose',
            'edit-draft',
            'execute',
            'validate',
            'approve',
            'reject',
            'supersede',
        ]
    ]
    schemaVersion: Literal['1.0.0']
