/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export type ArtifactType =
  | 'project-brief'
  | 'requirement-set'
  | 'functional-architecture'
  | 'next-action'
  | 'component-plan'
  | 'electrical-architecture'
  | 'physical-architecture';

export interface CircuitSimulationSupportAssessment {
  capabilityId: 'circuit-simulation';
  findings: {
    entityReference?: ArtifactEntityReference;
    findingId: string;
    mappingType: 'exact' | 'equivalent' | 'surrogate' | 'unsupported';
    message: string;
    reasonCode: string;
  }[];
  firmwareRequired: boolean;
  providerId: string;
  schemaVersion: '1.0.0';
  status: 'SUPPORTED' | 'PARTIALLY_SUPPORTED' | 'UNSUPPORTED' | 'SURROGATE_REQUIRED' | 'FIRMWARE_REQUIRED';
  surrogateUsed: boolean;
}
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
