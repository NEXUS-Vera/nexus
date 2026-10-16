/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export type ConsequenceLevel = 'low' | 'medium' | 'high' | 'safety-critical';

export interface SelectionDecision {
  approvalRequirement: ApprovalRequirement;
  approvedAt?: string;
  approvedBy?: ActorReference;
  componentRoleId: string;
  createdAt: string;
  proposedBy: ActorReference1;
  rationale: string;
  selectedCandidateId: string;
  selectionDecisionId: string;
  selectionState: 'not-started' | 'proposed' | 'awaiting-user' | 'approved' | 'rejected' | 'superseded' | 'blocked';
  source: 'user-explicit' | 'agent-proposed' | 'fixture' | 'inferred';
  supersedesSelectionDecisionId?: string;
  tradeoffs: string[];
}
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
export interface ActorReference {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface ActorReference1 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
