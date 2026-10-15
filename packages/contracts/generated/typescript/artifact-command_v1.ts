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
          | 'sandbox-execution'
          | 'embedded-build'
          | 'python-kernel'
          | 'circuit-simulation'
          | 'architecture-export';
        commandSpec?: ExecutionCommandSpec;
        executionMode?: 'validate' | 'simulate';
        expectedText?: string;
        maxDurationMs?: number;
        maxOutputBytes?: number;
        /**
         * @maxItems 4
         */
        requestedOutputs?:
          | []
          | ['serial-log' | 'logic-trace' | 'simulation-screenshot' | 'provider-workspace']
          | [
              'serial-log' | 'logic-trace' | 'simulation-screenshot' | 'provider-workspace',
              'serial-log' | 'logic-trace' | 'simulation-screenshot' | 'provider-workspace'
            ]
          | [
              'serial-log' | 'logic-trace' | 'simulation-screenshot' | 'provider-workspace',
              'serial-log' | 'logic-trace' | 'simulation-screenshot' | 'provider-workspace',
              'serial-log' | 'logic-trace' | 'simulation-screenshot' | 'provider-workspace'
            ]
          | [
              'serial-log' | 'logic-trace' | 'simulation-screenshot' | 'provider-workspace',
              'serial-log' | 'logic-trace' | 'simulation-screenshot' | 'provider-workspace',
              'serial-log' | 'logic-trace' | 'simulation-screenshot' | 'provider-workspace',
              'serial-log' | 'logic-trace' | 'simulation-screenshot' | 'provider-workspace'
            ];
        snapshotId: string;
      };
      projectId: string;
      requestedAt: string;
      requestedBy: ActorReference8;
      schemaVersion: '1.0.0';
      workspaceId: string;
    }
  | {
      artifactId: string;
      baseArtifactVersion: number;
      baseProjectStateVersion: number;
      commandId: string;
      commandType: 'workspace.acquire-edit-lease';
      input: {
        ttlSeconds?: number;
      };
      projectId: string;
      requestedAt: string;
      requestedBy: ActorReference9;
      schemaVersion: '1.0.0';
      workspaceId: string;
    }
  | {
      artifactId: string;
      baseArtifactVersion: number;
      baseProjectStateVersion: number;
      commandId: string;
      commandType: 'workspace.release-edit-lease';
      input: {
        leaseToken?: string;
      };
      projectId: string;
      requestedAt: string;
      requestedBy: ActorReference10;
      schemaVersion: '1.0.0';
      workspaceId: string;
    }
  | {
      artifactId: string;
      baseArtifactVersion: number;
      baseProjectStateVersion: number;
      commandId: string;
      commandType: 'workspace.discard-draft';
      input: {
        expectedDraftVersion: number;
        refreshLease?: boolean;
      };
      projectId: string;
      requestedAt: string;
      requestedBy: ActorReference11;
      schemaVersion: '1.0.0';
      workspaceId: string;
    }
  | {
      artifactId: string;
      baseArtifactVersion: number;
      baseProjectStateVersion: number;
      commandId: string;
      commandType: 'artifact.inspect-deletion-impact';
      input: {
        entityId: string;
        entityType: 'functional-node';
      };
      projectId: string;
      requestedAt: string;
      requestedBy: ActorReference12;
      schemaVersion: '1.0.0';
      workspaceId?: string;
    };
export type ArtifactType =
  | 'project-brief'
  | 'requirement-set'
  | 'functional-architecture'
  | 'next-action'
  | 'component-plan'
  | 'code-scratch'
  | 'firmware'
  | 'electrical-architecture'
  | 'physical-architecture';
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
export interface ExecutionCommandSpec {
  /**
   * @maxItems 64
   */
  arguments: string[];
  /**
   * @maxItems 32
   */
  declaredOutputs: {
    kind: 'result' | 'artifact' | 'log';
    path: string;
  }[];
  /**
   * Explicit non-secret environment values. Backend secrets must never appear here.
   *
   * @maxItems 64
   */
  environment: {
    name: string;
    value: string;
  }[];
  /**
   * Executable name or workspace-relative path. Must not be a host absolute path.
   */
  executable: string;
  schemaVersion: '1.0.0';
  /**
   * Workspace-relative working directory scoped to the materialized snapshot. Empty string means snapshot root.
   */
  workingDirectory: string;
}
export interface ActorReference8 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface ActorReference9 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface ActorReference10 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface ActorReference11 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface ActorReference12 {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
