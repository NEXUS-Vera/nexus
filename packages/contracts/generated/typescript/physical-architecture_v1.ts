/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export interface PhysicalArchitectureContent {
  architectureId: string;
  assumptions: {
    assumptionId: string;
    confidence: 'high' | 'medium' | 'low';
    confirmationStatus: 'confirmed' | 'proposed' | 'needs-confirmation' | 'rejected';
    sourceType: 'user-explicit' | 'user-implied' | 'system-inferred' | 'project-policy';
    statement: string;
  }[];
  coverageSummary: {
    coveredElectricalNodes: number;
    provisionalRelationshipCount: number;
    totalElectricalNodes: number;
    uncoveredElectricalNodeIds: string[];
    unresolvedPlacementCount: number;
  };
  evidenceStatus: 'unverified' | 'inferred' | 'partially-grounded' | 'grounded' | 'calculated' | 'tested';
  maturity: 'provisional' | 'drafted' | 'reviewed' | 'approved';
  nodes: {
    constraints?: string[];
    electricalNodeIds: string[];
    name: string;
    nodeId: string;
    nodeType:
      | 'assembly'
      | 'board'
      | 'module'
      | 'sensor'
      | 'actuator'
      | 'power-source'
      | 'connector'
      | 'enclosure'
      | 'mount'
      | 'external-system'
      | 'zone';
    notes?: string;
    placementStatus: 'placed' | 'unresolved' | 'provisional' | 'unknown';
    provenance?: DerivedFactProvenance;
    qualitativePlacement?: string;
    zoneId?: string;
  }[];
  relationships: {
    fromNodeId: string;
    provenance?: DerivedFactProvenance1;
    relationshipId: string;
    relationshipType:
      'mounted-on' | 'inside' | 'attached-to' | 'adjacent-to' | 'connected-to' | 'exposed-to' | 'isolated-from';
    status: 'resolved' | 'provisional' | 'unresolved';
    toNodeId: string;
  }[];
  summary: string;
  unresolvedDecisions: OpenQuestionReference[];
  warnings: {
    code: string;
    message: string;
    relatedNodeIds?: string[];
    severity: 'info' | 'warning' | 'blocking';
  }[];
  zones: {
    memberNodeIds?: string[];
    name: string;
    notes?: string;
    zoneId: string;
    zoneKind: 'enclosure' | 'chassis' | 'external-sensing' | 'power' | 'user-interface' | 'other' | 'unknown';
  }[];
}
export interface DerivedFactProvenance {
  derivedFromIds?: string[];
  notes?: string;
  schemaVersion: '1.0.0';
  sourceReference?: EvidenceReference | string;
  sourceType:
    | 'fixture'
    | 'component-plan'
    | 'user'
    | 'llm-derived'
    | 'manufacturer-datasheet'
    | 'external-provider'
    | 'runtime-output'
    | 'derived'
    | 'unknown';
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
export interface DerivedFactProvenance1 {
  derivedFromIds?: string[];
  notes?: string;
  schemaVersion: '1.0.0';
  sourceReference?: EvidenceReference1 | string;
  sourceType:
    | 'fixture'
    | 'component-plan'
    | 'user'
    | 'llm-derived'
    | 'manufacturer-datasheet'
    | 'external-provider'
    | 'runtime-output'
    | 'derived'
    | 'unknown';
}
export interface EvidenceReference1 {
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
export interface OpenQuestionReference {
  displayId?: string;
  questionId: string;
  schemaVersion: '1.0.0';
}
