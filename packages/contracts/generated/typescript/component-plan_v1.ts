/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export interface ComponentPlanContent {
  approvalStatus: 'not-required' | 'proposed' | 'awaiting-user' | 'user-approved' | 'agent-decided' | 'rejected';
  candidateCount: number;
  constraintSummary: string;
  selectionState: 'draft' | 'proposed' | 'accepted' | 'blocked';
  unresolvedCompatibilityChecks: string[];
}
