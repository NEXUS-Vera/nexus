/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export interface ExternalWorkspaceReference {
  createdAt: string;
  displayLabel?: string;
  externalReferenceId: string;
  lastSyncedAt?: string;
  providerId: 'fake' | 'wokwi' | 'flux' | 'jupyter' | 'github' | 'kicad';
  schemaVersion: '1.0.0';
  syncStatus: 'unbound' | 'bound' | 'stale' | 'error';
  updatedAt: string;
}
