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
export type ComponentCategory1 =
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
export type ConsequenceLevel = 'low' | 'medium' | 'high' | 'safety-critical';

/**
 * Structured Component Plan content. Envelope owns artifactId, version, lifecycle, evidence, approval, and timestamps; those fields are omitted here.
 */
export interface ComponentPlanContent {
  assumptions: string[];
  candidates: ComponentCandidate[];
  compatibilityChecks: CompatibilityCheck[];
  componentPlanId?: string;
  componentRoles: ComponentRole[];
  coverageSummary: ComponentPlanCoverageSummary;
  evidenceReferences: EvidenceReference2[];
  maturity:
    | 'roles-defined'
    | 'candidates-proposed'
    | 'candidates-grounded'
    | 'compatibility-checked'
    | 'selection-proposed'
    | 'selection-approved'
    | 'validated';
  openQuestions: {
    questionId: string;
    summary?: string;
  }[];
  selectionConstraints: SelectionConstraint[];
  selectionDecisions: SelectionDecision[];
  summary: string;
  validationSummary: {
    blockingIssueCount: number;
    issueCount: number;
    status: 'ok' | 'warnings' | 'blocking';
    warningCount: number;
  };
}
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
  evidenceReferences: EvidenceReference1[];
  inputReferences: string[];
  performedAt?: string;
  performedBy?: ActorReference2;
  reason: string;
  severity: 'info' | 'warning' | 'blocking';
  status: 'not-checked' | 'unknown' | 'pass' | 'conditional' | 'warning' | 'fail' | 'not-applicable';
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
export interface ActorReference2 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface ComponentRole {
  architectureNodeIds: string[];
  category: ComponentCategory1;
  componentRoleId: string;
  description: string;
  displayId: string;
  name: string;
  openQuestionIds?: string[];
  priority: 'low' | 'medium' | 'high' | 'blocking';
  rationale: string;
  requiredCapabilities: string[];
  requirementIds: string[];
  source: 'user-explicit' | 'inferred' | 'agent-proposed' | 'fixture';
  status:
    | 'identified'
    | 'needs-clarification'
    | 'ready-for-candidates'
    | 'candidate-review'
    | 'selection-proposed'
    | 'selected'
    | 'blocked'
    | 'superseded';
}
export interface ComponentPlanCoverageSummary {
  coveredArchitectureNodes: number;
  coveredRequirementIds: string[];
  rolesAwaitingApproval: number;
  rolesWithBlockedSelection: number;
  rolesWithoutArchitectureMapping: number;
  rolesWithoutCandidates: number;
  rolesWithoutRequirementMapping: number;
  totalArchitectureNodes: number;
  totalRelevantRequirements: number;
  uncoveredArchitectureNodeIds: string[];
  uncoveredRequirementIds: string[];
}
export interface EvidenceReference2 {
  attribution?: ActorReference3;
  evidenceId: string;
  evidenceStrength: 'direct' | 'supporting' | 'inferred' | 'contradicting';
  schemaVersion: '1.0.0';
  sourceId: string;
  sourceLocator?: string;
  sourceType:
    'user-turn' | 'project-policy' | 'document' | 'external-source' | 'calculation' | 'test-result' | 'agent-inference';
  supportedClaim?: string;
}
export interface ActorReference3 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface SelectionConstraint {
  componentRoleId: string;
  confirmationStatus: 'confirmed' | 'inferred' | 'proposed' | 'unknown';
  constraintId: string;
  constraintType:
    | 'measurement-range'
    | 'accuracy'
    | 'resolution'
    | 'sample-rate'
    | 'bandwidth'
    | 'latency'
    | 'supply-voltage'
    | 'logic-voltage'
    | 'active-current'
    | 'sleep-current'
    | 'peak-current'
    | 'interface'
    | 'bus-bandwidth'
    | 'operating-temperature'
    | 'humidity-rating'
    | 'size'
    | 'weight'
    | 'cost'
    | 'availability'
    | 'driver-support'
    | 'platform-support'
    | 'environment'
    | 'mechanical-mounting';
  importance: 'required' | 'preferred' | 'nice-to-have';
  operator: 'eq' | 'neq' | 'gte' | 'lte' | 'gt' | 'lt' | 'in' | 'contains' | 'unknown';
  rationale: string;
  sourceArchitectureNodeIds: string[];
  sourceRequirementIds: string[];
  targetValue:
    | number
    | string
    | boolean
    | {
        kind: 'unknown';
      };
  unit: string | null;
}
export interface SelectionDecision {
  approvalRequirement: ApprovalRequirement;
  approvedAt?: string;
  approvedBy?: ActorReference4;
  componentRoleId: string;
  createdAt: string;
  proposedBy: ActorReference5;
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
export interface ActorReference4 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface ActorReference5 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
