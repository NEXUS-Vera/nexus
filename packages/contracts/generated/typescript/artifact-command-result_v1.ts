/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export type ArtifactType =
  | 'project-brief'
  | 'requirement-set'
  | 'functional-architecture'
  | 'next-action'
  | 'component-plan'
  | 'electrical-architecture'
  | 'physical-architecture'
  | 'code-scratch'
  | 'firmware'
  | 'analysis'
  | 'test-plan'
  | 'risk-register';

export interface ArtifactCommandResult {
  artifactId: string;
  commandId: string;
  commandRunId: string;
  completedAt?: string;
  error?: {
    code: string;
    message: string;
  };
  evidenceReferences: string[];
  executionRunId?: string;
  issueReferences: string[];
  outputReferences: string[];
  producedArtifactReference?: {
    artifactId: string;
    artifactType: ArtifactType;
    artifactVersion: number;
  };
  projectId: string;
  proposalId?: string;
  resultPayload?: {
    [k: string]: any;
  };
  schemaVersion: '1.0.0';
  snapshotId?: string;
  startedAt: string;
  status: 'accepted' | 'running' | 'completed' | 'completed-with-warnings' | 'rejected' | 'failed' | 'conflicted';
  workspaceId?: string;
}
