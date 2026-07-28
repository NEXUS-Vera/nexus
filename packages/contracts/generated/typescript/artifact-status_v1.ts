/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export interface ArtifactStatus {
  approvalStatus: 'not-required' | 'proposed' | 'awaiting-user' | 'user-approved' | 'agent-decided' | 'rejected';
  evidenceStatus: 'unverified' | 'inferred' | 'partially-grounded' | 'grounded' | 'calculated' | 'tested';
  lifecycleStatus: 'drafted' | 'ready' | 'affected' | 'stale' | 'blocked' | 'superseded' | 'archived';
}
