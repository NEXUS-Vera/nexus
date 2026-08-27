/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export type ArtifactType =
  | 'project-brief'
  | 'requirement-set'
  | 'functional-architecture'
  | 'next-action'
  | 'component-plan'
  | 'electrical-architecture'
  | 'physical-architecture'
  | 'code-scratch'
  | 'firmware'
  | 'analysis'
  | 'test-plan'
  | 'risk-register';

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
      artifactType: ArtifactType;
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
