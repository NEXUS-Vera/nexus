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
        'electrical-architecture',
        'physical-architecture',
        'analysis',
        'test-plan',
        'risk-register',
        'execution-plan',
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
            'electrical-architecture',
            'physical-architecture',
            'analysis',
            'test-plan',
            'risk-register',
            'execution-plan',
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
            'electrical-architecture',
            'physical-architecture',
            'analysis',
            'test-plan',
            'risk-register',
            'execution-plan',
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
            'electrical-architecture',
            'physical-architecture',
            'analysis',
            'test-plan',
            'risk-register',
            'execution-plan',
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
            'electrical-architecture',
            'physical-architecture',
            'analysis',
            'test-plan',
            'risk-register',
            'execution-plan',
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
            'electrical-architecture',
            'physical-architecture',
            'analysis',
            'test-plan',
            'risk-register',
            'execution-plan',
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
    'electrical-architecture',
    'physical-architecture',
    'analysis',
    'test-plan',
    'risk-register',
    'execution-plan',
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
        'electrical-architecture',
        'physical-architecture',
        'analysis',
        'test-plan',
        'risk-register',
        'execution-plan',
    ]
]
