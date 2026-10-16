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

/**
 * Directed dependency between two project artifacts. Dependencies are recorded at artifact-type level so they survive artifact revisions, and may additionally pin the specific revisions involved.
 */
export interface ArtifactDependency {
  createdAt: string;
  dependencyId: string;
  dependencyKind: 'derives-from' | 'constrains' | 'covers' | 'blocks' | 'invalidates';
  projectId: string;
  reason: string;
  schemaVersion: '1.0.0';
  sourceArtifactId?: string;
  sourceArtifactType: ArtifactType;
  targetArtifactId?: string;
  targetArtifactType: ArtifactType1;
}
