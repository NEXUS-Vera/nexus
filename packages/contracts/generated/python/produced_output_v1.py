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

class EntityReference(TypedDict, closed=True):
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
        'analysis',
        'test-plan',
        'risk-register',
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

class Attribution(TypedDict, closed=True):
    actorId: str
    actorType: Literal['user', 'vera', 'embedded-systems-agent', 'shared', 'system']
    displayName: NotRequired[str]
    schemaVersion: Literal['1.0.0']

class SourceReference(TypedDict, closed=True):
    attribution: NotRequired[Attribution]
    evidenceId: str
    evidenceStrength: Literal['direct', 'supporting', 'inferred', 'contradicting']
    schemaVersion: Literal['1.0.0']
    sourceId: str
    sourceLocator: NotRequired[str]
    sourceType: Literal[
        'user-turn',
        'project-policy',
        'document',
        'external-source',
        'calculation',
        'test-result',
        'agent-inference',
    ]
    supportedClaim: NotRequired[str]

class Provenance(TypedDict, closed=True):
    derivedFromIds: NotRequired[list[str]]
    notes: NotRequired[str]
    schemaVersion: Literal['1.0.0']
    sourceReference: NotRequired[SourceReference | str]
    sourceType: Literal[
        'fixture',
        'component-plan',
        'user',
        'llm-derived',
        'manufacturer-datasheet',
        'external-provider',
        'runtime-output',
        'derived',
        'unknown',
    ]

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
    entityReferences: NotRequired[list[EntityReference]]
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
    provenance: NotRequired[Provenance]
    providerId: NotRequired[str]
    schemaVersion: Literal['1.0.0']
    supports: list[Support]
    workspaceId: str
