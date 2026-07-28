/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export interface OpenQuestion {
  blocks: string[];
  createdAt: string;
  projectId: string;
  question: string;
  questionId: string;
  reason: string;
  requestedFrom: ActorReference;
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
export interface ActorReference {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
