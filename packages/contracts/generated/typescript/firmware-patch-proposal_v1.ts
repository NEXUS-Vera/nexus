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

export interface FirmwarePatchProposal {
  artifactId: string;
  artifactType: 'firmware';
  baseSnapshotId: string;
  decidedAt?: string;
  decidedBy?: ActorReference;
  generatorId: string;
  generatorVersion: string;
  inputArtifactReferences: {
    artifactId?: string;
    artifactType: ArtifactType;
    artifactVersion: number;
  }[];
  /**
   * @minItems 1
   * @maxItems 32
   */
  operations: [
    (
      | {
          content: string;
          contentHash: string;
          operationType: 'create-file';
          path: string;
        }
      | {
          content: string;
          contentHash: string;
          expectedBaseHash: string;
          operationType: 'replace-file';
          path: string;
        }
      | {
          expectedBaseHash: string;
          operationType: 'delete-file';
          path: string;
        }
    ),
    ...(
      | {
          content: string;
          contentHash: string;
          operationType: 'create-file';
          path: string;
        }
      | {
          content: string;
          contentHash: string;
          expectedBaseHash: string;
          operationType: 'replace-file';
          path: string;
        }
      | {
          expectedBaseHash: string;
          operationType: 'delete-file';
          path: string;
        }
    )[]
  ];
  projectId: string;
  proposalId: string;
  requestedAt: string;
  requestedBy: ActorReference1;
  requestedChange: string;
  schemaVersion: '1.0.0';
  status: 'proposed' | 'applied' | 'discarded';
  workspaceId: string;
}
export interface ActorReference {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface ActorReference1 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
