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
  | 'physical-architecture';

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
  openQuestionReferences: OpenQuestionReference[];
  projectId: string;
  projectPhase: 'concept' | 'prototype-planning';
  schemaVersion: '1.0.0';
  title: string;
  updatedAt: string;
}
export interface OpenQuestionReference {
  displayId?: string;
  questionId: string;
  schemaVersion: '1.0.0';
}
