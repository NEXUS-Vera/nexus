/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export interface AnalysisVerificationAssessment {
  assessment: 'PASS' | 'FAIL' | 'INCONCLUSIVE';
  authority: 'deterministic-code';
  computedMetric: {
    executionRunId?: string | null;
    metricId: string;
    outputId?: string | null;
    rmsNoiseDefinition?: 'demeaned' | 'about-zero';
    unit: string;
    value: number;
  };
  notes?: string;
  schemaVersion: '1.0.0';
  verificationCriterion: {
    linkedRequirementId: string;
    metricId: string;
    operator: '<' | '<=' | '>' | '>=' | '==' | '!=';
    threshold: number;
    unit: string;
  };
}
