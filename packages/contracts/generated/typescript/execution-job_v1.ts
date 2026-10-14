/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export interface ExecutionJob {
  /**
   * Infrastructure cleanup warning that must not rewrite a successful engineering result into failed.
   */
  cleanupWarning?: string;
  commandSpec: ExecutionCommandSpec;
  completedAt?: string;
  createdAt: string;
  executionJobId: string;
  executionRunId: string;
  exitCode?: number;
  failure?: {
    code: string;
    message: string;
  };
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
  logTruncated?: boolean;
  projectId: string;
  queuePosition?: number;
  /**
   * Opaque runtime ownership handle for crash recovery (container id, etc.).
   */
  runtimeHandle?: {
    containerId?: string;
    pid?: number;
  };
  runtimeIdentity: {
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
  runtimeKind: 'process' | 'container';
  schemaVersion: '1.0.0';
  startedAt?: string;
  status: 'queued' | 'starting' | 'running' | 'cancelling' | 'succeeded' | 'failed' | 'timed-out' | 'cancelled';
  workspaceSnapshotId: string;
}
export interface ExecutionCommandSpec {
  /**
   * @maxItems 64
   */
  arguments: string[];
  /**
   * @maxItems 32
   */
  declaredOutputs: {
    kind: 'result' | 'artifact' | 'log';
    path: string;
  }[];
  /**
   * Explicit non-secret environment values. Backend secrets must never appear here.
   *
   * @maxItems 64
   */
  environment: {
    name: string;
    value: string;
  }[];
  /**
   * Executable name or workspace-relative path. Must not be a host absolute path.
   */
  executable: string;
  schemaVersion: '1.0.0';
  /**
   * Workspace-relative working directory scoped to the materialized snapshot. Empty string means snapshot root.
   */
  workingDirectory: string;
}
