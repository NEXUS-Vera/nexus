/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export interface WorkspaceFile {
  contentHash: string;
  /**
   * Opaque content-addressed blob reference; never a host filesystem path.
   */
  contentReference: string;
  createdAt: string;
  generatedFrom?: string;
  mediaType?: string;
  modifiedByUser: boolean;
  origin: 'USER' | 'GENERATED' | 'SYSTEM' | 'RUNTIME_OUTPUT';
  /**
   * Normalized relative workspace path using '/' separators.
   */
  path: string;
  schemaVersion: '1.0.0';
  sizeBytes: number;
  updatedAt: string;
  updatedBy?: ActorReference;
  workspaceId: string;
  writePolicy: 'USER_EDITABLE' | 'REGENERATION_MANAGED' | 'READ_ONLY' | 'EPHEMERAL';
}
export interface ActorReference {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
