/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export interface TestPlanContent {
  coverageSummary: {
    blockedRequirements: number;
    coveredRequirements: number;
    failedRequirements: number;
    totalRequirements: number;
    uncoveredRequirements: number;
    unverifiedRequirements: number;
    verifiedRequirements: number;
  };
  provenance?: {
    generatedBy?: 'fixture' | 'llm' | 'user' | 'derived';
    notes?: string;
  };
  schemaVersion: '1.0.0';
  summary?: string;
  /**
   * @minItems 1
   */
  testCases: [
    {
      actualResult?: string;
      assessment?: 'PASS' | 'FAIL' | 'INCONCLUSIVE';
      assessmentAuthority?: 'deterministic-code' | 'manual' | 'none';
      criterion?: {
        criterionType: 'numeric-comparison' | 'exact-match' | 'contains' | 'existence' | 'structural-mapping' | 'range';
        expectedMapping?: string;
        expectedValue?: any;
        marker?: string;
        maxValue?: number;
        metricId?: string;
        minValue?: number;
        operator?: '<' | '<=' | '>' | '>=' | '==' | '!=';
        outputName?: string;
        signal?: string;
        tolerance?: number;
        toleranceUnit?: 'absolute' | 'percent';
        unit?: string;
      };
      description?: string;
      displayId: string;
      evidenceReferences?: EvidenceReference[];
      executionRunId?: string;
      expectedResult: string;
      finding?: string;
      inputs?: string[];
      linkedArchitectureRefs?: string[];
      linkedComponentIds?: string[];
      linkedRequirementIds: string[];
      preconditions?: string[];
      procedure?: string[];
      producedOutputIds?: string[];
      status: 'planned' | 'ready' | 'running' | 'passed' | 'failed' | 'blocked' | 'inconclusive';
      testId: string;
      title: string;
      verificationMethod: 'inspection' | 'simulation' | 'firmware-test' | 'analysis' | 'execution-output' | 'manual';
    },
    ...{
      actualResult?: string;
      assessment?: 'PASS' | 'FAIL' | 'INCONCLUSIVE';
      assessmentAuthority?: 'deterministic-code' | 'manual' | 'none';
      criterion?: {
        criterionType: 'numeric-comparison' | 'exact-match' | 'contains' | 'existence' | 'structural-mapping' | 'range';
        expectedMapping?: string;
        expectedValue?: any;
        marker?: string;
        maxValue?: number;
        metricId?: string;
        minValue?: number;
        operator?: '<' | '<=' | '>' | '>=' | '==' | '!=';
        outputName?: string;
        signal?: string;
        tolerance?: number;
        toleranceUnit?: 'absolute' | 'percent';
        unit?: string;
      };
      description?: string;
      displayId: string;
      evidenceReferences?: EvidenceReference[];
      executionRunId?: string;
      expectedResult: string;
      finding?: string;
      inputs?: string[];
      linkedArchitectureRefs?: string[];
      linkedComponentIds?: string[];
      linkedRequirementIds: string[];
      preconditions?: string[];
      procedure?: string[];
      producedOutputIds?: string[];
      status: 'planned' | 'ready' | 'running' | 'passed' | 'failed' | 'blocked' | 'inconclusive';
      testId: string;
      title: string;
      verificationMethod: 'inspection' | 'simulation' | 'firmware-test' | 'analysis' | 'execution-output' | 'manual';
    }[]
  ];
  testPlanId: string;
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
