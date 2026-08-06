/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export type ComponentCategory =
  | 'sensor'
  | 'compute'
  | 'power'
  | 'communication'
  | 'storage'
  | 'interface'
  | 'actuation'
  | 'protection'
  | 'mechanical'
  | 'supporting-electronics';

export interface ComponentCandidate {
  advantages: string[];
  candidateCategory: ComponentCategory;
  candidateId: string;
  candidateState:
    'discovered' | 'proposed' | 'shortlisted' | 'preferred' | 'selected' | 'rejected' | 'blocked' | 'superseded';
  compatibilityCheckIds: string[];
  componentRoleId: string;
  confidence: 'low' | 'medium' | 'high';
  displayName: string;
  evidenceReferences: EvidenceReference[];
  evidenceStatus: 'unverified' | 'inferred' | 'partially-grounded' | 'grounded' | 'calculated' | 'tested';
  limitations: string[];
  manufacturer: string;
  notes?: string;
  partNumber: string;
  source: 'fixture' | 'agent-inference' | 'user-provided' | 'future-datasheet' | 'future-tool-output';
  specifications: {
    operator?: 'eq' | 'neq' | 'gte' | 'lte' | 'gt' | 'lt' | 'in' | 'contains' | 'unknown';
    specKey: string;
    unit?: string;
    value:
      | number
      | string
      | {
          kind: 'unknown';
        };
  }[];
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
