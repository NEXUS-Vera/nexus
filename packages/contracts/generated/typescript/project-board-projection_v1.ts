/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export type ArtifactType =
  'project-brief' | 'requirement-set' | 'functional-architecture' | 'next-action' | 'component-plan';
export type ArtifactType1 =
  'project-brief' | 'requirement-set' | 'functional-architecture' | 'next-action' | 'component-plan';

export interface ProjectBoardProjection {
  artifactSummaries: {
    approvalStatus: 'not-required' | 'proposed' | 'awaiting-user' | 'user-approved' | 'agent-decided' | 'rejected';
    artifactId: string;
    artifactType: ArtifactType;
    artifactVersion: number;
    blockerCount: number;
    evidenceStatus: 'unverified' | 'inferred' | 'partially-grounded' | 'grounded' | 'calculated' | 'tested';
    lastChangedAt: string;
    lastExecutionStatus?:
      | 'queued'
      | 'starting'
      | 'running'
      | 'completed'
      | 'completed-with-warnings'
      | 'failed'
      | 'cancelled'
      | 'timed-out'
      | 'stale';
    lifecycleStatus: 'drafted' | 'ready' | 'affected' | 'stale' | 'blocked' | 'superseded' | 'archived';
    openQuestionCount: number;
    workspaceStatus: 'none' | 'creating' | 'ready' | 'dirty' | 'validating' | 'blocked' | 'archived';
  }[];
  blockingIssueCount: number;
  currentPhase: 'DEFINE' | 'DESIGN' | 'BUILD' | 'VERIFY';
  evidenceSummary: {
    contradictedCount: number;
    testedCount: number;
    totalCount: number;
    unverifiedCount: number;
  };
  nextActionSummary: {
    artifactId: string;
    artifactVersion: number;
    blockerCount?: number;
    priority: 'low' | 'medium' | 'high' | 'blocking';
    title: string;
  } | null;
  openQuestionCount: number;
  projectId: string;
  projectStateVersion: number;
  projectTitle: string;
  projectionVersion: number;
  recentChanges: {
    eventId: string;
    eventType:
      | 'workspace.created'
      | 'workspace.snapshot-created'
      | 'artifact.revision-proposed'
      | 'artifact.revision-accepted'
      | 'artifact.revision-rejected'
      | 'artifact.marked-affected'
      | 'artifact.superseded'
      | 'execution.queued'
      | 'execution.started'
      | 'execution.completed'
      | 'execution.failed'
      | 'output.produced'
      | 'evidence.attached'
      | 'evidence.contradicted'
      | 'evidence.superseded'
      | 'question.opened'
      | 'question.resolved'
      | 'decision.accepted'
      | 'decision.reversed';
    occurredAt: string;
    summary: string;
  }[];
  recentExecutionSummaries: {
    artifactType?: ArtifactType1;
    capability:
      | 'structured-validation'
      | 'fake-execution'
      | 'file-workspace'
      | 'embedded-build'
      | 'python-kernel'
      | 'circuit-simulation'
      | 'architecture-export';
    completedAt?: string;
    executionRunId: string;
    startedAt: string;
    status:
      | 'queued'
      | 'starting'
      | 'running'
      | 'completed'
      | 'completed-with-warnings'
      | 'failed'
      | 'cancelled'
      | 'timed-out'
      | 'stale';
  }[];
  schemaVersion: '1.0.0';
  updatedAt: string;
}
