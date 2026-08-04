/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export type ConsequenceLevel = 'low' | 'medium' | 'high' | 'safety-critical';

export interface ApprovalRequirement {
  /**
   * @minItems 1
   */
  allowedApproverKinds: ['user' | 'agent' | 'system', ...('user' | 'agent' | 'system')[]];
  autoAcceptAllowed?: boolean;
  consequenceLevel: ConsequenceLevel;
  reason: string;
  required: boolean;
  schemaVersion: '1.0.0';
}
