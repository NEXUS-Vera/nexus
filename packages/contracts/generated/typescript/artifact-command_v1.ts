/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export type ArtifactCommand =
  | {
      artifactId: string;
      baseArtifactVersion: number;
      baseProjectStateVersion: number;
      commandId: string;
      commandType: 'workspace.create';
      input: {
        artifactType: ArtifactType;
        initialContent?: {
          [k: string]: any;
        };
      };
      projectId: string;
      requestedAt: string;
      requestedBy: ActorReference;
      schemaVersion: '1.0.0';
      workspaceId?: string;
    }
  | {
      artifactId: string;
      baseArtifactVersion: number;
      baseProjectStateVersion: number;
      commandId: string;
      commandType: 'workspace.update-draft';
      input: {
        content: {
          [k: string]: any;
        };
        expectedDraftVersion: number;
      };
      projectId: string;
      requestedAt: string;
      requestedBy: ActorReference1;
      schemaVersion: '1.0.0';
      workspaceId: string;
    }
  | {
      artifactId: string;
      baseArtifactVersion: number;
      baseProjectStateVersion: number;
      commandId: string;
      commandType: 'workspace.create-snapshot';
      input: {
        reason: string;
      };
      projectId: string;
      requestedAt: string;
      requestedBy: ActorReference2;
      schemaVersion: '1.0.0';
      workspaceId: string;
    }
  | {
      artifactId: string;
      baseArtifactVersion: number;
      baseProjectStateVersion: number;
      commandId: string;
      commandType: 'workspace.restore-snapshot';
      input: {
        snapshotId: string;
      };
      projectId: string;
      requestedAt: string;
      requestedBy: ActorReference3;
      schemaVersion: '1.0.0';
      workspaceId: string;
    }
  | {
      artifactId: string;
      baseArtifactVersion: number;
      baseProjectStateVersion: number;
      commandId: string;
      commandType: 'artifact.validate-draft';
      input: {
        snapshotId: string;
      };
      projectId: string;
      requestedAt: string;
      requestedBy: ActorReference4;
      schemaVersion: '1.0.0';
      workspaceId: string;
    }
  | {
      artifactId: string;
      baseArtifactVersion: number;
      baseProjectStateVersion: number;
      commandId: string;
      commandType: 'artifact.propose-revision';
      input: {
        consequenceLevel: ConsequenceLevel;
        snapshotId: string;
        summary?: string;
      };
      projectId: string;
      requestedAt: string;
      requestedBy: ActorReference5;
      schemaVersion: '1.0.0';
      workspaceId: string;
    }
  | {
      artifactId: string;
      baseArtifactVersion: number;
      baseProjectStateVersion: number;
      commandId: string;
      commandType: 'artifact.accept-revision';
      input: {
        proposalId: string;
        reason?: string;
      };
      projectId: string;
      requestedAt: string;
      requestedBy: ActorReference6;
      schemaVersion: '1.0.0';
      workspaceId: string;
    }
  | {
      artifactId: string;
      baseArtifactVersion: number;
      baseProjectStateVersion: number;
      commandId: string;
      commandType: 'artifact.reject-revision';
      input: {
        proposalId: string;
        reason: string;
      };
      projectId: string;
      requestedAt: string;
      requestedBy: ActorReference7;
      schemaVersion: '1.0.0';
      workspaceId: string;
    }
  | {
      artifactId: string;
      baseArtifactVersion: number;
      baseProjectStateVersion: number;
      commandId: string;
      commandType: 'artifact.execute';
      input: {
        capability:
          | 'structured-validation'
          | 'fake-execution'
          | 'file-workspace'
          | 'embedded-build'
          | 'python-kernel'
          | 'circuit-simulation'
          | 'architecture-export';
        maxDurationMs?: number;
        snapshotId: string;
      };
      projectId: string;
      requestedAt: string;
      requestedBy: ActorReference8;
      schemaVersion: '1.0.0';
      workspaceId: string;
    };
export type ArtifactType =
  'project-brief' | 'requirement-set' | 'functional-architecture' | 'next-action' | 'component-plan';
export type ConsequenceLevel = 'low' | 'medium' | 'high' | 'safety-critical';

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
export interface ActorReference2 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface ActorReference3 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface ActorReference4 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface ActorReference5 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface ActorReference6 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface ActorReference7 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface ActorReference8 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
