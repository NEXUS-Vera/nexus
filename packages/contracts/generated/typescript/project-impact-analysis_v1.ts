/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export type ArtifactType =
  'project-brief' | 'requirement-set' | 'functional-architecture' | 'next-action' | 'component-plan' | 'code-scratch';
export type ArtifactType1 =
  'project-brief' | 'requirement-set' | 'functional-architecture' | 'next-action' | 'component-plan' | 'code-scratch';
export type ArtifactType2 =
  'project-brief' | 'requirement-set' | 'functional-architecture' | 'next-action' | 'component-plan' | 'code-scratch';
export type ArtifactType3 =
  'project-brief' | 'requirement-set' | 'functional-architecture' | 'next-action' | 'component-plan' | 'code-scratch';
export type ArtifactType4 =
  'project-brief' | 'requirement-set' | 'functional-architecture' | 'next-action' | 'component-plan' | 'code-scratch';
export type ArtifactType5 =
  'project-brief' | 'requirement-set' | 'functional-architecture' | 'next-action' | 'component-plan' | 'code-scratch';

/**
 * Deterministic classification of how a project change propagates across artifact types. Every non-unchanged classification must carry an explicit reason so downstream regeneration is auditable.
 */
export interface ProjectImpactAnalysis {
  affected: ArtifactType[];
  changed: ArtifactType1[];
  reasonByArtifact: {
    artifactType: ArtifactType2;
    reason: string;
  }[];
  regenerate: ArtifactType3[];
  schemaVersion: '1.0.0';
  stale: ArtifactType4[];
  unchanged: ArtifactType5[];
}
