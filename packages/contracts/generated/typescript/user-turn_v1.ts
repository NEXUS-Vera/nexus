/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export interface UserTurn {
  actor: ActorReference;
  attachmentReferences?: EvidenceReference[];
  parentTurnId?: string;
  projectId: string;
  rawUserMessage: string;
  schemaVersion: '1.0.0';
  timestamp: string;
  turnId: string;
}
export interface ActorReference {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface EvidenceReference {
  attribution?: ActorReference1;
  evidenceId: string;
  evidenceStrength: 'direct' | 'supporting' | 'inferred' | 'contradicting';
  schemaVersion: '1.0.0';
  sourceId: string;
  sourceLocator?: string;
  sourceType:
    'user-turn' | 'project-policy' | 'document' | 'external-source' | 'calculation' | 'test-result' | 'agent-inference';
  supportedClaim?: string;
}
export interface ActorReference1 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
