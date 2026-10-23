/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export type ArtifactType =
  | 'project-brief'
  | 'requirement-set'
  | 'functional-architecture'
  | 'next-action'
  | 'component-plan'
  | 'code-scratch'
  | 'firmware'
  | 'electrical-architecture'
  | 'physical-architecture'
  | 'analysis'
  | 'test-plan'
  | 'risk-register'
  | 'execution-plan';
export type ArtifactType1 =
  | 'project-brief'
  | 'requirement-set'
  | 'functional-architecture'
  | 'next-action'
  | 'component-plan'
  | 'code-scratch'
  | 'firmware'
  | 'electrical-architecture'
  | 'physical-architecture'
  | 'analysis'
  | 'test-plan'
  | 'risk-register'
  | 'execution-plan';

export interface ProjectEvent {
  actor: ActorReference;
  causationId?: string;
  correlationId?: string;
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
    | 'decision.reversed'
    | 'component-plan.created'
    | 'component-role.identified'
    | 'component-candidate.proposed'
    | 'component-candidate.rejected'
    | 'component-selection.proposed'
    | 'component-selection.approved'
    | 'component-selection.rejected'
    | 'compatibility-check.recorded'
    | 'component-plan.revised'
    | 'component-plan.marked-stale'
    | 'workspace.scaffold-generated'
    | 'workspace.patch-proposed'
    | 'workspace.patch-applied'
    | 'workspace.patch-discarded'
    | 'verification.invalidated'
    | 'verification.revalidated'
    | 'workspace.plan-materialized';
  occurredAt: string;
  payload: {
    artifactId?: string;
    artifactType?: ArtifactType;
    artifactVersion?: number;
    baseProjectStateVersion?: number;
    baseSnapshotId?: string;
    capability?:
      | 'structured-validation'
      | 'fake-execution'
      | 'file-workspace'
      | 'embedded-build'
      | 'python-kernel'
      | 'circuit-simulation'
      | 'architecture-export'
      | 'sandbox-execution';
    decisionId?: string;
    eventId?: string;
    evidenceId?: string;
    evidenceStatus?: 'unverified' | 'inferred' | 'partially-grounded' | 'grounded' | 'calculated' | 'tested';
    executionRunId?: string;
    fromVersion?: number;
    generatedFiles?: {
      contentHash: string;
      path: string;
    }[];
    generationId?: string;
    generationKind?: 'scaffold' | 'patch';
    generatorId?: string;
    generatorVersion?: string;
    inputArtifactReferences?: {
      artifactId?: string;
      artifactType: ArtifactType1;
      artifactVersion: number;
    }[];
    outputId?: string;
    outputType?:
      | 'validation-report'
      | 'log'
      | 'structured-result'
      | 'file-reference'
      | 'plot-reference'
      | 'binary-reference'
      | 'test-report';
    patchOperations?: {
      contentHash?: string;
      expectedBaseHash?: string;
      operationType: 'create-file' | 'replace-file' | 'delete-file';
      path: string;
    }[];
    patchProposalId?: string;
    path?: string[];
    proposalId?: string;
    questionId?: string;
    reason?: string;
    requestedChange?: string;
    requirementIds?: string[];
    resultingArtifactId?: string;
    resultingArtifactVersion?: number;
    scaffoldProfileId?: string;
    scaffoldProfileVersion?: string;
    snapshotId?: string;
    status?: string;
    summary?: string;
    supersededBy?: string;
    testId?: string;
    toVersion?: number;
    triggerArtifactId?: string;
    triggerArtifactType?: string;
    workspaceId?: string;
  };
  projectId: string;
  schemaVersion: '1.0.0';
  subject: {
    subjectId: string;
    subjectType:
      | 'workspace'
      | 'artifact'
      | 'proposal'
      | 'execution'
      | 'output'
      | 'evidence'
      | 'question'
      | 'decision'
      | 'snapshot';
  };
}
export interface ActorReference {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
