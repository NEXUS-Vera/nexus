# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

class Edge(TypedDict, closed=True):
    createdByEventId: str
    edgeId: str
    edgeType: Literal[
        'depends-on',
        'derives-from',
        'constrains',
        'covers',
        'blocks',
        'invalidates',
        'supports',
        'contradicts',
        'supersedes',
        'produced-by',
        'belongs-to',
        'answers',
    ]
    projectId: str
    reason: NotRequired[str]
    schemaVersion: Literal['1.0.0']
    sourceNodeId: str
    targetNodeId: str
    validFrom: str
    validUntil: NotRequired[str]

class Node(TypedDict, closed=True):
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

class GraphTraversalResultV1(TypedDict, closed=True):
    direction: Literal['upstream', 'downstream', 'neighbors', 'subgraph']
    edgeLimitReached: bool
    edges: list[Edge]
    maxDepth: int
    nodeLimitReached: bool
    nodes: list[Node]
    projectId: str
    rootNodeId: str
    schemaVersion: Literal['1.0.0']
    truncated: bool
