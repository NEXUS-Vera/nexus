import type {
  ExecutionRun,
  ProjectBoardProjection,
  ProjectCurrentState,
  ProjectHistory,
} from '@nexus/contracts';
import { ARTIFACT_REGISTRY, WORKFLOW_GROUPS } from '../artifacts/registry';
import { selectArtifactByType } from '../artifacts';
import type { ArtifactRouteKey } from '../artifacts/types';
import { themeColors } from '../lib/theme';
import { StatusBadge } from '../components/statuses/StatusBadge';

type Props = {
  state: ProjectCurrentState;
  board: ProjectBoardProjection | null;
  history: ProjectHistory | null;
  executions?: ExecutionRun[];
  isDark: boolean;
  onNavigate: (key: ArtifactRouteKey) => void;
  onOpenNextAction: () => void;
  onOpenHistory: () => void;
};

function componentPlanCounts(
  state: ProjectCurrentState,
  board: ProjectBoardProjection | null,
): { roles: number; candidates: number; selected?: number } | null {
  const summary = board?.artifactSummaries?.find((s) => s.artifactType === 'component-plan');
  const live = selectArtifactByType(state.artifacts, 'component-plan');
  if (summary?.roleCount != null || summary?.candidateCount != null) {
    return {
      roles: summary.roleCount ?? live?.content.componentRoles.length ?? 0,
      candidates: summary.candidateCount ?? live?.content.candidates.length ?? 0,
      selected: summary.selectedCount,
    };
  }
  if (!live) return null;
  return {
    roles: live.content.componentRoles.length,
    candidates: live.content.candidates.length,
    selected: live.content.selectionDecisions.filter((d) => d.selectionState === 'approved')
      .length,
  };
}

export function ProjectOverview({
  state,
  board,
  history,
  executions = [],
  isDark,
  onNavigate,
  onOpenNextAction,
  onOpenHistory,
}: Props) {
  const t = themeColors(isDark);
  const nextArtifact = selectArtifactByType(state.artifacts, 'next-action');
  const openQuestions = (state.openQuestions ?? []).filter((q) => q.status === 'open');
  const blockers = state.validationIssues.filter((i) => i.blocking && i.resolutionStatus === 'open');
  const recentTurns = [...(history?.turns ?? [])].slice(-5).reverse();

  const openQuestionCount = board?.openQuestionCount ?? openQuestions.length;
  const blockingIssueCount = board?.blockingIssueCount ?? blockers.length;
  const liveArtifactCount = board?.artifactSummaries?.length ?? state.artifacts.length;
  const nextTitle = board?.nextActionSummary?.title ?? nextArtifact?.content.title;
  const nextDescription = nextArtifact?.content.description;
  const nextVersion =
    board?.nextActionSummary?.artifactVersion ?? nextArtifact?.artifactVersion ?? 1;
  const recentChanges = board?.recentChanges ?? [];
  const recentExecutions =
    board?.recentExecutionSummaries ??
    executions.slice(0, 5).map((run) => ({
      executionRunId: run.executionRunId,
      capability: run.capability,
      status: run.status,
      startedAt: run.startedAt,
      completedAt: run.completedAt,
      artifactType: undefined as string | undefined,
    }));
  const evidence = board?.evidenceSummary;
  const planCounts = componentPlanCounts(state, board);

  return (
    <div style={{ flex: 1, overflow: 'auto', padding: 20, background: t.bg }} data-testid="project-overview">
      <div style={{ maxWidth: 960, margin: '0 auto', display: 'grid', gap: 16 }}>
        <header>
          <p style={{ margin: 0, fontSize: 12, color: t.textMuted }}>
            Overview{board ? ' · board projection' : ' · current state'}
          </p>
          <h2 style={{ margin: '4px 0 0', color: t.text }}>
            {board?.projectTitle ?? state.project.title}
          </h2>
          <p style={{ margin: '6px 0 0', color: t.textSec, fontSize: 13 }}>
            Phase {board?.currentPhase ?? state.project.projectPhase} · State v
            {board?.projectStateVersion ?? state.project.currentStateVersion} ·{' '}
            {state.project.domain}
          </p>
        </header>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12 }}>
          <StatBlock label="Live artifacts" value={String(liveArtifactCount)} isDark={isDark} />
          <StatBlock label="Open questions" value={String(openQuestionCount)} isDark={isDark} />
          <StatBlock label="Blocking issues" value={String(blockingIssueCount)} isDark={isDark} />
          <StatBlock
            label="Board slots"
            value={`${WORKFLOW_GROUPS.flatMap((g) => g.artifacts).filter((k) => ARTIFACT_REGISTRY[k].availability !== 'placeholder').length}/8 active`}
            isDark={isDark}
          />
        </div>

        {evidence ? (
          <section style={{ border: `1px solid ${t.border}`, borderRadius: 8, padding: 14, background: t.surface }}>
            <h3 style={{ margin: '0 0 8px', fontSize: 13, color: t.textMuted }}>Evidence</h3>
            <p style={{ margin: 0, fontSize: 13, color: t.text }}>
              {evidence.totalCount} total · {evidence.unverifiedCount} unverified ·{' '}
              {evidence.testedCount} tested · {evidence.contradictedCount} contradicted
            </p>
          </section>
        ) : null}

        {nextTitle ? (
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
              Next Action · v{nextVersion}
              {board?.nextActionSummary?.priority
                ? ` · ${board.nextActionSummary.priority}`
                : ''}
            </div>
            <div style={{ fontSize: 15, fontWeight: 600, color: t.text }}>{nextTitle}</div>
            {nextDescription ? (
              <p style={{ margin: '6px 0 0', fontSize: 13, color: t.textSec }}>{nextDescription}</p>
            ) : null}
          </button>
        ) : null}

        {WORKFLOW_GROUPS.map((group) => (
          <section key={group.label} data-testid={`overview-phase-${group.label}`}>
            <h3 style={{ margin: '0 0 10px', fontSize: 13, color: t.textMuted }}>
              {group.label}
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10 }}>
              {group.artifacts.map((key) => {
                const def = ARTIFACT_REGISTRY[key];
                const summary =
                  def.artifactType == null
                    ? undefined
                    : board?.artifactSummaries?.find((s) => s.artifactType === def.artifactType);
                const live =
                  def.artifactType == null
                    ? undefined
                    : state.artifacts.find((a) => a.artifactType === def.artifactType);
                const lifecycle = summary?.lifecycleStatus ?? live?.lifecycleStatus ?? 'unavailable';
                const version = summary?.artifactVersion ?? live?.artifactVersion;
                const evidenceStatus = summary?.evidenceStatus ?? live?.evidenceStatus;

                let detail =
                  version != null
                    ? `v${version}${evidenceStatus ? ` · ${evidenceStatus}` : ''}`
                    : def.availability === 'proof'
                      ? 'Proof workspace'
                      : 'Placeholder';

                if (key === 'component-plan' && planCounts) {
                  const selected =
                    planCounts.selected != null ? ` · ${planCounts.selected} selected` : '';
                  detail = `${planCounts.roles} roles · ${planCounts.candidates} candidates${selected}${
                    version != null ? ` · v${version}` : ''
                  }`;
                }

                return (
                  <button
                    key={key}
                    type="button"
                    onClick={() => onNavigate(key)}
                    data-testid={`overview-artifact-${key}`}
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
                      <StatusBadge status={lifecycle} />
                    </div>
                    <p style={{ margin: '8px 0 0', fontSize: 12, color: t.textSec }}>{detail}</p>
                  </button>
                );
              })}
            </div>
          </section>
        ))}

        {recentChanges.length ? (
          <section>
            <h3 style={{ margin: '0 0 10px', fontSize: 13, color: t.textMuted }}>Recent changes</h3>
            <ul style={{ margin: 0, paddingLeft: 18, color: t.text, fontSize: 13 }}>
              {recentChanges.slice(0, 8).map((change) => (
                <li key={change.eventId}>
                  <time dateTime={change.occurredAt}>{change.occurredAt}</time> — {change.summary}
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {recentExecutions.length ? (
          <section>
            <h3 style={{ margin: '0 0 10px', fontSize: 13, color: t.textMuted }}>Recent executions</h3>
            <ul style={{ margin: 0, paddingLeft: 18, color: t.text, fontSize: 13 }}>
              {recentExecutions.slice(0, 5).map((run) => (
                <li key={run.executionRunId}>
                  {run.capability} · {run.status}
                  {run.artifactType ? ` · ${run.artifactType}` : ''}
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {!board && blockers.length ? (
          <section>
            <h3 style={{ margin: '0 0 10px', fontSize: 13, color: t.textMuted }}>Blockers</h3>
            <ul style={{ margin: 0, paddingLeft: 18, color: t.text, fontSize: 13 }}>
              {blockers.map((issue) => (
                <li key={issue.issueId}>{issue.message}</li>
              ))}
            </ul>
          </section>
        ) : null}

        {!board && openQuestions.length ? (
          <section>
            <h3 style={{ margin: '0 0 10px', fontSize: 13, color: t.textMuted }}>Open questions</h3>
            <ul style={{ margin: 0, paddingLeft: 18, color: t.text, fontSize: 13 }}>
              {openQuestions.map((q) => (
                <li key={q.questionId}>{q.question}</li>
              ))}
            </ul>
          </section>
        ) : null}

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

function StatBlock({ label, value, isDark }: { label: string; value: string; isDark: boolean }) {
  const t = themeColors(isDark);
  return (
    <div style={{ border: `1px solid ${t.border}`, borderRadius: 8, padding: 14, background: t.surface }}>
      <div style={{ fontSize: 11, color: t.textMuted }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color: t.text, marginTop: 4 }}>{value}</div>
    </div>
  );
}
