/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export interface TurnRoute {
  autonomyMode: 'collaborate' | 'delegate';
  chairmanRequiredEventually: boolean;
  complexity: 'low' | 'medium' | 'high' | 'unknown';
  domain: 'embedded-products';
  projectOperation: 'create-project' | 'none';
  /**
   * @minItems 1
   */
  reasons: [string, ...string[]];
  routeId: string;
  routeType: 'project-initialization' | 'unsupported';
  schemaVersion: '1.0.0';
  supported: boolean;
  turnId: string;
  unsupportedReason?: string;
}
