import type { Artifact } from '@nexus/contracts';
import { WorkspaceHeader } from '../../components/layout/WorkspaceHeader';
import { StatusBadge } from '../../components/statuses/StatusBadge';
import { themeColors } from '../../lib/theme';

type Props = {
  artifact: Extract<Artifact, { artifactType: 'requirement-set' }>;
  changeIndicator?: string;
  isDark: boolean;
  selectedRequirementId: string | null;
  onSelectRequirement: (id: string) => void;
  architectureNodeIdsByRequirement?: Record<string, string[]>;
};

export function RequirementsWorkspace({
  artifact,
  changeIndicator,
  isDark,
  selectedRequirementId,
  onSelectRequirement,
  architectureNodeIdsByRequirement = {},
}: Props) {
  const t = themeColors(isDark);
  const { requirements, requirementSummary, openQuestionIds } = artifact.content;
  const byStatus = requirements.reduce<Record<string, number>>((acc, req) => {
    acc[req.confirmationStatus] = (acc[req.confirmationStatus] ?? 0) + 1;
    return acc;
  }, {});
  const selected =
    requirements.find(
      (r) => r.requirementId === selectedRequirementId || r.displayId === selectedRequirementId,
    ) ?? requirements[0];

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }} data-testid="workspace-requirements">
      <WorkspaceHeader
        title="Requirements"
        subtitle={`${requirements.length} requirements · ${requirementSummary}`}
        version={artifact.artifactVersion}
        lifecycleStatus={artifact.lifecycleStatus}
        evidenceStatus={artifact.evidenceStatus}
        approvalStatus={artifact.approvalStatus}
        changeIndicator={changeIndicator}
        isDark={isDark}
      />
      <div
        style={{
          display: 'flex',
          gap: 8,
          padding: '10px 16px',
          borderBottom: `1px solid ${t.border}`,
          background: t.surface,
          flexWrap: 'wrap',
          fontSize: 12,
          color: t.textSec,
        }}
      >
        <span>Total: {requirements.length}</span>
        <span>Confirmed: {byStatus.confirmed ?? 0}</span>
        <span>Proposed: {byStatus.proposed ?? 0}</span>
        <span>Needs confirmation: {byStatus['needs-confirmation'] ?? 0}</span>
        <span>Linked questions: {openQuestionIds?.length ?? 0}</span>
      </div>
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: 'minmax(0,1.2fr) minmax(0,1fr)', overflow: 'hidden' }}>
        <ul
          style={{
            listStyle: 'none',
            margin: 0,
            padding: 12,
            overflow: 'auto',
            background: t.bg,
            borderRight: `1px solid ${t.border}`,
            display: 'grid',
            gap: 8,
            alignContent: 'start',
          }}
        >
          {requirements.map((req) => {
            const active = selected?.requirementId === req.requirementId;
            return (
              <li key={req.requirementId}>
                <button
                  type="button"
                  onClick={() => onSelectRequirement(req.requirementId)}
                  style={{
                    width: '100%',
                    textAlign: 'left',
                    border: `1px solid ${active ? t.cobalt : t.border}`,
                    borderRadius: 8,
                    padding: 12,
                    background: active ? t.cobaltSelected : t.surface,
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}>
                    <strong style={{ fontSize: 12, color: t.cobalt }}>{req.displayId}</strong>
                    <StatusBadge status={req.confirmationStatus} />
                    <span style={{ marginLeft: 'auto', fontSize: 11, color: t.textMuted }}>
                      {req.priority}
                    </span>
                  </div>
                  <p style={{ margin: 0, fontSize: 13, color: t.text }}>{req.statement}</p>
                </button>
              </li>
            );
          })}
        </ul>
        <div style={{ overflow: 'auto', padding: 16, background: t.surface }}>
          {selected ? (
            <div style={{ display: 'grid', gap: 12 }}>
              <h3 style={{ margin: 0, color: t.text }}>
                {selected.displayId}
              </h3>
              <p style={{ margin: 0, color: t.text, fontSize: 14 }}>{selected.statement}</p>
              <p style={{ margin: 0, color: t.textSec, fontSize: 12 }}>
                {selected.category} · {selected.priority} · confidence {selected.confidence} ·{' '}
                {selected.sourceType}
              </p>
              <p style={{ margin: 0, color: t.textSec, fontSize: 12 }}>
                Verification: {selected.verificationMethod}
              </p>
              {selected.targetQuantity ? (
                <p style={{ margin: 0, color: t.textSec, fontSize: 12 }}>
                  Target: {selected.targetQuantity.value} {selected.targetQuantity.unit}
                </p>
              ) : null}
              {selected.acceptanceCriteria?.length ? (
                <div>
                  <h4 style={{ margin: '0 0 6px', fontSize: 12, color: t.textMuted }}>
                    Acceptance criteria
                  </h4>
                  <ul style={{ margin: 0, paddingLeft: 18, color: t.text, fontSize: 13 }}>
                    {selected.acceptanceCriteria.map((c) => (
                      <li key={c}>{c}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              <div>
                <h4 style={{ margin: '0 0 6px', fontSize: 12, color: t.textMuted }}>
                  Live architecture trace
                </h4>
                {(architectureNodeIdsByRequirement[selected.requirementId] ?? []).length ? (
                  <p style={{ margin: 0, fontSize: 12, color: t.text }}>
                    Covered by nodes:{' '}
                    {(architectureNodeIdsByRequirement[selected.requirementId] ?? []).join(', ')}
                  </p>
                ) : (
                  <p style={{ margin: 0, fontSize: 12, color: t.textSec }}>
                    No architecture node currently lists this requirement. Firmware/test traces are
                    hidden until those artifacts exist.
                  </p>
                )}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
