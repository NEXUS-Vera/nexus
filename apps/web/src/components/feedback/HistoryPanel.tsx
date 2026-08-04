import type { ProjectHistory } from '@nexus/contracts';
import { themeColors } from '../../lib/theme';
import type { InspectorSelection } from '../../lib/inspector-selection';

type HistoryPanelProps = {
  history: ProjectHistory;
  isDark: boolean;
  onSelectRevision: (selection: Extract<InspectorSelection, { kind: 'artifact-revision' }>) => void;
  onClose: () => void;
};

export function HistoryPanel({ history, isDark, onSelectRevision, onClose }: HistoryPanelProps) {
  const t = themeColors(isDark);
  return (
    <section
      aria-label="Project history"
      data-testid="history-panel"
      style={{
        borderTop: `1px solid ${t.border}`,
        background: t.surface,
        maxHeight: 220,
        overflow: 'auto',
        padding: 12,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ margin: 0, fontSize: 13, color: t.text }}>History</h2>
        <button
          type="button"
          onClick={onClose}
          style={{
            border: `1px solid ${t.border}`,
            background: t.surface2,
            borderRadius: 6,
            padding: '4px 8px',
            fontSize: 12,
            cursor: 'pointer',
            color: t.textSec,
          }}
        >
          Hide history
        </button>
      </div>

      <h3 style={{ margin: '12px 0 6px', fontSize: 12, color: t.textMuted }}>Turns</h3>
      <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: t.text }}>
        {history.turns.map((turn) => (
          <li key={turn.turnId}>
            <time dateTime={turn.timestamp}>{turn.timestamp}</time> — {turn.rawUserMessage}
          </li>
        ))}
      </ul>

      <h3 style={{ margin: '12px 0 6px', fontSize: 12, color: t.textMuted }}>Vera responses</h3>
      <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: t.text }}>
        {history.veraResponses.map((response) => (
          <li key={`${response.turnId}-${response.timestamp}`}>
            {response.userFacingMessage.slice(0, 120)}
            {response.userFacingMessage.length > 120 ? '…' : ''}
          </li>
        ))}
      </ul>

      <h3 style={{ margin: '12px 0 6px', fontSize: 12, color: t.textMuted }}>Workflow runs</h3>
      <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: t.text }}>
        {history.workflowRuns.map((run) => (
          <li key={run.workflowRunId}>
            {run.workflowType} · {run.status}
          </li>
        ))}
      </ul>

      <h3 style={{ margin: '12px 0 6px', fontSize: 12, color: t.textMuted }}>Artifact revisions</h3>
      <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: t.text }}>
        {history.artifactRevisions.map((rev) => (
          <li key={`${rev.artifactId}-${rev.artifactVersion}`}>
            {rev.artifactType} v{rev.artifactVersion} ({rev.lifecycleStatus}){' '}
            <button
              type="button"
              onClick={() =>
                onSelectRevision({
                  kind: 'artifact-revision',
                  artifactType: rev.artifactType,
                  version: rev.artifactVersion,
                })
              }
              style={{
                border: `1px solid ${t.border}`,
                background: t.surface2,
                borderRadius: 4,
                padding: '1px 6px',
                fontSize: 11,
                cursor: 'pointer',
                color: t.cobalt,
              }}
            >
              Inspect
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
