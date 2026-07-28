/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export interface ValidationIssue {
  artifactId?: string;
  blocking: boolean;
  code: string;
  createdAt: string;
  issueId: string;
  itemId?: string;
  message: string;
  projectId: string;
  resolutionStatus: 'open' | 'resolved';
  resolutionType: 'user-input' | 'artifact-regeneration' | 'manual-review' | 'automatic-fix' | 'not-applicable';
  resolvedAt?: string;
  schemaVersion: '1.0.0';
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  suggestedResolution?: string;
}
