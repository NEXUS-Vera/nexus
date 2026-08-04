/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export interface ArtifactAuthority {
  actorKind: 'user' | 'agent' | 'system' | 'execution' | 'external-provider';
  authorities: ('propose' | 'edit-draft' | 'execute' | 'validate' | 'approve' | 'reject' | 'supersede')[];
  schemaVersion: '1.0.0';
}
