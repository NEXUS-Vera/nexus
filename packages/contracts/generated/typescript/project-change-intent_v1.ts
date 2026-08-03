/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
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
    | 'change-project-scope';
  requestedChange: string;
  requiresUserConfirmation: boolean;
  schemaVersion: '1.0.0';
  sourceTurnId: string;
  targetArtifactType: 'project-brief' | 'requirement-set' | 'functional-architecture' | 'next-action' | null;
  targetQuestionId?: string;
  targetRequirementId?: string;
}
