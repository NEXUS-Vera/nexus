/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export interface WorkspaceSnapshot {
  artifactId: string;
  baseArtifactVersion: number;
  baseProjectStateVersion: number;
  content:
    | {
        kind: 'structured';
        structuredContent: {
          [k: string]: any;
        };
      }
    | {
        filesystemManifest: {
          entries: {
            contentHash: string;
            contentReference: string;
            generatedFrom?: string;
            mediaType?: string;
            modifiedByUser: boolean;
            origin: 'USER' | 'GENERATED' | 'SYSTEM' | 'RUNTIME_OUTPUT';
            path: string;
            sizeBytes: number;
            writePolicy: 'USER_EDITABLE' | 'REGENERATION_MANAGED' | 'READ_ONLY' | 'EPHEMERAL';
          }[];
          manifestDigest: string;
        };
        kind: 'filesystem';
      }
    | {
        contentDigest: string;
        kind: 'storage-reference';
        storageKind: 'postgres-jsonb' | 'object-store' | 'file-store';
        uri: string;
      };
  contentDigest: string;
  createdAt: string;
  createdBy: ActorReference;
  projectId: string;
  reason: string;
  schemaVersion: '1.0.0';
  snapshotId: string;
  snapshotVersion: number;
  workspaceId: string;
}
export interface ActorReference {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
