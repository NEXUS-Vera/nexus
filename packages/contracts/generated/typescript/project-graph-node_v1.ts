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

export interface ProjectGraphNode {
  artifactType?: ArtifactType;
  createdAt: string;
  createdByEventId?: string;
  label: string;
  nodeId: string;
  nodeType:
    | 'artifact'
    | 'artifact-revision'
    | 'requirement'
    | 'architecture-node'
    | 'electrical-node'
    | 'physical-node'
    | 'component-role'
    | 'question'
    | 'validation-issue'
    | 'decision'
    | 'evidence'
    | 'execution'
    | 'output'
    | 'workspace';
  projectId: string;
  refId?: string;
  schemaVersion: '1.0.0';
}
