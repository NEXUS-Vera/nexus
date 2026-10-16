/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export interface ExecutionLogChunk {
  content: string;
  executionJobId: string;
  schemaVersion: '1.0.0';
  sequence: number;
  stream: 'stdout' | 'stderr' | 'system';
  timestamp: string;
  truncated?: boolean;
}
