/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export interface ProjectImpactAnalysis {
  affected: ('project-brief' | 'requirement-set' | 'functional-architecture' | 'next-action')[];
  changed: ('project-brief' | 'requirement-set' | 'functional-architecture' | 'next-action')[];
  reasonByArtifact: {
    artifactType: 'project-brief' | 'requirement-set' | 'functional-architecture' | 'next-action';
    reason: string;
  }[];
  regenerate: ('project-brief' | 'requirement-set' | 'functional-architecture' | 'next-action')[];
  schemaVersion: '1.0.0';
  stale: ('project-brief' | 'requirement-set' | 'functional-architecture' | 'next-action')[];
  unchanged: ('project-brief' | 'requirement-set' | 'functional-architecture' | 'next-action')[];
}
