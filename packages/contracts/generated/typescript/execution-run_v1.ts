/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export interface ExecutionRun {
  artifactId?: string;
  baseArtifactVersion: number;
  baseProjectStateVersion: number;
  capability:
    | 'structured-validation'
    | 'fake-execution'
    | 'file-workspace'
    | 'embedded-build'
    | 'python-kernel'
    | 'circuit-simulation'
    | 'architecture-export';
  completedAt?: string;
  error?: {
    code: string;
    message: string;
  };
  evidenceReferences: string[];
  executionRequestId: string;
  executionRunId: string;
  inputSnapshotId: string;
  logReference?: string;
  outputReferences: string[];
  projectId: string;
  providerId: string;
  schemaVersion: '1.0.0';
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
  workspaceId?: string;
}
