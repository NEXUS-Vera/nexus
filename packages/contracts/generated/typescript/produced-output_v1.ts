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

export interface ProducedOutput {
  artifactId: string;
  content:
    | {
        kind: 'inline-structured';
        structuredResult: {
          [k: string]: any;
        };
      }
    | {
        kind: 'storage-reference';
        storageKind: 'postgres-jsonb' | 'object-store' | 'file-store';
        uri: string;
      };
  contentDigest: string;
  createdAt: string;
  entityReferences?: ArtifactEntityReference[];
  evidenceStatus: 'unverified' | 'inferred' | 'partially-grounded' | 'grounded' | 'calculated' | 'tested';
  executionRunId: string;
  mediaType: string;
  name: string;
  outputId: string;
  outputType:
    | 'validation-report'
    | 'log'
    | 'structured-result'
    | 'file-reference'
    | 'plot-reference'
    | 'binary-reference'
    | 'test-report';
  projectId: string;
  provenance?: DerivedFactProvenance;
  providerId?: string;
  schemaVersion: '1.0.0';
  supports: {
    supportKind: 'artifact' | 'requirement' | 'architecture-node' | 'validation-issue' | 'decision';
    targetId: string;
  }[];
  workspaceId: string;
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
export interface DerivedFactProvenance {
  derivedFromIds?: string[];
  notes?: string;
  schemaVersion: '1.0.0';
  sourceReference?: EvidenceReference | string;
  sourceType:
    | 'fixture'
    | 'component-plan'
    | 'user'
    | 'llm-derived'
    | 'manufacturer-datasheet'
    | 'external-provider'
    | 'runtime-output'
    | 'derived'
    | 'unknown';
}
export interface EvidenceReference {
  attribution?: ActorReference;
  evidenceId: string;
  evidenceStrength: 'direct' | 'supporting' | 'inferred' | 'contradicting';
  schemaVersion: '1.0.0';
  sourceId: string;
  sourceLocator?: string;
  sourceType:
    'user-turn' | 'project-policy' | 'document' | 'external-source' | 'calculation' | 'test-result' | 'agent-inference';
  supportedClaim?: string;
}
export interface ActorReference {
  actorId: string;
  actorType: 'user' | 'vera' | 'embedded-systems-agent' | 'shared' | 'system';
  displayName?: string;
  schemaVersion: '1.0.0';
}
