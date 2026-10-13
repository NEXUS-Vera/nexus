/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export interface ExecutionRequest {
  artifactId: string;
  capability:
    | 'structured-validation'
    | 'fake-execution'
    | 'file-workspace'
    | 'embedded-build'
    | 'python-kernel'
    | 'circuit-simulation'
    | 'architecture-export';
  executionRequestId: string;
  projectId: string;
  requestedAt: string;
  requestedBy: ActorReference;
  resourceLimits: {
    maxDurationMs: number;
    maxOutputBytes?: number;
  };
  schemaVersion: '1.0.0';
  snapshotId: string;
  workspaceId: string;
}
export interface ActorReference {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
