# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired, TypeAlias

from typing_extensions import TypedDict

class ArtifactDependencyV1(TypedDict, closed=True):
    createdAt: str
    dependencyId: str
    dependencyKind: Literal[
        'derives-from', 'constrains', 'covers', 'blocks', 'invalidates'
    ]
    projectId: str
    reason: str
    schemaVersion: Literal['1.0.0']
    sourceArtifactId: NotRequired[str]
    sourceArtifactType: Literal[
        'project-brief',
        'requirement-set',
        'functional-architecture',
        'next-action',
        'component-plan',
        'code-scratch',
        'firmware',
        'electrical-architecture',
        'physical-architecture',
        'analysis',
        'test-plan',
        'risk-register',
    ]
    targetArtifactId: NotRequired[str]
    targetArtifactType: Literal[
        'project-brief',
        'requirement-set',
        'functional-architecture',
        'next-action',
        'component-plan',
        'code-scratch',
        'firmware',
        'electrical-architecture',
        'physical-architecture',
        'analysis',
        'test-plan',
        'risk-register',
    ]

ArtifactType: TypeAlias = Literal[
    'project-brief',
    'requirement-set',
    'functional-architecture',
    'next-action',
    'component-plan',
    'code-scratch',
    'firmware',
    'electrical-architecture',
    'physical-architecture',
    'analysis',
    'test-plan',
    'risk-register',
]
