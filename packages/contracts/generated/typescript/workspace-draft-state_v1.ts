/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export interface WorkspaceDraftState {
  baseArtifactVersion: number;
  baseProjectStateVersion: number;
  content: {
    [k: string]: any;
  };
  createdAt: string;
  draftVersion: number;
  schemaVersion: '1.0.0';
  updatedAt: string;
  updatedBy: ActorReference;
  validationState: 'unvalidated' | 'valid' | 'invalid' | 'stale';
  workspaceId: string;
}
export interface ActorReference {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
