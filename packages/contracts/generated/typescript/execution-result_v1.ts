/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export interface ExecutionResult {
  completedAt: string;
  error?: {
    code: string;
    message: string;
  };
  evidenceReferences: string[];
  executionRunId: string;
  outputReferences: string[];
  schemaVersion: '1.0.0';
  status: 'completed' | 'completed-with-warnings' | 'failed' | 'cancelled' | 'timed-out' | 'stale';
  summary?: string;
}
