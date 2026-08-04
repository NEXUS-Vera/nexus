/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export type ArtifactType =
  'project-brief' | 'requirement-set' | 'functional-architecture' | 'next-action' | 'component-plan';
export type ArtifactType1 =
  'project-brief' | 'requirement-set' | 'functional-architecture' | 'next-action' | 'component-plan';

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
      artifactType: ArtifactType;
      artifactVersion: number;
      contentSchemaVersion: '1.0.0';
    },
    ...{
      artifactId: string;
      artifactType: ArtifactType;
      artifactVersion: number;
      contentSchemaVersion: '1.0.0';
    }[]
  ];
  nextActionArtifactReference: {
    artifactId: string;
    artifactType: ArtifactType1;
    artifactVersion: number;
    contentSchemaVersion: '1.0.0';
  };
  openQuestionReferences: OpenQuestionReference[];
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
export interface OpenQuestionReference {
  displayId?: string;
  questionId: string;
  schemaVersion: '1.0.0';
}
