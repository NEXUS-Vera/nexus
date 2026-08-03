/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export interface ArtifactDependency {
  createdAt: string;
  dependencyId: string;
  dependencyKind: 'derives-from' | 'constrains' | 'covers' | 'blocks' | 'invalidates';
  projectId: string;
  reason: string;
  schemaVersion: '1.0.0';
  sourceArtifactId?: string;
  sourceArtifactType: 'project-brief' | 'requirement-set' | 'functional-architecture' | 'next-action';
  targetArtifactId?: string;
  targetArtifactType: 'project-brief' | 'requirement-set' | 'functional-architecture' | 'next-action';
}
