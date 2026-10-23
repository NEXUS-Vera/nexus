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
  executionPlan?: ExecutionPlan;
  openQuestionReferences: OpenQuestionReference[];
  projectId: string;
  projectPhase: 'concept' | 'prototype-planning';
  schemaVersion: '1.0.0';
  title: string;
  updatedAt: string;
}
/**
 * Initialization review proposal pinned to source revisions; workspace keys are plan-local targets, not runtime workspace IDs.
 */
export interface ExecutionPlan {
  assumptions: {
    artifactId: string;
    entityId: string;
  }[];
  basisProjectStateVersion: number;
  components: {
    artifactId: string;
    entityId: string;
  }[];
  interfaces: {
    artifactId: string;
    entityId: string;
  }[];
  openDecisionIds: string[];
  /**
   * @minItems 1
   */
  requirements: [
    {
      artifactId: string;
      entityId: string;
    },
    ...{
      artifactId: string;
      entityId: string;
    }[]
  ];
  schemaVersion: '1.0.0';
  /**
   * @minItems 1
   */
  sourceArtifacts: [
    {
      artifactId: string;
      artifactVersion: number;
    },
    ...{
      artifactId: string;
      artifactVersion: number;
    }[]
  ];
  status: 'proposed';
  /**
   * @minItems 1
   */
  steps: [
    {
      dependsOn: string[];
      objectiveIds: string[];
      requiresApproval: true;
      stepId: string;
      title: string;
      workspaceKeys: string[];
    },
    ...{
      dependsOn: string[];
      objectiveIds: string[];
      requiresApproval: true;
      stepId: string;
      title: string;
      workspaceKeys: string[];
    }[]
  ];
  /**
   * @minItems 1
   */
  verificationObjectives: [
    {
      acceptanceCriteria: string[];
      method: string;
      objectiveId: string;
      requirementId: string;
      workspaceKey: string;
    },
    ...{
      acceptanceCriteria: string[];
      method: string;
      objectiveId: string;
      requirementId: string;
      workspaceKey: string;
    }[]
  ];
  /**
   * @minItems 1
   */
  workspaces: [
    {
      artifactType: ArtifactType1;
      availability: 'artifact-available' | 'planned';
      workspaceKey: string;
    },
    ...{
      artifactType: ArtifactType1;
      availability: 'artifact-available' | 'planned';
      workspaceKey: string;
    }[]
  ];
}
export interface OpenQuestionReference {
  displayId?: string;
  questionId: string;
  schemaVersion: '1.0.0';
}
