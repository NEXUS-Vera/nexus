# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, TypeAlias

from typing_extensions import TypedDict

class ReasonByArtifactItem(TypedDict, closed=True):
    artifactType: Literal[
        'project-brief',
        'requirement-set',
        'functional-architecture',
        'next-action',
        'component-plan',
        'code-scratch',
        'firmware',
    ]
    reason: str

class ProjectImpactAnalysisV1(TypedDict, closed=True):
    affected: list[
        Literal[
            'project-brief',
            'requirement-set',
            'functional-architecture',
            'next-action',
            'component-plan',
            'code-scratch',
            'firmware',
        ]
    ]
    changed: list[
        Literal[
            'project-brief',
            'requirement-set',
            'functional-architecture',
            'next-action',
            'component-plan',
            'code-scratch',
            'firmware',
        ]
    ]
    reasonByArtifact: list[ReasonByArtifactItem]
    regenerate: list[
        Literal[
            'project-brief',
            'requirement-set',
            'functional-architecture',
            'next-action',
            'component-plan',
            'code-scratch',
            'firmware',
        ]
    ]
    schemaVersion: Literal['1.0.0']
    stale: list[
        Literal[
            'project-brief',
            'requirement-set',
            'functional-architecture',
            'next-action',
            'component-plan',
            'code-scratch',
            'firmware',
        ]
    ]
    unchanged: list[
        Literal[
            'project-brief',
            'requirement-set',
            'functional-architecture',
            'next-action',
            'component-plan',
            'code-scratch',
            'firmware',
        ]
    ]

ArtifactType: TypeAlias = Literal[
    'project-brief',
    'requirement-set',
    'functional-architecture',
    'next-action',
    'component-plan',
    'code-scratch',
    'firmware',
]

ArtifactTypeList: TypeAlias = list[
    Literal[
        'project-brief',
        'requirement-set',
        'functional-architecture',
        'next-action',
        'component-plan',
        'code-scratch',
        'firmware',
    ]
]
