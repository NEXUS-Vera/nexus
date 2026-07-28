/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export type Artifact =
  | (ArtifactEnvelope & {
      artifactType: 'project-brief';
      content: ProjectBriefContent1;
      [k: string]: any;
    })
  | (ArtifactEnvelope1 & {
      artifactType: 'requirement-set';
      content: RequirementSetContent2;
      [k: string]: any;
    })
  | (ArtifactEnvelope2 & {
      artifactType: 'functional-architecture';
      content: FunctionalArchitectureContent3;
      [k: string]: any;
    })
  | (ArtifactEnvelope3 & {
      artifactType: 'next-action';
      content: NextActionContent4;
      [k: string]: any;
    });
export type TurnRoute = {
  [k: string]: any;
} & {
  autonomyMode: 'collaborate' | 'delegate';
  chairmanRequiredEventually: boolean;
  complexity: 'low' | 'medium' | 'high' | 'unknown';
  domain: 'embedded-products';
  projectOperation: 'create-project' | 'none';
  /**
   * @minItems 1
   */
  reasons: [string, ...string[]];
  routeId: string;
  routeType: 'project-initialization' | 'unsupported';
  schemaVersion: '1.0.0';
  supported: boolean;
  turnId: string;
  unsupportedReason?: string;
};

/**
 * Canonical wrapper for a successful fixture-backed embedded project initialization package.
 */
export interface ProjectInitializationResult {
  /**
   * @minItems 4
   * @maxItems 4
   */
  artifacts: {
    [k: string]: any;
  } & [Artifact, Artifact, Artifact, Artifact];
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
  artifactType: 'project-brief' | 'requirement-set' | 'functional-architecture' | 'next-action';
  artifactVersion: number;
  content: ProjectBriefContent | RequirementSetContent | FunctionalArchitectureContent | NextActionContent;
  contentSchemaVersion: '1.0.0';
  createdAt: string;
  createdBy: ActorReference1;
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
export interface Quantity {
  schemaVersion: '1.0.0';
  unit: string;
  value: number;
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
export interface ActorReference1 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface ProjectBriefContent1 {
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
  unknowns: OpenQuestionReference4[];
}
export interface OpenQuestionReference4 {
  displayId?: string;
  questionId: string;
  schemaVersion: '1.0.0';
}
export interface ArtifactEnvelope1 {
  approvalStatus: 'not-required' | 'proposed' | 'awaiting-user' | 'user-approved' | 'agent-decided' | 'rejected';
  artifactId: string;
  artifactType: 'project-brief' | 'requirement-set' | 'functional-architecture' | 'next-action';
  artifactVersion: number;
  content: ProjectBriefContent2 | RequirementSetContent1 | FunctionalArchitectureContent1 | NextActionContent1;
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
export interface ProjectBriefContent2 {
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
  unknowns: OpenQuestionReference5[];
}
export interface OpenQuestionReference5 {
  displayId?: string;
  questionId: string;
  schemaVersion: '1.0.0';
}
export interface RequirementSetContent1 {
  missingDimensions?: string[];
  openQuestionIds?: OpenQuestionReference6[];
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
      sourceReference: EvidenceReference1;
      sourceType: 'user-explicit' | 'user-implied' | 'system-inferred' | 'project-policy';
      statement: string;
      targetQuantity?: Quantity1;
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
      sourceReference: EvidenceReference1;
      sourceType: 'user-explicit' | 'user-implied' | 'system-inferred' | 'project-policy';
      statement: string;
      targetQuantity?: Quantity1;
      verificationMethod: string;
    }[]
  ];
}
export interface OpenQuestionReference6 {
  displayId?: string;
  questionId: string;
  schemaVersion: '1.0.0';
}
export interface EvidenceReference1 {
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
export interface Quantity1 {
  schemaVersion: '1.0.0';
  unit: string;
  value: number;
}
export interface FunctionalArchitectureContent1 {
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
  unresolvedDecisions: OpenQuestionReference7[];
}
export interface OpenQuestionReference7 {
  displayId?: string;
  questionId: string;
  schemaVersion: '1.0.0';
}
export interface NextActionContent1 {
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
  prerequisites: OpenQuestionReference8[];
  priority: 'critical' | 'high' | 'medium' | 'low';
  rationale: string;
  sourceIssueIds: string[];
  sourceQuestionIds: string[];
  title: string;
}
export interface OpenQuestionReference8 {
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
export interface RequirementSetContent2 {
  missingDimensions?: string[];
  openQuestionIds?: OpenQuestionReference9[];
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
      sourceReference: EvidenceReference2;
      sourceType: 'user-explicit' | 'user-implied' | 'system-inferred' | 'project-policy';
      statement: string;
      targetQuantity?: Quantity2;
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
      sourceReference: EvidenceReference2;
      sourceType: 'user-explicit' | 'user-implied' | 'system-inferred' | 'project-policy';
      statement: string;
      targetQuantity?: Quantity2;
      verificationMethod: string;
    }[]
  ];
}
export interface OpenQuestionReference9 {
  displayId?: string;
  questionId: string;
  schemaVersion: '1.0.0';
}
export interface EvidenceReference2 {
  attribution?: ActorReference4;
  evidenceId: string;
  evidenceStrength: 'direct' | 'supporting' | 'inferred' | 'contradicting';
  schemaVersion: '1.0.0';
  sourceId: string;
  sourceLocator?: string;
  sourceType:
    'user-turn' | 'project-policy' | 'document' | 'external-source' | 'calculation' | 'test-result' | 'agent-inference';
  supportedClaim?: string;
}
export interface ActorReference4 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface Quantity2 {
  schemaVersion: '1.0.0';
  unit: string;
  value: number;
}
export interface ArtifactEnvelope2 {
  approvalStatus: 'not-required' | 'proposed' | 'awaiting-user' | 'user-approved' | 'agent-decided' | 'rejected';
  artifactId: string;
  artifactType: 'project-brief' | 'requirement-set' | 'functional-architecture' | 'next-action';
  artifactVersion: number;
  content: ProjectBriefContent3 | RequirementSetContent3 | FunctionalArchitectureContent2 | NextActionContent2;
  contentSchemaVersion: '1.0.0';
  createdAt: string;
  createdBy: ActorReference6;
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
export interface ProjectBriefContent3 {
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
  unknowns: OpenQuestionReference10[];
}
export interface OpenQuestionReference10 {
  displayId?: string;
  questionId: string;
  schemaVersion: '1.0.0';
}
export interface RequirementSetContent3 {
  missingDimensions?: string[];
  openQuestionIds?: OpenQuestionReference11[];
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
      sourceReference: EvidenceReference3;
      sourceType: 'user-explicit' | 'user-implied' | 'system-inferred' | 'project-policy';
      statement: string;
      targetQuantity?: Quantity3;
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
      sourceReference: EvidenceReference3;
      sourceType: 'user-explicit' | 'user-implied' | 'system-inferred' | 'project-policy';
      statement: string;
      targetQuantity?: Quantity3;
      verificationMethod: string;
    }[]
  ];
}
export interface OpenQuestionReference11 {
  displayId?: string;
  questionId: string;
  schemaVersion: '1.0.0';
}
export interface EvidenceReference3 {
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
export interface Quantity3 {
  schemaVersion: '1.0.0';
  unit: string;
  value: number;
}
export interface FunctionalArchitectureContent2 {
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
  unresolvedDecisions: OpenQuestionReference12[];
}
export interface OpenQuestionReference12 {
  displayId?: string;
  questionId: string;
  schemaVersion: '1.0.0';
}
export interface NextActionContent2 {
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
  prerequisites: OpenQuestionReference13[];
  priority: 'critical' | 'high' | 'medium' | 'low';
  rationale: string;
  sourceIssueIds: string[];
  sourceQuestionIds: string[];
  title: string;
}
export interface OpenQuestionReference13 {
  displayId?: string;
  questionId: string;
  schemaVersion: '1.0.0';
}
export interface ActorReference6 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface FunctionalArchitectureContent3 {
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
  unresolvedDecisions: OpenQuestionReference14[];
}
export interface OpenQuestionReference14 {
  displayId?: string;
  questionId: string;
  schemaVersion: '1.0.0';
}
export interface ArtifactEnvelope3 {
  approvalStatus: 'not-required' | 'proposed' | 'awaiting-user' | 'user-approved' | 'agent-decided' | 'rejected';
  artifactId: string;
  artifactType: 'project-brief' | 'requirement-set' | 'functional-architecture' | 'next-action';
  artifactVersion: number;
  content: ProjectBriefContent4 | RequirementSetContent4 | FunctionalArchitectureContent4 | NextActionContent3;
  contentSchemaVersion: '1.0.0';
  createdAt: string;
  createdBy: ActorReference8;
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
export interface ProjectBriefContent4 {
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
  unknowns: OpenQuestionReference15[];
}
export interface OpenQuestionReference15 {
  displayId?: string;
  questionId: string;
  schemaVersion: '1.0.0';
}
export interface RequirementSetContent4 {
  missingDimensions?: string[];
  openQuestionIds?: OpenQuestionReference16[];
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
      sourceReference: EvidenceReference4;
      sourceType: 'user-explicit' | 'user-implied' | 'system-inferred' | 'project-policy';
      statement: string;
      targetQuantity?: Quantity4;
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
      sourceReference: EvidenceReference4;
      sourceType: 'user-explicit' | 'user-implied' | 'system-inferred' | 'project-policy';
      statement: string;
      targetQuantity?: Quantity4;
      verificationMethod: string;
    }[]
  ];
}
export interface OpenQuestionReference16 {
  displayId?: string;
  questionId: string;
  schemaVersion: '1.0.0';
}
export interface EvidenceReference4 {
  attribution?: ActorReference7;
  evidenceId: string;
  evidenceStrength: 'direct' | 'supporting' | 'inferred' | 'contradicting';
  schemaVersion: '1.0.0';
  sourceId: string;
  sourceLocator?: string;
  sourceType:
    'user-turn' | 'project-policy' | 'document' | 'external-source' | 'calculation' | 'test-result' | 'agent-inference';
  supportedClaim?: string;
}
export interface ActorReference7 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface Quantity4 {
  schemaVersion: '1.0.0';
  unit: string;
  value: number;
}
export interface FunctionalArchitectureContent4 {
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
  unresolvedDecisions: OpenQuestionReference17[];
}
export interface OpenQuestionReference17 {
  displayId?: string;
  questionId: string;
  schemaVersion: '1.0.0';
}
export interface NextActionContent3 {
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
  prerequisites: OpenQuestionReference18[];
  priority: 'critical' | 'high' | 'medium' | 'low';
  rationale: string;
  sourceIssueIds: string[];
  sourceQuestionIds: string[];
  title: string;
}
export interface OpenQuestionReference18 {
  displayId?: string;
  questionId: string;
  schemaVersion: '1.0.0';
}
export interface ActorReference8 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface NextActionContent4 {
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
  prerequisites: OpenQuestionReference19[];
  priority: 'critical' | 'high' | 'medium' | 'low';
  rationale: string;
  sourceIssueIds: string[];
  sourceQuestionIds: string[];
  title: string;
}
export interface OpenQuestionReference19 {
  displayId?: string;
  questionId: string;
  schemaVersion: '1.0.0';
}
export interface OpenQuestion {
  blocks: string[];
  createdAt: string;
  projectId: string;
  question: string;
  questionId: string;
  reason: string;
  requestedFrom: ActorReference9;
  schemaVersion: '1.0.0';
  /**
   * @minItems 1
   */
  sourceReferences: [
    {
      [k: string]: any;
    } & {
      [k: string]: any;
    },
    ...({
      [k: string]: any;
    } & {
      [k: string]: any;
    })[]
  ];
  status: 'open' | 'answered' | 'resolved' | 'dismissed';
  updatedAt: string;
}
export interface ActorReference9 {
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
    artifactType: 'project-brief' | 'requirement-set' | 'functional-architecture' | 'next-action';
    artifactVersion: number;
    contentSchemaVersion: '1.0.0';
  }[];
  currentStateVersion: number;
  domain: 'embedded-products';
  openQuestionReferences: OpenQuestionReference20[];
  projectId: string;
  projectPhase: 'concept' | 'prototype-planning';
  schemaVersion: '1.0.0';
  title: string;
  updatedAt: string;
}
export interface OpenQuestionReference20 {
  displayId?: string;
  questionId: string;
  schemaVersion: '1.0.0';
}
export interface UserTurn {
  actor: ActorReference10;
  attachmentReferences?: EvidenceReference5[];
  parentTurnId?: string;
  projectId: string;
  rawUserMessage: string;
  schemaVersion: '1.0.0';
  timestamp: string;
  turnId: string;
}
export interface ActorReference10 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface EvidenceReference5 {
  attribution?: ActorReference11;
  evidenceId: string;
  evidenceStrength: 'direct' | 'supporting' | 'inferred' | 'contradicting';
  schemaVersion: '1.0.0';
  sourceId: string;
  sourceLocator?: string;
  sourceType:
    'user-turn' | 'project-policy' | 'document' | 'external-source' | 'calculation' | 'test-result' | 'agent-inference';
  supportedClaim?: string;
}
export interface ActorReference11 {
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
      artifactType: 'project-brief' | 'requirement-set' | 'functional-architecture' | 'next-action';
      artifactVersion: number;
      contentSchemaVersion: '1.0.0';
    },
    ...{
      artifactId: string;
      artifactType: 'project-brief' | 'requirement-set' | 'functional-architecture' | 'next-action';
      artifactVersion: number;
      contentSchemaVersion: '1.0.0';
    }[]
  ];
  nextActionArtifactReference: {
    artifactId: string;
    artifactType: 'project-brief' | 'requirement-set' | 'functional-architecture' | 'next-action';
    artifactVersion: number;
    contentSchemaVersion: '1.0.0';
  };
  openQuestionReferences: OpenQuestionReference21[];
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
export interface OpenQuestionReference21 {
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
      artifactType: 'project-brief' | 'requirement-set' | 'functional-architecture' | 'next-action';
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
  workflowType: 'embedded-project-initialization';
}
