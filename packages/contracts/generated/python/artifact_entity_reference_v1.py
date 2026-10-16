# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

class ArtifactEntityReferenceV1(TypedDict, closed=True):
    artifactId: str
    artifactType: Literal[
        'project-brief',
        'requirement-set',
        'functional-architecture',
        'next-action',
        'component-plan',
        'code-scratch',
        'firmware',
        'electrical-architecture',
        'physical-architecture',
    ]
    artifactVersion: NotRequired[int]
    displayLabel: NotRequired[str]
    entityId: str
    entityType: Literal[
        'requirement',
        'functional-node',
        'functional-edge',
        'component-role',
        'component-candidate',
        'selection-decision',
        'electrical-node',
        'electrical-connection',
        'electrical-interface',
        'power-domain',
        'physical-node',
        'physical-relationship',
        'physical-zone',
        'open-question',
        'other',
    ]
    schemaVersion: Literal['1.0.0']
