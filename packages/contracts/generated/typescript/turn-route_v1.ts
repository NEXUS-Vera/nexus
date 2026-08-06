/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export interface TurnRoute {
  autonomyMode: 'collaborate' | 'delegate';
  chairmanRequiredEventually: boolean;
  complexity: 'low' | 'medium' | 'high' | 'unknown';
  domain: 'embedded-products';
  projectOperation:
    | 'create-project'
    | 'clarify-requirement'
    | 'add-requirement'
    | 'change-requirement'
    | 'remove-proposed-requirement'
    | 'answer-open-question'
    | 'change-project-scope'
    | 'reject-component-candidate'
    | 'approve-component-selection'
    | 'change-component-preference'
    | 'add-component-constraint'
    | 'change-interface-constraint'
    | 'request-component-alternatives'
    | 'answer-component-open-question'
    | 'none';
  /**
   * @minItems 1
   */
  reasons: [string, ...string[]];
  routeId: string;
  routeType: 'project-initialization' | 'project-modification' | 'unsupported';
  schemaVersion: '1.0.0';
  supported: boolean;
  turnId: string;
  unsupportedReason?: string;
}
