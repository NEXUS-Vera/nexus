# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

class Actor(TypedDict, closed=True):
    actorId: str
    actorType: Literal['user', 'vera', 'embedded-systems-agent', 'shared', 'system']
    displayName: NotRequired[str]
    schemaVersion: Literal['1.0.0']

class GeneratedFile(TypedDict, closed=True):
    contentHash: str
    path: str

class InputArtifactReference(TypedDict, closed=True):
    artifactId: NotRequired[str]
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
    artifactVersion: int

class PatchOperation(TypedDict, closed=True):
    contentHash: NotRequired[str]
    expectedBaseHash: NotRequired[str]
    operationType: Literal['create-file', 'replace-file', 'delete-file']
    path: str

class Payload(TypedDict, closed=True):
    artifactId: NotRequired[str]
    artifactType: NotRequired[
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
    artifactVersion: NotRequired[int]
    baseProjectStateVersion: NotRequired[int]
    baseSnapshotId: NotRequired[str]
    capability: NotRequired[
        Literal[
            'structured-validation',
            'fake-execution',
            'file-workspace',
            'embedded-build',
            'python-kernel',
            'circuit-simulation',
            'architecture-export',
            'sandbox-execution',
        ]
    ]
    decisionId: NotRequired[str]
    eventId: NotRequired[str]
    evidenceId: NotRequired[str]
    evidenceStatus: NotRequired[
        Literal[
            'unverified',
            'inferred',
            'partially-grounded',
            'grounded',
            'calculated',
            'tested',
        ]
    ]
    executionRunId: NotRequired[str]
    fromVersion: NotRequired[int]
    generatedFiles: NotRequired[list[GeneratedFile]]
    generationId: NotRequired[str]
    generationKind: NotRequired[Literal['scaffold', 'patch']]
    generatorId: NotRequired[str]
    generatorVersion: NotRequired[str]
    inputArtifactReferences: NotRequired[list[InputArtifactReference]]
    outputId: NotRequired[str]
    outputType: NotRequired[
        Literal[
            'validation-report',
            'log',
            'structured-result',
            'file-reference',
            'plot-reference',
            'binary-reference',
            'test-report',
        ]
    ]
    patchOperations: NotRequired[list[PatchOperation]]
    patchProposalId: NotRequired[str]
    path: NotRequired[list[str]]
    proposalId: NotRequired[str]
    questionId: NotRequired[str]
    reason: NotRequired[str]
    requestedChange: NotRequired[str]
    requirementIds: NotRequired[list[str]]
    resultingArtifactId: NotRequired[str]
    resultingArtifactVersion: NotRequired[int]
    scaffoldProfileId: NotRequired[str]
    scaffoldProfileVersion: NotRequired[str]
    snapshotId: NotRequired[str]
    status: NotRequired[str]
    summary: NotRequired[str]
    supersededBy: NotRequired[str]
    testId: NotRequired[str]
    toVersion: NotRequired[int]
    triggerArtifactId: NotRequired[str]
    triggerArtifactType: NotRequired[str]
    workspaceId: NotRequired[str]

class Subject(TypedDict, closed=True):
    subjectId: str
    subjectType: Literal[
        'workspace',
        'artifact',
        'proposal',
        'execution',
        'output',
        'evidence',
        'question',
        'decision',
        'snapshot',
    ]

class ProjectEventV1(TypedDict, closed=True):
    actor: Actor
    causationId: NotRequired[str]
    correlationId: NotRequired[str]
    eventId: str
    eventType: Literal[
        'workspace.created',
        'workspace.snapshot-created',
        'artifact.revision-proposed',
        'artifact.revision-accepted',
        'artifact.revision-rejected',
        'artifact.marked-affected',
        'artifact.superseded',
        'execution.queued',
        'execution.started',
        'execution.completed',
        'execution.failed',
        'output.produced',
        'evidence.attached',
        'evidence.contradicted',
        'evidence.superseded',
        'question.opened',
        'question.resolved',
        'decision.accepted',
        'decision.reversed',
        'component-plan.created',
        'component-role.identified',
        'component-candidate.proposed',
        'component-candidate.rejected',
        'component-selection.proposed',
        'component-selection.approved',
        'component-selection.rejected',
        'compatibility-check.recorded',
        'component-plan.revised',
        'component-plan.marked-stale',
        'workspace.scaffold-generated',
        'workspace.patch-proposed',
        'workspace.patch-applied',
        'workspace.patch-discarded',
        'verification.invalidated',
        'verification.revalidated',
        'workspace.plan-materialized',
    ]
    occurredAt: str
    payload: Payload
    projectId: str
    schemaVersion: Literal['1.0.0']
    subject: Subject
