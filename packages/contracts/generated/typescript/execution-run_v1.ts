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
    | 'sandbox-execution'
    | 'embedded-build'
    | 'python-kernel'
    | 'circuit-simulation'
    | 'architecture-export';
  /**
   * Infrastructure cleanup warning after a successful or terminal run.
   */
  cleanupWarning?: string;
  completedAt?: string;
  error?: {
    code: string;
    message: string;
  };
  evidenceReferences: string[];
  /**
   * Optional infrastructure job id for Nexus-owned sandboxed execution.
   */
  executionJobId?: string;
  executionRequestId: string;
  executionRunId: string;
  inputOutputReferences?: string[];
  inputSnapshotId: string;
  logReference?: string;
  outputReferences: string[];
  projectId: string;
  providerId: string;
  /**
   * Runtime fingerprint recorded for job-backed executions.
   */
  runtimeIdentity?: {
    commandSpecVersion: '1.0.0';
    executableFingerprint?: string;
    imageDigest?: string;
    imageReference?: string;
    isolationGuarantees?: string[];
    isolationLimitations?: string[];
    limits: {
      cpuMillis?: number;
      memoryBytes?: number;
      outputFileCount: number;
      processCount?: number;
      producedOutputBytes: number;
      stderrBytes: number;
      stdoutBytes: number;
      totalLogBytes: number;
      wallTimeMs: number;
      workspaceBytes: number;
    };
    networkPolicy?: 'none' | 'restricted';
    runtimeKind: 'process' | 'container';
    runtimeVersion: string;
    securityLevel?: 'limited' | 'isolated';
    workspaceManifestDigest: string;
    workspaceSnapshotId: string;
  };
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
