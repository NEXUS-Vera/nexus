/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export type ArtifactType =
  'project-brief' | 'requirement-set' | 'functional-architecture' | 'next-action' | 'component-plan' | 'code-scratch';

export interface WorkspaceDescriptor {
  artifactId: string;
  artifactType: ArtifactType;
  baseArtifactVersion: number;
  baseProjectStateVersion: number;
  createdAt: string;
  createdBy: ActorReference;
  currentSnapshotId?: string;
  externalWorkspaceReferences: ExternalWorkspaceReference[];
  projectId: string;
  runtimeCapabilityRequirements: (
    | 'structured-validation'
    | 'fake-execution'
    | 'file-workspace'
    | 'sandbox-execution'
    | 'embedded-build'
    | 'python-kernel'
    | 'circuit-simulation'
    | 'architecture-export'
  )[];
  schemaVersion: '1.0.0';
  status: 'creating' | 'ready' | 'dirty' | 'validating' | 'blocked' | 'archived';
  updatedAt: string;
  workspaceId: string;
  workspaceType:
    | 'structured-document'
    | 'graph-workspace'
    | 'comparison-workspace'
    | 'code-workspace'
    | 'notebook-workspace'
    | 'test-workspace'
    | 'risk-workspace'
    | 'focused-action';
}
export interface ActorReference {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
export interface ExternalWorkspaceReference {
  createdAt: string;
  displayLabel?: string;
  externalReferenceId: string;
  lastSyncedAt?: string;
  providerId: 'fake' | 'wokwi' | 'flux' | 'jupyter' | 'github' | 'kicad';
  schemaVersion: '1.0.0';
  syncStatus: 'unbound' | 'bound' | 'stale' | 'error';
  updatedAt: string;
}
