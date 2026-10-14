# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

class ProjectGraphNodeV1(TypedDict, closed=True):
    artifactType: NotRequired[
        Literal[
            'project-brief',
            'requirement-set',
            'functional-architecture',
            'next-action',
            'component-plan',
            'code-scratch',
        ]
    ]
    createdAt: str
    createdByEventId: NotRequired[str]
    label: str
    nodeId: str
    nodeType: Literal[
        'artifact',
        'artifact-revision',
        'requirement',
        'architecture-node',
        'question',
        'validation-issue',
        'decision',
        'evidence',
        'execution',
        'output',
        'workspace',
    ]
    projectId: str
    refId: NotRequired[str]
    schemaVersion: Literal['1.0.0']
