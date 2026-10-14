# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Any, Literal, NotRequired

from typing_extensions import TypedDict

class Content(TypedDict, closed=True):
    kind: Literal['inline-structured']
    structuredResult: dict[str, Any]

class Content1(TypedDict, closed=True):
    kind: Literal['storage-reference']
    storageKind: Literal['postgres-jsonb', 'object-store', 'file-store']
    uri: str

class Support(TypedDict, closed=True):
    supportKind: Literal[
        'artifact', 'requirement', 'architecture-node', 'validation-issue', 'decision'
    ]
    targetId: str

class ProducedOutputV1(TypedDict, closed=True):
    artifactId: str
    content: Content | Content1
    contentDigest: str
    createdAt: str
    evidenceStatus: Literal[
        'unverified',
        'inferred',
        'partially-grounded',
        'grounded',
        'calculated',
        'tested',
    ]
    executionRunId: str
    mediaType: str
    name: str
    outputId: str
    outputType: Literal[
        'validation-report',
        'log',
        'structured-result',
        'file-reference',
        'plot-reference',
        'binary-reference',
        'test-report',
    ]
    projectId: str
    providerId: NotRequired[str]
    schemaVersion: Literal['1.0.0']
    supports: list[Support]
    workspaceId: str
