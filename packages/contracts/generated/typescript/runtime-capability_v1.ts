/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export interface RuntimeCapability {
  available: boolean;
  capabilityId:
    | 'structured-validation'
    | 'fake-execution'
    | 'file-workspace'
    | 'embedded-build'
    | 'python-kernel'
    | 'circuit-simulation'
    | 'architecture-export';
  description?: string;
  displayName: string;
  providerId: string;
  schemaVersion: '1.0.0';
}
