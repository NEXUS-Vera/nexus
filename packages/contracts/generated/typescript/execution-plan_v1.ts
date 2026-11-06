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
  | 'risk-register'
  | 'execution-plan';

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
      criterion?: {
        criterionType: 'numeric-comparison' | 'exact-match' | 'contains' | 'existence' | 'structural-mapping' | 'range';
        expectedMapping?: string;
        expectedValue?: string | number | boolean;
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
      method: string;
      objectiveId: string;
      requirementId: string;
      verificationMethod?: 'inspection' | 'simulation' | 'firmware-test' | 'analysis' | 'execution-output' | 'manual';
      workspaceKey: string;
    },
    ...{
      acceptanceCriteria: string[];
      criterion?: {
        criterionType: 'numeric-comparison' | 'exact-match' | 'contains' | 'existence' | 'structural-mapping' | 'range';
        expectedMapping?: string;
        expectedValue?: string | number | boolean;
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
      method: string;
      objectiveId: string;
      requirementId: string;
      verificationMethod?: 'inspection' | 'simulation' | 'firmware-test' | 'analysis' | 'execution-output' | 'manual';
      workspaceKey: string;
    }[]
  ];
  /**
   * @minItems 1
   */
  workspaces: [
    {
      artifactType: ArtifactType;
      availability: 'artifact-available' | 'planned';
      workspaceKey: string;
    },
    ...{
      artifactType: ArtifactType;
      availability: 'artifact-available' | 'planned';
      workspaceKey: string;
    }[]
  ];
}
