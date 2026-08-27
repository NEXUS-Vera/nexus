/** Analysis workspace top-level modes (Results-first productization). */

export type AnalysisWorkspaceMode = 'results' | 'code' | 'data' | 'history';

export const ANALYSIS_WORKSPACE_MODES: readonly AnalysisWorkspaceMode[] = [
  'results',
  'code',
  'data',
  'history',
] as const;

export const ANALYSIS_STAGE_IDS = [
  'INPUTS',
  'TRANSFORM',
  'METRICS',
  'VISUALIZATION',
  'VERIFY',
] as const;

export type AnalysisStageId = (typeof ANALYSIS_STAGE_IDS)[number];

export type AnalysisInvestigation = {
  schemaVersion?: string;
  investigationId?: string;
  title: string;
  purpose: 'exploration' | 'verification';
  question?: string | null;
  linkedRequirementIds: string[];
  linkedComponentIds: string[];
  linkedTestPlanIds: string[];
  linkedEvidenceIds: string[];
  lifecycleStage?: AnalysisStageId | string;
  verificationCriterion?: {
    metricId?: string;
    operator?: string;
    threshold?: number;
    unit?: string;
    linkedRequirementId?: string;
  } | null;
  stageVocabulary?: string[];
};

export const INVESTIGATION_PATH = 'nexus/investigation.json';

export function parseInvestigation(raw: unknown): AnalysisInvestigation | null {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null;
  const obj = raw as Record<string, unknown>;
  const purpose = obj.purpose === 'verification' ? 'verification' : 'exploration';
  const title =
    typeof obj.title === 'string' && obj.title.trim()
      ? obj.title.trim()
      : purpose === 'verification'
        ? 'Verification analysis'
        : 'Untitled analysis';
  const asIds = (value: unknown) =>
    Array.isArray(value)
      ? value.filter((item): item is string => typeof item === 'string' && item.length > 0)
      : [];
  return {
    schemaVersion: typeof obj.schemaVersion === 'string' ? obj.schemaVersion : undefined,
    investigationId:
      typeof obj.investigationId === 'string' ? obj.investigationId : undefined,
    title,
    purpose,
    question: typeof obj.question === 'string' ? obj.question : null,
    linkedRequirementIds: asIds(obj.linkedRequirementIds),
    linkedComponentIds: asIds(obj.linkedComponentIds),
    linkedTestPlanIds: asIds(obj.linkedTestPlanIds),
    linkedEvidenceIds: asIds(obj.linkedEvidenceIds),
    lifecycleStage:
      typeof obj.lifecycleStage === 'string' ? obj.lifecycleStage : undefined,
    verificationCriterion:
      obj.verificationCriterion && typeof obj.verificationCriterion === 'object'
        ? (obj.verificationCriterion as AnalysisInvestigation['verificationCriterion'])
        : null,
    stageVocabulary: Array.isArray(obj.stageVocabulary)
      ? obj.stageVocabulary.filter((s): s is string => typeof s === 'string')
      : [...ANALYSIS_STAGE_IDS],
  };
}

export function formatEngineeringNumber(value: number, digits = 4): string {
  if (!Number.isFinite(value)) return '—';
  const abs = Math.abs(value);
  if (abs !== 0 && (abs < 1e-3 || abs >= 1e4)) return value.toExponential(2);
  return value.toFixed(digits).replace(/\.?0+$/, (m) => (m.includes('.') ? m.replace(/0+$/, '').replace(/\.$/, '') : m));
}
