# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

class CreatedBy(TypedDict, closed=True):
    actorId: str
    actorType: Literal['user', 'vera', 'embedded-systems-agent', 'shared', 'system']
    displayName: NotRequired[str]
    schemaVersion: Literal['1.0.0']

class ExternalWorkspaceReference(TypedDict, closed=True):
    createdAt: str
    displayLabel: NotRequired[str]
    externalReferenceId: str
    lastSyncedAt: NotRequired[str]
    providerId: Literal['fake', 'wokwi', 'flux', 'jupyter', 'github', 'kicad']
    schemaVersion: Literal['1.0.0']
    syncStatus: Literal['unbound', 'bound', 'stale', 'error']
    updatedAt: str

class WorkspaceDescriptorV1(TypedDict, closed=True):
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
    baseArtifactVersion: int
    baseProjectStateVersion: int
    createdAt: str
    createdBy: CreatedBy
    currentSnapshotId: NotRequired[str]
    externalWorkspaceReferences: list[ExternalWorkspaceReference]
    projectId: str
    runtimeCapabilityRequirements: list[
        Literal[
            'structured-validation',
            'fake-execution',
            'file-workspace',
            'sandbox-execution',
            'embedded-build',
            'python-kernel',
            'circuit-simulation',
            'architecture-export',
        ]
    ]
    schemaVersion: Literal['1.0.0']
    status: Literal['creating', 'ready', 'dirty', 'validating', 'blocked', 'archived']
    updatedAt: str
    workspaceId: str
    workspaceType: Literal[
        'structured-document',
        'graph-workspace',
        'comparison-workspace',
        'code-workspace',
        'notebook-workspace',
        'test-workspace',
        'risk-workspace',
        'focused-action',
    ]
