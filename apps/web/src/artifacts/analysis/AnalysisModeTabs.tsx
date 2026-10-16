import { themeColors } from '../../lib/theme';
import type { AnalysisWorkspaceMode } from './modes';
import { ANALYSIS_WORKSPACE_MODES } from './modes';

type Props = {
  mode: AnalysisWorkspaceMode;
  isDark: boolean;
  onChange: (mode: AnalysisWorkspaceMode) => void;
};

const LABELS: Record<AnalysisWorkspaceMode, string> = {
  results: 'Results',
  code: 'Code',
  data: 'Data',
  history: 'History',
};

export function AnalysisModeTabs({ mode, isDark, onChange }: Props) {
  const t = themeColors(isDark);
  return (
    <div
      role="tablist"
      aria-label="Analysis workspace mode"
      data-testid="analysis-mode-tabs"
      style={{ display: 'flex', gap: 6, alignItems: 'center' }}
    >
      {ANALYSIS_WORKSPACE_MODES.map((id) => {
        const active = mode === id;
        return (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={active}
            data-testid={`analysis-mode-${id}`}
            onClick={() => onChange(id)}
            style={{
              border: `1px solid ${active ? t.cobalt : t.border}`,
              background: active ? t.cobaltSelected : t.surface,
              color: active ? t.cobalt : t.text,
              borderRadius: 7,
              padding: '5px 10px',
              fontSize: 12,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            {LABELS[id]}
          </button>
        );
      })}
    </div>
  );
}
