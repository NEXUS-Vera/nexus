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
  | 'risk-register'
  | 'execution-plan';

export interface ArtifactEntityReference {
  artifactId: string;
  artifactType: ArtifactType;
  artifactVersion?: number;
  displayLabel?: string;
  entityId: string;
  entityType:
    | 'requirement'
    | 'functional-node'
    | 'functional-edge'
    | 'component-role'
    | 'component-candidate'
    | 'selection-decision'
    | 'electrical-node'
    | 'electrical-connection'
    | 'electrical-interface'
    | 'power-domain'
    | 'physical-node'
    | 'physical-relationship'
    | 'physical-zone'
    | 'open-question'
    | 'other';
  schemaVersion: '1.0.0';
}
