import type { ProjectCurrentState, ProjectHistory } from '@nexus/contracts';
import { ARTIFACT_ORDER, ARTIFACT_REGISTRY } from '../artifacts/registry';
import { selectArtifactByType } from '../artifacts';
import type { ArtifactRouteKey } from '../artifacts/types';
import { themeColors } from '../lib/theme';
import { StatusBadge } from '../components/statuses/StatusBadge';

type Props = {
  state: ProjectCurrentState;
  history: ProjectHistory | null;
  isDark: boolean;
  onNavigate: (key: ArtifactRouteKey) => void;
  onOpenNextAction: () => void;
  onOpenHistory: () => void;
};

export function ProjectOverview({
  state,
  history,
  isDark,
  onNavigate,
  onOpenNextAction,
  onOpenHistory,
}: Props) {
  const t = themeColors(isDark);
  const next = selectArtifactByType(state.artifacts, 'next-action');
  const openQuestions = (state.openQuestions ?? []).filter((q) => q.status === 'open');
  const blockers = state.validationIssues.filter((i) => i.blocking && i.resolutionStatus === 'open');
  const recentTurns = [...(history?.turns ?? [])].slice(-5).reverse();

  return (
    <div style={{ flex: 1, overflow: 'auto', padding: 20, background: t.bg }} data-testid="project-overview">
      <div style={{ maxWidth: 960, margin: '0 auto', display: 'grid', gap: 16 }}>
        <header>
          <p style={{ margin: 0, fontSize: 12, color: t.textMuted }}>Overview</p>
          <h2 style={{ margin: '4px 0 0', color: t.text }}>{state.project.title}</h2>
          <p style={{ margin: '6px 0 0', color: t.textSec, fontSize: 13 }}>
            Phase {state.project.projectPhase} · State v{state.project.currentStateVersion} ·{' '}
            {state.project.domain}
          </p>
        </header>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12 }}>
          <StatCard label="Live artifacts" value={String(state.artifacts.length)} isDark={isDark} />
          <StatCard label="Open questions" value={String(openQuestions.length)} isDark={isDark} />
          <StatCard label="Blocking issues" value={String(blockers.length)} isDark={isDark} />
          <StatCard
            label="Board slots"
            value={`${ARTIFACT_ORDER.filter((k) => ARTIFACT_REGISTRY[k].availability === 'live').length}/8 live`}
            isDark={isDark}
          />
        </div>

        {next ? (
          <button
            type="button"
            onClick={onOpenNextAction}
            style={{
              textAlign: 'left',
              border: `1px solid ${t.cobalt}33`,
              borderLeft: `4px solid ${t.cobalt}`,
              borderRadius: 8,
              padding: 16,
              background: t.cobaltTint,
              cursor: 'pointer',
            }}
          >
            <div style={{ fontSize: 11, fontWeight: 600, color: t.cobalt, marginBottom: 4 }}>
              Next Action · v{next.artifactVersion}
            </div>
            <div style={{ fontSize: 15, fontWeight: 600, color: t.text }}>{next.content.title}</div>
            <p style={{ margin: '6px 0 0', fontSize: 13, color: t.textSec }}>{next.content.description}</p>
          </button>
        ) : null}

        <section>
          <h3 style={{ margin: '0 0 10px', fontSize: 13, color: t.textMuted }}>Artifacts</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10 }}>
            {ARTIFACT_ORDER.map((key) => {
              const def = ARTIFACT_REGISTRY[key];
              const live =
                def.artifactType == null
                  ? undefined
                  : selectArtifactByType(
                      state.artifacts,
                      def.artifactType as
                        | 'project-brief'
                        | 'requirement-set'
                        | 'functional-architecture'
                        | 'next-action',
                    );
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => onNavigate(key)}
                  style={{
                    textAlign: 'left',
                    border: `1px solid ${t.border}`,
                    borderRadius: 8,
                    padding: 12,
                    background: t.surface,
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                    <strong style={{ fontSize: 13, color: t.text }}>{def.label}</strong>
                    <StatusBadge status={live?.lifecycleStatus ?? 'unavailable'} />
                  </div>
                  <p style={{ margin: '8px 0 0', fontSize: 12, color: t.textSec }}>
                    {live ? `v${live.artifactVersion} · ${live.evidenceStatus}` : 'Placeholder'}
                  </p>
                </button>
              );
            })}
          </div>
        </section>

        <section>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ margin: 0, fontSize: 13, color: t.textMuted }}>Recent activity</h3>
            <button
              type="button"
              onClick={onOpenHistory}
              style={{
                border: `1px solid ${t.border}`,
                background: t.surface,
                borderRadius: 6,
                padding: '4px 8px',
                fontSize: 12,
                cursor: 'pointer',
                color: t.textSec,
              }}
            >
              Open history
            </button>
          </div>
          {recentTurns.length ? (
            <ul style={{ margin: '10px 0 0', paddingLeft: 18, color: t.text, fontSize: 13 }}>
              {recentTurns.map((turn) => (
                <li key={turn.turnId}>
                  <time dateTime={turn.timestamp}>{turn.timestamp}</time> — {turn.rawUserMessage}
                </li>
              ))}
            </ul>
          ) : (
            <p style={{ margin: '10px 0 0', color: t.textSec, fontSize: 13 }}>No turns yet.</p>
          )}
        </section>
      </div>
    </div>
  );
}

function StatCard({ label, value, isDark }: { label: string; value: string; isDark: boolean }) {
  const t = themeColors(isDark);
  return (
    <div style={{ border: `1px solid ${t.border}`, borderRadius: 8, padding: 14, background: t.surface }}>
      <div style={{ fontSize: 11, color: t.textMuted }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color: t.text, marginTop: 4 }}>{value}</div>
    </div>
  );
}
