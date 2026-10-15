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
  | 'physical-architecture';

/**
 * Lightweight append-only history of a project: the turns that were submitted, the workflow runs they triggered, every artifact revision produced, and the user-facing responses returned.
 */
export interface ProjectHistory {
  artifactRevisions: {
    artifactId: string;
    artifactType: ArtifactType;
    artifactVersion: number;
    createdAt: string;
    lifecycleStatus: 'drafted' | 'ready' | 'affected' | 'stale' | 'blocked' | 'superseded' | 'archived';
    sourceTurnId: string;
    supersedesArtifactId?: string;
    supersedesArtifactVersion?: number;
  }[];
  projectId: string;
  schemaVersion: '1.0.0';
  turns: {
    rawUserMessage: string;
    timestamp: string;
    turnId: string;
  }[];
  veraResponses: {
    timestamp: string;
    turnId: string;
    userFacingMessage: string;
  }[];
  workflowRuns: {
    completedAt?: string;
    startedAt: string;
    status: 'pending' | 'running' | 'completed' | 'completed-with-warnings' | 'failed';
    turnId: string;
    workflowRunId: string;
    workflowType: 'embedded-project-initialization' | 'embedded-project-modification';
  }[];
}
