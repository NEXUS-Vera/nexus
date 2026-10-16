/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export interface CompatibilityCheck {
  candidateId: string;
  checkType:
    | 'requirement-fit'
    | 'architecture-fit'
    | 'electrical-supply'
    | 'logic-level'
    | 'interface-type'
    | 'interface-bandwidth'
    | 'bus-address'
    | 'pin-availability'
    | 'performance'
    | 'sample-rate'
    | 'bandwidth'
    | 'power-budget'
    | 'environmental'
    | 'mechanical'
    | 'firmware-support'
    | 'driver-availability'
    | 'cost'
    | 'availability'
    | 'documentation-quality';
  compatibilityCheckId: string;
  componentRoleId: string;
  evidenceReferences: EvidenceReference[];
  inputReferences: string[];
  performedAt?: string;
  performedBy?: ActorReference1;
  reason: string;
  severity: 'info' | 'warning' | 'blocking';
  status: 'not-checked' | 'unknown' | 'pass' | 'conditional' | 'warning' | 'fail' | 'not-applicable';
}
export interface EvidenceReference {
  attribution?: ActorReference;
  evidenceId: string;
  evidenceStrength: 'direct' | 'supporting' | 'inferred' | 'contradicting';
  schemaVersion: '1.0.0';
  sourceId: string;
  sourceLocator?: string;
  sourceType:
    'user-turn' | 'project-policy' | 'document' | 'external-source' | 'calculation' | 'test-result' | 'agent-inference';
  supportedClaim?: string;
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
