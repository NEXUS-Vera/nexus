/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export interface RiskRegisterContent {
  provenance?: {
    generatedBy?: 'fixture' | 'llm' | 'user' | 'derived';
    notes?: string;
  };
  riskRegisterId: string;
  /**
   * @minItems 1
   */
  risks: [
    {
      category:
        | 'electrical'
        | 'firmware'
        | 'communication'
        | 'power'
        | 'thermal'
        | 'mechanical'
        | 'integration'
        | 'performance'
        | 'data-quality'
        | 'safety';
      description: string;
      displayId: string;
      evidenceReferences?: EvidenceReference[];
      likelihood: 'rare' | 'unlikely' | 'possible' | 'likely';
      linkedArchitectureRefs?: string[];
      linkedComponentIds?: string[];
      linkedRequirementIds?: string[];
      linkedTestIds?: string[];
      mitigation: string;
      priorityScore: number;
      residualRisk?: string;
      riskId: string;
      severity: 'low' | 'medium' | 'high' | 'critical';
      status: 'open' | 'mitigating' | 'mitigated' | 'accepted' | 'monitoring';
      title: string;
      verificationTestIds?: string[];
    },
    ...{
      category:
        | 'electrical'
        | 'firmware'
        | 'communication'
        | 'power'
        | 'thermal'
        | 'mechanical'
        | 'integration'
        | 'performance'
        | 'data-quality'
        | 'safety';
      description: string;
      displayId: string;
      evidenceReferences?: EvidenceReference[];
      likelihood: 'rare' | 'unlikely' | 'possible' | 'likely';
      linkedArchitectureRefs?: string[];
      linkedComponentIds?: string[];
      linkedRequirementIds?: string[];
      linkedTestIds?: string[];
      mitigation: string;
      priorityScore: number;
      residualRisk?: string;
      riskId: string;
      severity: 'low' | 'medium' | 'high' | 'critical';
      status: 'open' | 'mitigating' | 'mitigated' | 'accepted' | 'monitoring';
      title: string;
      verificationTestIds?: string[];
    }[]
  ];
  schemaVersion: '1.0.0';
  summary: {
    highOrCritical: number;
    mitigated: number;
    openRisks: number;
    totalRisks: number;
    unverifiedMitigations: number;
  };
  title?: string;
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
