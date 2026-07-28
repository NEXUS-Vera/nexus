/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
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
