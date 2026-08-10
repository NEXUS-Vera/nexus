# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

class ArtifactSummary(TypedDict, closed=True):
    approvalStatus: Literal[
        'not-required',
        'proposed',
        'awaiting-user',
        'user-approved',
        'agent-decided',
        'rejected',
    ]
    approvedImplementationCount: NotRequired[int]
    artifactId: str
    artifactType: Literal[
        'project-brief',
        'requirement-set',
        'functional-architecture',
        'next-action',
        'component-plan',
        'electrical-architecture',
        'physical-architecture',
    ]
    artifactVersion: int
    awaitingApprovalCount: NotRequired[int]
    blockedRoleCount: NotRequired[int]
    blockerCount: int
    candidateCount: NotRequired[int]
    evidenceStatus: Literal[
        'unverified',
        'inferred',
        'partially-grounded',
        'grounded',
        'calculated',
        'tested',
    ]
    lastChangedAt: str
    lastExecutionStatus: NotRequired[
        Literal[
            'queued',
            'starting',
            'running',
            'completed',
            'completed-with-warnings',
            'failed',
            'cancelled',
            'timed-out',
            'stale',
        ]
    ]
    lifecycleStatus: Literal[
        'drafted', 'ready', 'affected', 'stale', 'blocked', 'superseded', 'archived'
    ]
    maturity: NotRequired[
        Literal[
            'roles-defined',
            'candidates-proposed',
            'candidates-grounded',
            'compatibility-checked',
            'selection-proposed',
            'selection-approved',
            'validated',
        ]
    ]
    nodeCount: NotRequired[int]
    openQuestionCount: int
    provisionalImplementationCount: NotRequired[int]
    provisionalRelationshipCount: NotRequired[int]
    roleCount: NotRequired[int]
    selectedCount: NotRequired[int]
    unresolvedCompatibilityCheckCount: NotRequired[int]
    unresolvedConnectionCount: NotRequired[int]
    unresolvedPlacementCount: NotRequired[int]
    workspaceStatus: Literal[
        'none', 'creating', 'ready', 'dirty', 'validating', 'blocked', 'archived'
    ]

class EvidenceSummary(TypedDict, closed=True):
    contradictedCount: int
    testedCount: int
    totalCount: int
    unverifiedCount: int

class NextActionSummary(TypedDict, closed=True):
    artifactId: str
    artifactVersion: int
    blockerCount: NotRequired[int]
    priority: Literal['low', 'medium', 'high', 'blocking']
    title: str

class RecentChange(TypedDict, closed=True):
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
    ]
    occurredAt: str
    summary: str

class RecentExecutionSummary(TypedDict, closed=True):
    artifactType: NotRequired[
        Literal[
            'project-brief',
            'requirement-set',
            'functional-architecture',
            'next-action',
            'component-plan',
            'electrical-architecture',
            'physical-architecture',
        ]
    ]
    capability: Literal[
        'structured-validation',
        'fake-execution',
        'file-workspace',
        'embedded-build',
        'python-kernel',
        'circuit-simulation',
        'architecture-export',
    ]
    completedAt: NotRequired[str]
    executionRunId: str
    startedAt: str
    status: Literal[
        'queued',
        'starting',
        'running',
        'completed',
        'completed-with-warnings',
        'failed',
        'cancelled',
        'timed-out',
        'stale',
    ]

class ProjectBoardProjectionV1(TypedDict, closed=True):
    artifactSummaries: list[ArtifactSummary]
    blockingIssueCount: int
    currentPhase: Literal['DEFINE', 'DESIGN', 'BUILD', 'VERIFY']
    evidenceSummary: EvidenceSummary
    nextActionSummary: NextActionSummary | None
    openQuestionCount: int
    projectId: str
    projectStateVersion: int
    projectTitle: str
    projectionVersion: int
    recentChanges: list[RecentChange]
    recentExecutionSummaries: list[RecentExecutionSummary]
    schemaVersion: Literal['1.0.0']
    updatedAt: str
