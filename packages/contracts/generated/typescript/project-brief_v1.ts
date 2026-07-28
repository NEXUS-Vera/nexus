/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
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
