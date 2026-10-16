/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export type ArtifactType =
  | 'project-brief'
  | 'requirement-set'
  | 'functional-architecture'
  | 'next-action'
  | 'component-plan'
  | 'code-scratch'
  | 'firmware'
  | 'electrical-architecture'
  | 'physical-architecture'
  | 'analysis'
  | 'test-plan'
  | 'risk-register';
export type Artifact =
  | ArtifactEnvelope
  | ArtifactEnvelope1
  | ArtifactEnvelope2
  | ArtifactEnvelope3
  | ArtifactEnvelope4
  | ArtifactEnvelope5
  | ArtifactEnvelope6
  | ArtifactEnvelope7
  | ArtifactEnvelope8;
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
export type ArtifactType1 =
  | 'project-brief'
  | 'requirement-set'
  | 'functional-architecture'
  | 'next-action'
  | 'component-plan'
  | 'code-scratch'
  | 'firmware'
  | 'electrical-architecture'
  | 'physical-architecture'
  | 'analysis'
  | 'test-plan'
  | 'risk-register';
export type ArtifactType2 =
  | 'project-brief'
  | 'requirement-set'
  | 'functional-architecture'
  | 'next-action'
  | 'component-plan'
  | 'code-scratch'
  | 'firmware'
  | 'electrical-architecture'
  | 'physical-architecture'
  | 'analysis'
  | 'test-plan'
  | 'risk-register';
export type ArtifactType3 =
  | 'project-brief'
  | 'requirement-set'
  | 'functional-architecture'
  | 'next-action'
  | 'component-plan'
  | 'code-scratch'
  | 'firmware'
  | 'electrical-architecture'
  | 'physical-architecture'
  | 'analysis'
  | 'test-plan'
  | 'risk-register';
export type ArtifactType4 =
  | 'project-brief'
  | 'requirement-set'
  | 'functional-architecture'
  | 'next-action'
  | 'component-plan'
  | 'code-scratch'
  | 'firmware'
  | 'electrical-architecture'
  | 'physical-architecture'
  | 'analysis'
  | 'test-plan'
  | 'risk-register';
export type ArtifactType5 =
  | 'project-brief'
  | 'requirement-set'
  | 'functional-architecture'
  | 'next-action'
  | 'component-plan'
  | 'code-scratch'
  | 'firmware'
  | 'electrical-architecture'
  | 'physical-architecture'
  | 'analysis'
  | 'test-plan'
  | 'risk-register';
export type ArtifactType6 =
  | 'project-brief'
  | 'requirement-set'
  | 'functional-architecture'
  | 'next-action'
  | 'component-plan'
  | 'code-scratch'
  | 'firmware'
  | 'electrical-architecture'
  | 'physical-architecture'
  | 'analysis'
  | 'test-plan'
  | 'risk-register';
export type ArtifactType7 =
  | 'project-brief'
  | 'requirement-set'
  | 'functional-architecture'
  | 'next-action'
  | 'component-plan'
  | 'code-scratch'
  | 'firmware'
  | 'electrical-architecture'
  | 'physical-architecture'
  | 'analysis'
  | 'test-plan'
  | 'risk-register';
export type ArtifactType8 =
  | 'project-brief'
  | 'requirement-set'
  | 'functional-architecture'
  | 'next-action'
  | 'component-plan'
  | 'code-scratch'
  | 'firmware'
  | 'electrical-architecture'
  | 'physical-architecture'
  | 'analysis'
  | 'test-plan'
  | 'risk-register';
export type ArtifactType9 =
  | 'project-brief'
  | 'requirement-set'
  | 'functional-architecture'
  | 'next-action'
  | 'component-plan'
  | 'code-scratch'
  | 'firmware'
  | 'electrical-architecture'
  | 'physical-architecture'
  | 'analysis'
  | 'test-plan'
  | 'risk-register';
export type ArtifactType10 =
  | 'project-brief'
  | 'requirement-set'
  | 'functional-architecture'
  | 'next-action'
  | 'component-plan'
  | 'code-scratch'
  | 'firmware'
  | 'electrical-architecture'
  | 'physical-architecture'
  | 'analysis'
  | 'test-plan'
  | 'risk-register';
export type ArtifactType11 =
  | 'project-brief'
  | 'requirement-set'
  | 'functional-architecture'
  | 'next-action'
  | 'component-plan'
  | 'code-scratch'
  | 'firmware'
  | 'electrical-architecture'
  | 'physical-architecture'
  | 'analysis'
  | 'test-plan'
  | 'risk-register';
export type ArtifactType12 =
  | 'project-brief'
  | 'requirement-set'
  | 'functional-architecture'
  | 'next-action'
  | 'component-plan'
  | 'code-scratch'
  | 'firmware'
  | 'electrical-architecture'
  | 'physical-architecture'
  | 'analysis'
  | 'test-plan'
  | 'risk-register';
export type ArtifactType13 =
  | 'project-brief'
  | 'requirement-set'
  | 'functional-architecture'
  | 'next-action'
  | 'component-plan'
  | 'code-scratch'
  | 'firmware'
  | 'electrical-architecture'
  | 'physical-architecture'
  | 'analysis'
  | 'test-plan'
  | 'risk-register';

/**
 * Canonical response for a project-modification turn: the resulting current state together with the interpreted intent, the propagation analysis, and which artifact types were actually changed or regenerated.
 */
export interface ProjectTurnResult {
  changeIntent: ProjectChangeIntent;
  changedArtifactTypes: ArtifactType[];
  currentState: ProjectCurrentState;
  impactAnalysis: ProjectImpactAnalysis;
  regeneratedArtifactTypes: ArtifactType13[];
  schemaVersion: '1.0.0';
}
/**
 * Interpreted intent of a project-modification turn. Intent is recorded explicitly so ambiguous requests can require user confirmation before any artifact is regenerated.
 */
export interface ProjectChangeIntent {
  ambiguities: string[];
  confidence: 'low' | 'medium' | 'high';
  operation:
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
    | 'answer-component-open-question';
  requestedChange: string;
  requiresUserConfirmation: boolean;
  schemaVersion: '1.0.0';
  sourceTurnId: string;
  targetArtifactType:
    'project-brief' | 'requirement-set' | 'functional-architecture' | 'component-plan' | 'next-action' | null;
  targetQuestionId?: string;
  targetRequirementId?: string;
}
/**
 * Canonical current-state package for a persisted embedded project. This is the contract returned when reading a project, and it carries the current artifact heads plus the turn that produced them.
 */
export interface ProjectCurrentState {
  /**
   * @minItems 4
   * @maxItems 12
   */
  artifacts:
    | [Artifact, Artifact, Artifact, Artifact]
    | [Artifact, Artifact, Artifact, Artifact, Artifact]
    | [Artifact, Artifact, Artifact, Artifact, Artifact, Artifact]
    | [Artifact, Artifact, Artifact, Artifact, Artifact, Artifact, Artifact]
    | [Artifact, Artifact, Artifact, Artifact, Artifact, Artifact, Artifact, Artifact]
    | [Artifact, Artifact, Artifact, Artifact, Artifact, Artifact, Artifact, Artifact, Artifact]
    | [Artifact, Artifact, Artifact, Artifact, Artifact, Artifact, Artifact, Artifact, Artifact, Artifact]
    | [Artifact, Artifact, Artifact, Artifact, Artifact, Artifact, Artifact, Artifact, Artifact, Artifact, Artifact]
    | [
        Artifact,
        Artifact,
        Artifact,
        Artifact,
        Artifact,
        Artifact,
        Artifact,
        Artifact,
        Artifact,
        Artifact,
        Artifact,
        Artifact
      ];
  dependencies?: ArtifactDependency[];
  openQuestions: OpenQuestion[];
  previousTurnIds?: string[];
  project: Project;
  schemaVersion: '1.0.0';
  turnRoute: TurnRoute;
  userTurn: UserTurn;
  validationIssues: ValidationIssue[];
  veraResponse: VeraResponse;
  workflowRun: WorkflowRun;
}
export interface ArtifactEnvelope {
  approvalStatus: 'not-required' | 'proposed' | 'awaiting-user' | 'user-approved' | 'agent-decided' | 'rejected';
  artifactId: string;
  artifactType: 'project-brief';
  artifactVersion: number;
  content: ProjectBriefContent;
  contentSchemaVersion: '1.0.0';
  createdAt: string;
  createdBy: ActorReference;
  evidenceStatus: 'unverified' | 'inferred' | 'partially-grounded' | 'grounded' | 'calculated' | 'tested';
  lifecycleStatus: 'drafted' | 'ready' | 'affected' | 'stale' | 'blocked' | 'superseded' | 'archived';
  projectId: string;
  schemaVersion: '1.0.0';
  sourceTurnId: string;
  supersedesArtifactId?: string;
  supersedesArtifactVersion?: number;
  updatedAt: string;
  workflowRunId: string;
}
export interface ProjectBriefContent {
  assumptions: {
    assumptionId: string;
    confidence: 'high' | 'medium' | 'low';
    confirmationStatus: 'confirmed' | 'proposed' | 'needs-confirmation' | 'rejected';
    sourceType: 'user-explicit' | 'user-implied' | 'system-inferred' | 'project-policy';
    statement: string;
  }[];
  goal: string;
  intendedContext: string;
  outOfScope: string[];
  problemStatement: string;
  projectStage: 'concept' | 'prototype-planning';
  /**
   * @minItems 1
   */
  scope: [string, ...string[]];
  /**
   * @minItems 1
   */
  successCriteria: [string, ...string[]];
  unknowns: OpenQuestionReference[];
}
export interface OpenQuestionReference {
  displayId?: string;
  questionId: string;
  schemaVersion: '1.0.0';
}
export interface ActorReference {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface ArtifactEnvelope1 {
  approvalStatus: 'not-required' | 'proposed' | 'awaiting-user' | 'user-approved' | 'agent-decided' | 'rejected';
  artifactId: string;
  artifactType: 'requirement-set';
  artifactVersion: number;
  content: RequirementSetContent;
  contentSchemaVersion: '1.0.0';
  createdAt: string;
  createdBy: ActorReference2;
  evidenceStatus: 'unverified' | 'inferred' | 'partially-grounded' | 'grounded' | 'calculated' | 'tested';
  lifecycleStatus: 'drafted' | 'ready' | 'affected' | 'stale' | 'blocked' | 'superseded' | 'archived';
  projectId: string;
  schemaVersion: '1.0.0';
  sourceTurnId: string;
  supersedesArtifactId?: string;
  supersedesArtifactVersion?: number;
  updatedAt: string;
  workflowRunId: string;
}
export interface RequirementSetContent {
  missingDimensions?: string[];
  openQuestionIds?: OpenQuestionReference1[];
  requirementSummary: string;
  /**
   * @minItems 1
   */
  requirements: [
    {
      acceptanceCriteria?: string[];
      category:
        | 'functional'
        | 'performance'
        | 'interface'
        | 'environmental'
        | 'resource'
        | 'physical'
        | 'usability'
        | 'safety'
        | 'verification'
        | 'project-constraint';
      confidence: 'high' | 'medium' | 'low';
      confirmationStatus: 'confirmed' | 'proposed' | 'needs-confirmation' | 'rejected';
      dependencyReferences?: string[];
      displayId: string;
      priority: 'must' | 'should' | 'could' | 'unclassified';
      rationale?: string;
      requirementId: string;
      sourceReference: EvidenceReference;
      sourceType: 'user-explicit' | 'user-implied' | 'system-inferred' | 'project-policy';
      statement: string;
      targetQuantity?: Quantity;
      verificationMethod: string;
    },
    ...{
      acceptanceCriteria?: string[];
      category:
        | 'functional'
        | 'performance'
        | 'interface'
        | 'environmental'
        | 'resource'
        | 'physical'
        | 'usability'
        | 'safety'
        | 'verification'
        | 'project-constraint';
      confidence: 'high' | 'medium' | 'low';
      confirmationStatus: 'confirmed' | 'proposed' | 'needs-confirmation' | 'rejected';
      dependencyReferences?: string[];
      displayId: string;
      priority: 'must' | 'should' | 'could' | 'unclassified';
      rationale?: string;
      requirementId: string;
      sourceReference: EvidenceReference;
      sourceType: 'user-explicit' | 'user-implied' | 'system-inferred' | 'project-policy';
      statement: string;
      targetQuantity?: Quantity;
      verificationMethod: string;
    }[]
  ];
}
export interface OpenQuestionReference1 {
  displayId?: string;
  questionId: string;
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
export interface Quantity {
  schemaVersion: '1.0.0';
  unit: string;
  value: number;
}
export interface ActorReference2 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface ArtifactEnvelope2 {
  approvalStatus: 'not-required' | 'proposed' | 'awaiting-user' | 'user-approved' | 'agent-decided' | 'rejected';
  artifactId: string;
  artifactType: 'functional-architecture';
  artifactVersion: number;
  content: FunctionalArchitectureContent;
  contentSchemaVersion: '1.0.0';
  createdAt: string;
  createdBy: ActorReference3;
  evidenceStatus: 'unverified' | 'inferred' | 'partially-grounded' | 'grounded' | 'calculated' | 'tested';
  lifecycleStatus: 'drafted' | 'ready' | 'affected' | 'stale' | 'blocked' | 'superseded' | 'archived';
  projectId: string;
  schemaVersion: '1.0.0';
  sourceTurnId: string;
  supersedesArtifactId?: string;
  supersedesArtifactVersion?: number;
  updatedAt: string;
  workflowRunId: string;
}
export interface FunctionalArchitectureContent {
  architectureId: string;
  architectureMaturity: 'functional';
  assumptions: {
    assumptionId: string;
    confidence: 'high' | 'medium' | 'low';
    confirmationStatus: 'confirmed' | 'proposed' | 'needs-confirmation' | 'rejected';
    sourceType: 'user-explicit' | 'user-implied' | 'system-inferred' | 'project-policy';
    statement: string;
  }[];
  /**
   * @minItems 1
   */
  edges: [
    {
      description: string;
      edgeId: string;
      flowType: 'data' | 'control' | 'power' | 'user-input' | 'physical-output';
      fromNodeId: string;
      toNodeId: string;
    },
    ...{
      description: string;
      edgeId: string;
      flowType: 'data' | 'control' | 'power' | 'user-input' | 'physical-output';
      fromNodeId: string;
      toNodeId: string;
    }[]
  ];
  /**
   * @minItems 1
   */
  nodes: [
    {
      functionalType:
        | 'input'
        | 'sensing'
        | 'processing'
        | 'control'
        | 'storage'
        | 'communication'
        | 'power'
        | 'output'
        | 'actuation'
        | 'analysis'
        | 'user-interface'
        | 'external-system';
      inputs?: {
        dataType: string;
        description: string;
      }[];
      name: string;
      nodeId: string;
      outputs?: {
        dataType: string;
        description: string;
      }[];
      /**
       * @minItems 1
       */
      responsibilities: [string, ...string[]];
      /**
       * @minItems 1
       */
      satisfiesRequirementIds: [string, ...string[]];
    },
    ...{
      functionalType:
        | 'input'
        | 'sensing'
        | 'processing'
        | 'control'
        | 'storage'
        | 'communication'
        | 'power'
        | 'output'
        | 'actuation'
        | 'analysis'
        | 'user-interface'
        | 'external-system';
      inputs?: {
        dataType: string;
        description: string;
      }[];
      name: string;
      nodeId: string;
      outputs?: {
        dataType: string;
        description: string;
      }[];
      /**
       * @minItems 1
       */
      responsibilities: [string, ...string[]];
      /**
       * @minItems 1
       */
      satisfiesRequirementIds: [string, ...string[]];
    }[]
  ];
  requirementCoverage: {
    /**
     * @minItems 1
     */
    coveredRequirementIds: [string, ...string[]];
  };
  systemBoundary: string;
  unresolvedDecisions: OpenQuestionReference2[];
}
export interface OpenQuestionReference2 {
  displayId?: string;
  questionId: string;
  schemaVersion: '1.0.0';
}
export interface ActorReference3 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface ArtifactEnvelope3 {
  approvalStatus: 'not-required' | 'proposed' | 'awaiting-user' | 'user-approved' | 'agent-decided' | 'rejected';
  artifactId: string;
  artifactType: 'next-action';
  artifactVersion: number;
  content: NextActionContent;
  contentSchemaVersion: '1.0.0';
  createdAt: string;
  createdBy: ActorReference4;
  evidenceStatus: 'unverified' | 'inferred' | 'partially-grounded' | 'grounded' | 'calculated' | 'tested';
  lifecycleStatus: 'drafted' | 'ready' | 'affected' | 'stale' | 'blocked' | 'superseded' | 'archived';
  projectId: string;
  schemaVersion: '1.0.0';
  sourceTurnId: string;
  supersedesArtifactId?: string;
  supersedesArtifactVersion?: number;
  updatedAt: string;
  workflowRunId: string;
}
export interface NextActionContent {
  actionId: string;
  blocks: {
    issueId: string;
  }[];
  completionCondition: {
    completionCriteria: string;
    conditionType: 'validation-issues-cleared' | 'unknowns-resolved' | 'requirements-confirmed';
  };
  description: string;
  owner: 'user' | 'vera' | 'embedded-systems-agent' | 'shared';
  prerequisites: OpenQuestionReference3[];
  priority: 'critical' | 'high' | 'medium' | 'low';
  rationale: string;
  sourceIssueIds: string[];
  sourceQuestionIds: string[];
  title: string;
}
export interface OpenQuestionReference3 {
  displayId?: string;
  questionId: string;
  schemaVersion: '1.0.0';
}
export interface ActorReference4 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface ArtifactEnvelope4 {
  approvalStatus: 'not-required' | 'proposed' | 'awaiting-user' | 'user-approved' | 'agent-decided' | 'rejected';
  artifactId: string;
  artifactType: 'component-plan';
  artifactVersion: number;
  content: ComponentPlanContent;
  contentSchemaVersion: '1.0.0';
  createdAt: string;
  createdBy: ActorReference11;
  evidenceStatus: 'unverified' | 'inferred' | 'partially-grounded' | 'grounded' | 'calculated' | 'tested';
  lifecycleStatus: 'drafted' | 'ready' | 'affected' | 'stale' | 'blocked' | 'superseded' | 'archived';
  projectId: string;
  schemaVersion: '1.0.0';
  sourceTurnId: string;
  supersedesArtifactId?: string;
  supersedesArtifactVersion?: number;
  updatedAt: string;
  workflowRunId: string;
}
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
  evidenceReferences: EvidenceReference3[];
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
  evidenceReferences: EvidenceReference1[];
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
export interface EvidenceReference1 {
  attribution?: ActorReference5;
  evidenceId: string;
  evidenceStrength: 'direct' | 'supporting' | 'inferred' | 'contradicting';
  schemaVersion: '1.0.0';
  sourceId: string;
  sourceLocator?: string;
  sourceType:
    'user-turn' | 'project-policy' | 'document' | 'external-source' | 'calculation' | 'test-result' | 'agent-inference';
  supportedClaim?: string;
}
export interface ActorReference5 {
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
  evidenceReferences: EvidenceReference2[];
  inputReferences: string[];
  performedAt?: string;
  performedBy?: ActorReference7;
  reason: string;
  severity: 'info' | 'warning' | 'blocking';
  status: 'not-checked' | 'unknown' | 'pass' | 'conditional' | 'warning' | 'fail' | 'not-applicable';
}
export interface EvidenceReference2 {
  attribution?: ActorReference6;
  evidenceId: string;
  evidenceStrength: 'direct' | 'supporting' | 'inferred' | 'contradicting';
  schemaVersion: '1.0.0';
  sourceId: string;
  sourceLocator?: string;
  sourceType:
    'user-turn' | 'project-policy' | 'document' | 'external-source' | 'calculation' | 'test-result' | 'agent-inference';
  supportedClaim?: string;
}
export interface ActorReference6 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface ActorReference7 {
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
export interface EvidenceReference3 {
  attribution?: ActorReference8;
  evidenceId: string;
  evidenceStrength: 'direct' | 'supporting' | 'inferred' | 'contradicting';
  schemaVersion: '1.0.0';
  sourceId: string;
  sourceLocator?: string;
  sourceType:
    'user-turn' | 'project-policy' | 'document' | 'external-source' | 'calculation' | 'test-result' | 'agent-inference';
  supportedClaim?: string;
}
export interface ActorReference8 {
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
  approvedBy?: ActorReference9;
  componentRoleId: string;
  createdAt: string;
  proposedBy: ActorReference10;
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
export interface ActorReference9 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface ActorReference10 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface ActorReference11 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface ArtifactEnvelope5 {
  approvalStatus: 'not-required' | 'proposed' | 'awaiting-user' | 'user-approved' | 'agent-decided' | 'rejected';
  artifactId: string;
  artifactType: 'electrical-architecture';
  artifactVersion: number;
  content: ElectricalArchitectureContent;
  contentSchemaVersion: '1.0.0';
  createdAt: string;
  createdBy: ActorReference15;
  evidenceStatus: 'unverified' | 'inferred' | 'partially-grounded' | 'grounded' | 'calculated' | 'tested';
  lifecycleStatus: 'drafted' | 'ready' | 'affected' | 'stale' | 'blocked' | 'superseded' | 'archived';
  projectId: string;
  schemaVersion: '1.0.0';
  sourceTurnId: string;
  supersedesArtifactId?: string;
  supersedesArtifactVersion?: number;
  updatedAt: string;
  workflowRunId: string;
}
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
      voltage?: Quantity1;
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
    nominalVoltage?: Quantity2;
    notes?: string;
    powerDomainId: string;
    provenance?: DerivedFactProvenance2;
    status: 'known' | 'unknown' | 'needs-resolution';
  }[];
  selectionBasisSummary: string;
  summary: string;
  unresolvedDecisions: OpenQuestionReference4[];
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
  sourceReference?: EvidenceReference4 | string;
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
export interface EvidenceReference4 {
  attribution?: ActorReference12;
  evidenceId: string;
  evidenceStrength: 'direct' | 'supporting' | 'inferred' | 'contradicting';
  schemaVersion: '1.0.0';
  sourceId: string;
  sourceLocator?: string;
  sourceType:
    'user-turn' | 'project-policy' | 'document' | 'external-source' | 'calculation' | 'test-result' | 'agent-inference';
  supportedClaim?: string;
}
export interface ActorReference12 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface DerivedFactProvenance1 {
  derivedFromIds?: string[];
  notes?: string;
  schemaVersion: '1.0.0';
  sourceReference?: EvidenceReference5 | string;
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
export interface EvidenceReference5 {
  attribution?: ActorReference13;
  evidenceId: string;
  evidenceStrength: 'direct' | 'supporting' | 'inferred' | 'contradicting';
  schemaVersion: '1.0.0';
  sourceId: string;
  sourceLocator?: string;
  sourceType:
    'user-turn' | 'project-policy' | 'document' | 'external-source' | 'calculation' | 'test-result' | 'agent-inference';
  supportedClaim?: string;
}
export interface ActorReference13 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface Quantity1 {
  schemaVersion: '1.0.0';
  unit: string;
  value: number;
}
export interface Quantity2 {
  schemaVersion: '1.0.0';
  unit: string;
  value: number;
}
export interface DerivedFactProvenance2 {
  derivedFromIds?: string[];
  notes?: string;
  schemaVersion: '1.0.0';
  sourceReference?: EvidenceReference6 | string;
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
export interface EvidenceReference6 {
  attribution?: ActorReference14;
  evidenceId: string;
  evidenceStrength: 'direct' | 'supporting' | 'inferred' | 'contradicting';
  schemaVersion: '1.0.0';
  sourceId: string;
  sourceLocator?: string;
  sourceType:
    'user-turn' | 'project-policy' | 'document' | 'external-source' | 'calculation' | 'test-result' | 'agent-inference';
  supportedClaim?: string;
}
export interface ActorReference14 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface OpenQuestionReference4 {
  displayId?: string;
  questionId: string;
  schemaVersion: '1.0.0';
}
export interface ActorReference15 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface ArtifactEnvelope6 {
  approvalStatus: 'not-required' | 'proposed' | 'awaiting-user' | 'user-approved' | 'agent-decided' | 'rejected';
  artifactId: string;
  artifactType: 'physical-architecture';
  artifactVersion: number;
  content: PhysicalArchitectureContent;
  contentSchemaVersion: '1.0.0';
  createdAt: string;
  createdBy: ActorReference18;
  evidenceStatus: 'unverified' | 'inferred' | 'partially-grounded' | 'grounded' | 'calculated' | 'tested';
  lifecycleStatus: 'drafted' | 'ready' | 'affected' | 'stale' | 'blocked' | 'superseded' | 'archived';
  projectId: string;
  schemaVersion: '1.0.0';
  sourceTurnId: string;
  supersedesArtifactId?: string;
  supersedesArtifactVersion?: number;
  updatedAt: string;
  workflowRunId: string;
}
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
    provenance?: DerivedFactProvenance3;
    qualitativePlacement?: string;
    zoneId?: string;
  }[];
  relationships: {
    fromNodeId: string;
    provenance?: DerivedFactProvenance4;
    relationshipId: string;
    relationshipType:
      'mounted-on' | 'inside' | 'attached-to' | 'adjacent-to' | 'connected-to' | 'exposed-to' | 'isolated-from';
    status: 'resolved' | 'provisional' | 'unresolved';
    toNodeId: string;
  }[];
  summary: string;
  unresolvedDecisions: OpenQuestionReference5[];
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
export interface DerivedFactProvenance3 {
  derivedFromIds?: string[];
  notes?: string;
  schemaVersion: '1.0.0';
  sourceReference?: EvidenceReference7 | string;
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
export interface EvidenceReference7 {
  attribution?: ActorReference16;
  evidenceId: string;
  evidenceStrength: 'direct' | 'supporting' | 'inferred' | 'contradicting';
  schemaVersion: '1.0.0';
  sourceId: string;
  sourceLocator?: string;
  sourceType:
    'user-turn' | 'project-policy' | 'document' | 'external-source' | 'calculation' | 'test-result' | 'agent-inference';
  supportedClaim?: string;
}
export interface ActorReference16 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface DerivedFactProvenance4 {
  derivedFromIds?: string[];
  notes?: string;
  schemaVersion: '1.0.0';
  sourceReference?: EvidenceReference8 | string;
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
export interface EvidenceReference8 {
  attribution?: ActorReference17;
  evidenceId: string;
  evidenceStrength: 'direct' | 'supporting' | 'inferred' | 'contradicting';
  schemaVersion: '1.0.0';
  sourceId: string;
  sourceLocator?: string;
  sourceType:
    'user-turn' | 'project-policy' | 'document' | 'external-source' | 'calculation' | 'test-result' | 'agent-inference';
  supportedClaim?: string;
}
export interface ActorReference17 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface OpenQuestionReference5 {
  displayId?: string;
  questionId: string;
  schemaVersion: '1.0.0';
}
export interface ActorReference18 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface ArtifactEnvelope7 {
  approvalStatus: 'not-required' | 'proposed' | 'awaiting-user' | 'user-approved' | 'agent-decided' | 'rejected';
  artifactId: string;
  artifactType: 'test-plan';
  artifactVersion: number;
  content: TestPlanContent;
  contentSchemaVersion: '1.0.0';
  createdAt: string;
  createdBy: ActorReference20;
  evidenceStatus: 'unverified' | 'inferred' | 'partially-grounded' | 'grounded' | 'calculated' | 'tested';
  lifecycleStatus: 'drafted' | 'ready' | 'affected' | 'stale' | 'blocked' | 'superseded' | 'archived';
  projectId: string;
  schemaVersion: '1.0.0';
  sourceTurnId: string;
  supersedesArtifactId?: string;
  supersedesArtifactVersion?: number;
  updatedAt: string;
  workflowRunId: string;
}
export interface TestPlanContent {
  coverageSummary: {
    blockedRequirements: number;
    coveredRequirements: number;
    failedRequirements: number;
    totalRequirements: number;
    uncoveredRequirements: number;
    unverifiedRequirements: number;
    verifiedRequirements: number;
  };
  provenance?: {
    generatedBy?: 'fixture' | 'llm' | 'user' | 'derived';
    notes?: string;
  };
  schemaVersion: '1.0.0';
  summary?: string;
  /**
   * @minItems 1
   */
  testCases: [
    {
      actualResult?: string;
      assessment?: 'PASS' | 'FAIL' | 'INCONCLUSIVE';
      assessmentAuthority?: 'deterministic-code' | 'manual' | 'none';
      criterion?: {
        criterionType: 'numeric-comparison' | 'exact-match' | 'contains' | 'existence' | 'structural-mapping' | 'range';
        expectedMapping?: string;
        expectedValue?: any;
        marker?: string;
        maxValue?: number;
        metricId?: string;
        minValue?: number;
        operator?: '<' | '<=' | '>' | '>=' | '==' | '!=';
        outputName?: string;
        signal?: string;
        tolerance?: number;
        toleranceUnit?: 'absolute' | 'percent';
        unit?: string;
      };
      description?: string;
      displayId: string;
      evidenceReferences?: EvidenceReference9[];
      executionRunId?: string;
      expectedResult: string;
      finding?: string;
      inputs?: string[];
      linkedArchitectureRefs?: string[];
      linkedComponentIds?: string[];
      linkedRequirementIds: string[];
      preconditions?: string[];
      procedure?: string[];
      producedOutputIds?: string[];
      status: 'planned' | 'ready' | 'running' | 'passed' | 'failed' | 'blocked' | 'inconclusive';
      testId: string;
      title: string;
      verificationMethod: 'inspection' | 'simulation' | 'firmware-test' | 'analysis' | 'execution-output' | 'manual';
    },
    ...{
      actualResult?: string;
      assessment?: 'PASS' | 'FAIL' | 'INCONCLUSIVE';
      assessmentAuthority?: 'deterministic-code' | 'manual' | 'none';
      criterion?: {
        criterionType: 'numeric-comparison' | 'exact-match' | 'contains' | 'existence' | 'structural-mapping' | 'range';
        expectedMapping?: string;
        expectedValue?: any;
        marker?: string;
        maxValue?: number;
        metricId?: string;
        minValue?: number;
        operator?: '<' | '<=' | '>' | '>=' | '==' | '!=';
        outputName?: string;
        signal?: string;
        tolerance?: number;
        toleranceUnit?: 'absolute' | 'percent';
        unit?: string;
      };
      description?: string;
      displayId: string;
      evidenceReferences?: EvidenceReference9[];
      executionRunId?: string;
      expectedResult: string;
      finding?: string;
      inputs?: string[];
      linkedArchitectureRefs?: string[];
      linkedComponentIds?: string[];
      linkedRequirementIds: string[];
      preconditions?: string[];
      procedure?: string[];
      producedOutputIds?: string[];
      status: 'planned' | 'ready' | 'running' | 'passed' | 'failed' | 'blocked' | 'inconclusive';
      testId: string;
      title: string;
      verificationMethod: 'inspection' | 'simulation' | 'firmware-test' | 'analysis' | 'execution-output' | 'manual';
    }[]
  ];
  testPlanId: string;
  title?: string;
}
export interface EvidenceReference9 {
  attribution?: ActorReference19;
  evidenceId: string;
  evidenceStrength: 'direct' | 'supporting' | 'inferred' | 'contradicting';
  schemaVersion: '1.0.0';
  sourceId: string;
  sourceLocator?: string;
  sourceType:
    'user-turn' | 'project-policy' | 'document' | 'external-source' | 'calculation' | 'test-result' | 'agent-inference';
  supportedClaim?: string;
}
export interface ActorReference19 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface ActorReference20 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface ArtifactEnvelope8 {
  approvalStatus: 'not-required' | 'proposed' | 'awaiting-user' | 'user-approved' | 'agent-decided' | 'rejected';
  artifactId: string;
  artifactType: 'risk-register';
  artifactVersion: number;
  content: RiskRegisterContent;
  contentSchemaVersion: '1.0.0';
  createdAt: string;
  createdBy: ActorReference22;
  evidenceStatus: 'unverified' | 'inferred' | 'partially-grounded' | 'grounded' | 'calculated' | 'tested';
  lifecycleStatus: 'drafted' | 'ready' | 'affected' | 'stale' | 'blocked' | 'superseded' | 'archived';
  projectId: string;
  schemaVersion: '1.0.0';
  sourceTurnId: string;
  supersedesArtifactId?: string;
  supersedesArtifactVersion?: number;
  updatedAt: string;
  workflowRunId: string;
}
export interface RiskRegisterContent {
  provenance?: {
    generatedBy?: 'fixture' | 'llm' | 'user' | 'derived';
    notes?: string;
  };
  riskRegisterId: string;
  /**
   * @minItems 1
   */
  risks: [
    {
      category:
        | 'electrical'
        | 'firmware'
        | 'communication'
        | 'power'
        | 'thermal'
        | 'mechanical'
        | 'integration'
        | 'performance'
        | 'data-quality'
        | 'safety';
      description: string;
      displayId: string;
      evidenceReferences?: EvidenceReference10[];
      likelihood: 'rare' | 'unlikely' | 'possible' | 'likely';
      linkedArchitectureRefs?: string[];
      linkedComponentIds?: string[];
      linkedRequirementIds?: string[];
      linkedTestIds?: string[];
      mitigation: string;
      priorityScore: number;
      residualRisk?: string;
      riskId: string;
      severity: 'low' | 'medium' | 'high' | 'critical';
      status: 'open' | 'mitigating' | 'mitigated' | 'accepted' | 'monitoring';
      title: string;
      verificationTestIds?: string[];
    },
    ...{
      category:
        | 'electrical'
        | 'firmware'
        | 'communication'
        | 'power'
        | 'thermal'
        | 'mechanical'
        | 'integration'
        | 'performance'
        | 'data-quality'
        | 'safety';
      description: string;
      displayId: string;
      evidenceReferences?: EvidenceReference10[];
      likelihood: 'rare' | 'unlikely' | 'possible' | 'likely';
      linkedArchitectureRefs?: string[];
      linkedComponentIds?: string[];
      linkedRequirementIds?: string[];
      linkedTestIds?: string[];
      mitigation: string;
      priorityScore: number;
      residualRisk?: string;
      riskId: string;
      severity: 'low' | 'medium' | 'high' | 'critical';
      status: 'open' | 'mitigating' | 'mitigated' | 'accepted' | 'monitoring';
      title: string;
      verificationTestIds?: string[];
    }[]
  ];
  schemaVersion: '1.0.0';
  summary: {
    highOrCritical: number;
    mitigated: number;
    openRisks: number;
    totalRisks: number;
    unverifiedMitigations: number;
  };
  title?: string;
}
export interface EvidenceReference10 {
  attribution?: ActorReference21;
  evidenceId: string;
  evidenceStrength: 'direct' | 'supporting' | 'inferred' | 'contradicting';
  schemaVersion: '1.0.0';
  sourceId: string;
  sourceLocator?: string;
  sourceType:
    'user-turn' | 'project-policy' | 'document' | 'external-source' | 'calculation' | 'test-result' | 'agent-inference';
  supportedClaim?: string;
}
export interface ActorReference21 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface ActorReference22 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
/**
 * Directed dependency between two project artifacts. Dependencies are recorded at artifact-type level so they survive artifact revisions, and may additionally pin the specific revisions involved.
 */
export interface ArtifactDependency {
  createdAt: string;
  dependencyId: string;
  dependencyKind: 'derives-from' | 'constrains' | 'covers' | 'blocks' | 'invalidates';
  projectId: string;
  reason: string;
  schemaVersion: '1.0.0';
  sourceArtifactId?: string;
  sourceArtifactType: ArtifactType1;
  targetArtifactId?: string;
  targetArtifactType: ArtifactType2;
}
export interface OpenQuestion {
  blocks: string[];
  createdAt: string;
  projectId: string;
  question: string;
  questionId: string;
  reason: string;
  requestedFrom: ActorReference23;
  schemaVersion: '1.0.0';
  /**
   * @minItems 1
   */
  sourceReferences: [
    {
      artifactId?: string;
      kind: 'artifact' | 'requirement';
      requirementId?: string;
    },
    ...{
      artifactId?: string;
      kind: 'artifact' | 'requirement';
      requirementId?: string;
    }[]
  ];
  status: 'open' | 'answered' | 'resolved' | 'dismissed';
  updatedAt: string;
}
export interface ActorReference23 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface Project {
  autonomyMode: 'collaborate' | 'delegate';
  blockerOrValidationIssueReferences: {
    issueId: string;
  }[];
  createdAt: string;
  currentArtifactReferences: {
    artifactId: string;
    artifactType: ArtifactType3;
    artifactVersion: number;
    contentSchemaVersion: '1.0.0';
  }[];
  currentStateVersion: number;
  domain: 'embedded-products';
  openQuestionReferences: OpenQuestionReference6[];
  projectId: string;
  projectPhase: 'concept' | 'prototype-planning';
  schemaVersion: '1.0.0';
  title: string;
  updatedAt: string;
}
export interface OpenQuestionReference6 {
  displayId?: string;
  questionId: string;
  schemaVersion: '1.0.0';
}
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
export interface UserTurn {
  actor: ActorReference24;
  attachmentReferences?: EvidenceReference11[];
  parentTurnId?: string;
  projectId: string;
  rawUserMessage: string;
  schemaVersion: '1.0.0';
  timestamp: string;
  turnId: string;
}
export interface ActorReference24 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface EvidenceReference11 {
  attribution?: ActorReference25;
  evidenceId: string;
  evidenceStrength: 'direct' | 'supporting' | 'inferred' | 'contradicting';
  schemaVersion: '1.0.0';
  sourceId: string;
  sourceLocator?: string;
  sourceType:
    'user-turn' | 'project-policy' | 'document' | 'external-source' | 'calculation' | 'test-result' | 'agent-inference';
  supportedClaim?: string;
}
export interface ActorReference25 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface ValidationIssue {
  artifactId?: string;
  blocking: boolean;
  code: string;
  createdAt: string;
  issueId: string;
  itemId?: string;
  message: string;
  projectId: string;
  resolutionStatus: 'open' | 'resolved';
  resolutionType: 'user-input' | 'artifact-regeneration' | 'manual-review' | 'automatic-fix' | 'not-applicable';
  resolvedAt?: string;
  schemaVersion: '1.0.0';
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  suggestedResolution?: string;
}
export interface VeraResponse {
  blockerIssueReferences: {
    issueId: string;
  }[];
  completionStatus: 'completed' | 'completed-with-warnings' | 'failed';
  /**
   * @minItems 1
   */
  createdArtifactReferences: [
    {
      artifactId: string;
      artifactType: ArtifactType4;
      artifactVersion: number;
      contentSchemaVersion: '1.0.0';
    },
    ...{
      artifactId: string;
      artifactType: ArtifactType4;
      artifactVersion: number;
      contentSchemaVersion: '1.0.0';
    }[]
  ];
  nextActionArtifactReference: {
    artifactId: string;
    artifactType: ArtifactType5;
    artifactVersion: number;
    contentSchemaVersion: '1.0.0';
  };
  openQuestionReferences: OpenQuestionReference7[];
  projectId: string;
  projectStateSummary: {
    autonomyMode: 'collaborate' | 'delegate';
    openQuestionCount: number;
    projectPhase: 'concept' | 'prototype-planning';
    validationIssueCount: number;
  };
  schemaVersion: '1.0.0';
  turnId: string;
  userFacingMessage: string;
  warningIssueReferences: {
    issueId: string;
  }[];
}
export interface OpenQuestionReference7 {
  displayId?: string;
  questionId: string;
  schemaVersion: '1.0.0';
}
export interface WorkflowRun {
  completionTime?: string;
  errorReferences: {
    issueId: string;
  }[];
  projectId: string;
  runStatus: 'pending' | 'running' | 'completed' | 'completed-with-warnings' | 'failed';
  schemaVersion: '1.0.0';
  startTime: string;
  stepRecords: {
    attempt: number;
    completedAt?: string;
    errorReference?: {
      issueId: string;
    };
    outputArtifactReferences?: {
      artifactId: string;
      artifactType: ArtifactType6;
      artifactVersion: number;
      contentSchemaVersion: '1.0.0';
    }[];
    startedAt?: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
    stepId: string;
    stepType: string;
  }[];
  turnId: string;
  warnings: {
    issueId: string;
  }[];
  workflowRunId: string;
  workflowType: 'embedded-project-initialization' | 'embedded-project-modification';
}
/**
 * Deterministic classification of how a project change propagates across artifact types. Every non-unchanged classification must carry an explicit reason so downstream regeneration is auditable.
 */
export interface ProjectImpactAnalysis {
  affected: ArtifactType7[];
  changed: ArtifactType8[];
  reasonByArtifact: {
    artifactType: ArtifactType9;
    reason: string;
  }[];
  regenerate: ArtifactType10[];
  schemaVersion: '1.0.0';
  stale: ArtifactType11[];
  unchanged: ArtifactType12[];
}
