/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export interface ProducedOutput {
  artifactId: string;
  content:
    | {
        kind: 'inline-structured';
        structuredResult: {
          [k: string]: any;
        };
      }
    | {
        kind: 'storage-reference';
        storageKind: 'postgres-jsonb' | 'object-store' | 'file-store';
        uri: string;
      };
  contentDigest: string;
  createdAt: string;
  evidenceStatus: 'unverified' | 'inferred' | 'partially-grounded' | 'grounded' | 'calculated' | 'tested';
  executionRunId: string;
  mediaType: string;
  name: string;
  outputId: string;
  outputType:
    | 'validation-report'
    | 'log'
    | 'structured-result'
    | 'file-reference'
    | 'plot-reference'
    | 'binary-reference'
    | 'test-report';
  projectId: string;
  providerId?: string;
  schemaVersion: '1.0.0';
  supports: {
    supportKind: 'artifact' | 'requirement' | 'architecture-node' | 'validation-issue' | 'decision';
    targetId: string;
  }[];
  workspaceId: string;
}
