/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export interface ElectricalArchitectureContent {
  architectureId: string;
  assumptions: {
    assumptionId: string;
    confidence: 'high' | 'medium' | 'low';
    confirmationStatus: 'confirmed' | 'proposed' | 'needs-confirmation' | 'rejected';
    sourceType: 'user-explicit' | 'user-implied' | 'system-inferred' | 'project-policy';
    statement: string;
  }[];
  connections: {
    connectionId: string;
    connectionType: 'signal' | 'bus' | 'power' | 'ground' | 'communication' | 'control' | 'other';
    description?: string;
    fromInterfaceId?: string;
    fromNodeId: string;
    functionalArchitectureEdgeIds?: string[];
    interfaceType:
      | 'analog'
      | 'gpio'
      | 'i2c'
      | 'spi'
      | 'uart'
      | 'can'
      | 'usb'
      | 'ethernet'
      | 'pwm'
      | 'power'
      | 'ground'
      | 'other'
      | 'unknown';
    provenance?: DerivedFactProvenance;
    provisionalReason?: string;
    status: 'resolved' | 'provisional' | 'unresolved' | 'needs-resolution';
    toInterfaceId?: string;
    toNodeId: string;
  }[];
  coverageSummary: {
    approvedImplementationCount: number;
    coveredFunctionalNodes: number;
    preferredImplementationCount: number;
    totalFunctionalNodes: number;
    uncoveredFunctionalNodeIds: string[];
    unresolvedConnectionCount: number;
    unresolvedImplementationCount: number;
  };
  evidenceStatus: 'unverified' | 'inferred' | 'partially-grounded' | 'grounded' | 'calculated' | 'tested';
  maturity: 'provisional' | 'drafted' | 'reviewed' | 'approved';
  nodes: {
    assumptions?: string[];
    componentCandidateId?: string;
    componentRoleIds: string[];
    evidenceStatus: 'unverified' | 'inferred' | 'partially-grounded' | 'grounded' | 'calculated' | 'tested';
    functionalArchitectureNodeIds: string[];
    implementationStatus: 'unresolved' | 'preferred' | 'approved' | 'provisional' | 'unsupported';
    interfaces?: {
      direction: 'in' | 'out' | 'bidirectional' | 'unknown';
      interfaceId: string;
      interfaceType:
        | 'analog'
        | 'gpio'
        | 'i2c'
        | 'spi'
        | 'uart'
        | 'can'
        | 'usb'
        | 'ethernet'
        | 'pwm'
        | 'power'
        | 'ground'
        | 'other'
        | 'unknown';
      label?: string;
      notes?: string;
      provenance?: DerivedFactProvenance1;
      status: 'resolved' | 'unresolved' | 'unknown' | 'needs-resolution';
      voltage?: Quantity;
    }[];
    name: string;
    nodeId: string;
    nodeType:
      | 'component'
      | 'power-source'
      | 'power-regulator'
      | 'connector'
      | 'protection'
      | 'supporting-electronics'
      | 'external-interface'
      | 'junction';
    notes?: string;
    requirementIds?: string[];
    selectionState?: 'preferred' | 'approved' | 'unresolved' | 'none';
  }[];
  powerDomains: {
    memberNodeIds?: string[];
    name: string;
    nominalVoltage?: Quantity1;
    notes?: string;
    powerDomainId: string;
    provenance?: DerivedFactProvenance2;
    status: 'known' | 'unknown' | 'needs-resolution';
  }[];
  selectionBasisSummary: string;
  summary: string;
  unresolvedDecisions: OpenQuestionReference[];
  warnings: {
    code: string;
    message: string;
    relatedNodeIds?: string[];
    severity: 'info' | 'warning' | 'blocking';
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
export interface Quantity {
  schemaVersion: '1.0.0';
  unit: string;
  value: number;
}
export interface Quantity1 {
  schemaVersion: '1.0.0';
  unit: string;
  value: number;
}
export interface DerivedFactProvenance2 {
  derivedFromIds?: string[];
  notes?: string;
  schemaVersion: '1.0.0';
  sourceReference?: EvidenceReference2 | string;
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
export interface EvidenceReference2 {
  attribution?: ActorReference2;
  evidenceId: string;
  evidenceStrength: 'direct' | 'supporting' | 'inferred' | 'contradicting';
  schemaVersion: '1.0.0';
  sourceId: string;
  sourceLocator?: string;
  sourceType:
    'user-turn' | 'project-policy' | 'document' | 'external-source' | 'calculation' | 'test-result' | 'agent-inference';
  supportedClaim?: string;
}
export interface ActorReference2 {
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
