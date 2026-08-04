/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export type ConsequenceLevel = 'low' | 'medium' | 'high' | 'safety-critical';
export type ArtifactType =
  'project-brief' | 'requirement-set' | 'functional-architecture' | 'next-action' | 'component-plan';
export type ConsequenceLevel1 = 'low' | 'medium' | 'high' | 'safety-critical';

export interface ArtifactProposal {
  approvalRequirement: ApprovalRequirement;
  artifactId: string;
  artifactType: ArtifactType;
  baseArtifactVersion: number;
  baseProjectStateVersion: number;
  consequenceLevel: ConsequenceLevel1;
  decidedAt?: string;
  decidedBy?: ActorReference;
  decisionReason?: string;
  projectId: string;
  proposalId: string;
  proposedAt: string;
  proposedBy: ActorReference1;
  resultingArtifactId?: string;
  resultingArtifactVersion?: number;
  schemaVersion: '1.0.0';
  snapshotId: string;
  status: 'proposed' | 'awaiting-approval' | 'accepted' | 'rejected' | 'superseded' | 'conflicted';
  workspaceId: string;
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
