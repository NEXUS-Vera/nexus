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
  | 'risk-register';
export type ArtifactType1 =
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
  | 'risk-register';

export interface ArtifactTypeDefinition {
  approvalPolicyId: string;
  artifactType: ArtifactType;
  boardVisibility: 'primary' | 'global' | 'hidden';
  dependencies: {
    artifactType: ArtifactType1;
    relationship: 'depends-on' | 'derives-from' | 'constrains' | 'covers';
    required?: boolean;
  }[];
  displayName: string;
  editable: boolean;
  executable: boolean;
  phase: 'DEFINE' | 'DESIGN' | 'BUILD' | 'VERIFY';
  requiredCapabilities: (
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
  supportedCommandTypes: (
    | 'workspace.create'
    | 'workspace.update-draft'
    | 'workspace.acquire-edit-lease'
    | 'workspace.release-edit-lease'
    | 'workspace.discard-draft'
    | 'workspace.create-snapshot'
    | 'workspace.restore-snapshot'
    | 'artifact.validate-draft'
    | 'artifact.propose-revision'
    | 'artifact.accept-revision'
    | 'artifact.reject-revision'
    | 'artifact.execute'
    | 'artifact.inspect-deletion-impact'
  )[];
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
