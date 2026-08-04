/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export type Artifact = ArtifactEnvelope | ArtifactEnvelope1 | ArtifactEnvelope2 | ArtifactEnvelope3 | ArtifactEnvelope4;
export type ArtifactType =
  'project-brief' | 'requirement-set' | 'functional-architecture' | 'next-action' | 'component-plan';
export type ArtifactType1 =
  'project-brief' | 'requirement-set' | 'functional-architecture' | 'next-action' | 'component-plan';
export type ArtifactType2 =
  'project-brief' | 'requirement-set' | 'functional-architecture' | 'next-action' | 'component-plan';
export type ArtifactType3 =
  'project-brief' | 'requirement-set' | 'functional-architecture' | 'next-action' | 'component-plan';

/**
 * Canonical wrapper for a successful fixture-backed embedded project initialization package.
 */
export interface ProjectInitializationResult {
  /**
   * @minItems 4
   * @maxItems 4
   */
  artifacts: [Artifact, Artifact, Artifact, Artifact];
  openQuestions: OpenQuestion[];
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
  createdBy: ActorReference5;
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
export interface ComponentPlanContent {
  approvalStatus: 'not-required' | 'proposed' | 'awaiting-user' | 'user-approved' | 'agent-decided' | 'rejected';
  candidateCount: number;
  constraintSummary: string;
  selectionState: 'draft' | 'proposed' | 'accepted' | 'blocked';
  unresolvedCompatibilityChecks: string[];
}
export interface ActorReference5 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface OpenQuestion {
  blocks: string[];
  createdAt: string;
  projectId: string;
  question: string;
  questionId: string;
  reason: string;
  requestedFrom: ActorReference6;
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
export interface ActorReference6 {
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
    artifactType: ArtifactType;
    artifactVersion: number;
    contentSchemaVersion: '1.0.0';
  }[];
  currentStateVersion: number;
  domain: 'embedded-products';
  openQuestionReferences: OpenQuestionReference4[];
  projectId: string;
  projectPhase: 'concept' | 'prototype-planning';
  schemaVersion: '1.0.0';
  title: string;
  updatedAt: string;
}
export interface OpenQuestionReference4 {
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
  actor: ActorReference7;
  attachmentReferences?: EvidenceReference1[];
  parentTurnId?: string;
  projectId: string;
  rawUserMessage: string;
  schemaVersion: '1.0.0';
  timestamp: string;
  turnId: string;
}
export interface ActorReference7 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface EvidenceReference1 {
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
      artifactType: ArtifactType1;
      artifactVersion: number;
      contentSchemaVersion: '1.0.0';
    },
    ...{
      artifactId: string;
      artifactType: ArtifactType1;
      artifactVersion: number;
      contentSchemaVersion: '1.0.0';
    }[]
  ];
  nextActionArtifactReference: {
    artifactId: string;
    artifactType: ArtifactType2;
    artifactVersion: number;
    contentSchemaVersion: '1.0.0';
  };
  openQuestionReferences: OpenQuestionReference5[];
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
export interface OpenQuestionReference5 {
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
      artifactType: ArtifactType3;
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
