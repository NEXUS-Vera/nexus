import type { CSSProperties } from 'react';
import { themeColors } from '../../lib/theme';
import {
  ANALYSIS_STAGE_IDS,
  type AnalysisInvestigation,
} from './modes';

type Props = {
  investigation: AnalysisInvestigation | null;
  isDark: boolean;
  statusLabel?: string;
};

function chip(
  _label: string,
  t: ReturnType<typeof themeColors>,
  muted = false,
): CSSProperties {
  return {
    display: 'inline-flex',
    alignItems: 'center',
    border: `1px solid ${t.border}`,
    borderRadius: 999,
    padding: '2px 8px',
    fontSize: 11,
    color: muted ? t.textMuted : t.text,
    background: t.surface2,
  };
}

export function AnalysisInvestigationHeader({
  investigation,
  isDark,
  statusLabel,
}: Props) {
  const t = themeColors(isDark);
  const title = investigation?.title ?? 'Untitled analysis';
  const purpose = investigation?.purpose ?? 'exploration';
  const question = investigation?.question?.trim() || null;
  const reqs = investigation?.linkedRequirementIds ?? [];
  const comps = investigation?.linkedComponentIds ?? [];
  const linked =
    [...reqs, ...comps].length > 0
      ? [...reqs, ...comps].join(' · ')
      : 'No linked requirement';
  const stages = investigation?.stageVocabulary?.length
    ? investigation.stageVocabulary
    : [...ANALYSIS_STAGE_IDS];
  const current = investigation?.lifecycleStage;

  return (
    <header
      data-testid="analysis-investigation-header"
      style={{
        padding: '14px 16px 10px',
        borderBottom: `1px solid ${t.border}`,
        background: t.surface,
      }}
    >
      <div style={{ display: 'flex', gap: 10, alignItems: 'baseline', flexWrap: 'wrap' }}>
        <h2
          data-testid="analysis-investigation-title"
          style={{ margin: 0, fontSize: 18, fontWeight: 700, color: t.text }}
        >
          {title}
        </h2>
        <span
          data-testid="analysis-investigation-purpose"
          style={chip(purpose, t)}
        >
          {purpose === 'verification' ? 'Verification' : 'Exploration'}
        </span>
        {statusLabel ? (
          <span data-testid="analysis-investigation-status" style={chip(statusLabel, t)}>
            {statusLabel}
          </span>
        ) : null}
      </div>
      {question ? (
        <p
          data-testid="analysis-investigation-question"
          style={{ margin: '8px 0 0', fontSize: 13, color: t.textSec, lineHeight: 1.45 }}
        >
          {question}
        </p>
      ) : null}
      <div
        data-testid="analysis-investigation-links"
        style={{ marginTop: 8, fontSize: 12, color: t.textMuted }}
      >
        Linked: <span style={{ color: t.text }}>{linked}</span>
      </div>
      <div
        data-testid="analysis-stage-rail"
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 6,
          marginTop: 10,
        }}
        aria-label="Analysis stages"
      >
        {stages.map((stage) => {
          const active = stage === current;
          return (
            <span
              key={stage}
              data-testid={`analysis-stage-${stage}`}
              style={{
                ...chip(stage, t, !active),
                fontWeight: active ? 700 : 500,
                borderColor: active ? t.cobalt : t.border,
                color: active ? t.cobalt : t.textMuted,
              }}
            >
              {stage}
            </span>
          );
        })}
      </div>
    </header>
  );
}
