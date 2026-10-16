/* This file is GENERATED from packages/contracts/schemas.
 * Do not edit manually. Re-run: make generate-contract-types
 */
export interface AnalysisInvestigation {
  investigationId: string;
  lifecycleStage: 'INPUTS' | 'TRANSFORM' | 'METRICS' | 'VISUALIZATION' | 'VERIFY';
  /**
   * @maxItems 64
   */
  linkedComponentIds?: string[];
  /**
   * @maxItems 64
   */
  linkedEvidenceIds?: string[];
  /**
   * @maxItems 64
   */
  linkedRequirementIds?: string[];
  /**
   * @maxItems 64
   */
  linkedTestPlanIds?: string[];
  purpose: 'exploration' | 'verification';
  question?: string | null;
  schemaVersion: '1.0.0';
  stageVocabulary?: ('INPUTS' | 'TRANSFORM' | 'METRICS' | 'VISUALIZATION' | 'VERIFY')[];
  title: string;
  verificationCriterion?: {
    [k: string]: any;
  } | null;
}
