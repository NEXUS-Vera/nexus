/**
 * Risk Register workspace — priority/status first (Phase 17E).
 */
import { useMemo, useState } from 'react';
import type { Artifact } from '@nexus/contracts';
import { themeColors } from '../../lib/theme';

type RiskArtifact = Extract<Artifact, { artifactType: 'risk-register' }>;

type Props = {
  artifact: RiskArtifact;
  isDark: boolean;
  selectedRiskId: string | null;
  onSelectRisk: (id: string) => void;
};

export function RiskRegisterWorkspace({
  artifact,
  isDark,
  selectedRiskId,
  onSelectRisk,
}: Props) {
  const t = themeColors(isDark);
  const content = artifact.content;
  const risks = content.risks ?? [];
  const summary = content.summary;
  const [category, setCategory] = useState<string>('all');
  const [status, setStatus] = useState<string>('all');

  const filtered = useMemo(() => {
    return [...risks]
      .filter((r) => (category === 'all' ? true : r.category === category))
      .filter((r) => (status === 'all' ? true : r.status === status))
      .sort((a, b) => b.priorityScore - a.priorityScore);
  }, [risks, category, status]);

  const selected =
    filtered.find((r) => r.riskId === selectedRiskId || r.displayId === selectedRiskId) ??
    filtered[0] ??
    risks[0];

  const categories = [...new Set(risks.map((r) => r.category))];
  const statuses = [...new Set(risks.map((r) => r.status))];

  return (
    <div data-testid="workspace-risk-register" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div
        style={{
          padding: '10px 16px',
          borderBottom: `1px solid ${t.border}`,
          background: t.surface,
          display: 'flex',
          gap: 12,
          flexWrap: 'wrap',
          fontSize: 12,
          color: t.textSec,
        }}
      >
        <strong style={{ color: t.text }}>{content.title ?? 'Risk Register'}</strong>
        <span data-testid="risk-summary-open">Open: {summary.openRisks}</span>
        <span data-testid="risk-summary-high">High/Critical: {summary.highOrCritical}</span>
        <span>Mitigated: {summary.mitigated}</span>
        <span>Unverified mitigations: {summary.unverifiedMitigations}</span>
      </div>

      <div style={{ display: 'flex', gap: 8, padding: '8px 16px', borderBottom: `1px solid ${t.border}` }}>
        <label style={{ fontSize: 12, color: t.textMuted }}>
          Category{' '}
          <select data-testid="risk-filter-category" value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="all">all</option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
        <label style={{ fontSize: 12, color: t.textMuted }}>
          Status{' '}
          <select data-testid="risk-filter-status" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="all">all</option>
            {statuses.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: 'minmax(0,1.1fr) minmax(0,1fr)', overflow: 'hidden' }}>
        <ul style={{ listStyle: 'none', margin: 0, padding: 8, overflow: 'auto', borderRight: `1px solid ${t.border}`, background: t.bg }}>
          {filtered.map((risk) => (
            <li key={risk.riskId}>
              <button
                type="button"
                data-testid={`risk-item-${risk.displayId}`}
                onClick={() => onSelectRisk(risk.displayId)}
                style={{
                  width: '100%',
                  textAlign: 'left',
                  border: 'none',
                  background: selected?.riskId === risk.riskId ? t.cobaltSelected : 'transparent',
                  padding: '10px 12px',
                  cursor: 'pointer',
                  color: t.text,
                  borderRadius: 6,
                }}
              >
                <div style={{ fontSize: 11, color: t.textMuted, textTransform: 'uppercase' }}>
                  {risk.severity} · priority {risk.priorityScore}
                </div>
                <div style={{ fontWeight: 650 }}>
                  {risk.displayId} — {risk.title}
                </div>
                <div style={{ fontSize: 11, color: t.textSec }}>
                  {(risk.linkedRequirementIds ?? []).join(' · ') || 'No linked requirement'} · {risk.status}
                </div>
              </button>
            </li>
          ))}
        </ul>

        <section style={{ overflow: 'auto', padding: 16 }} data-testid="risk-detail">
          {!selected ? (
            <div style={{ color: t.textMuted }}>Select a risk.</div>
          ) : (
            <div>
              <h3 style={{ margin: '0 0 8px', color: t.text }}>
                {selected.displayId} — {selected.title}
              </h3>
              <p style={{ marginTop: 0, color: t.textSec, fontSize: 13 }}>{selected.description}</p>
              <Meta label="Category" value={selected.category} t={t} />
              <Meta label="Likelihood" value={selected.likelihood} t={t} />
              <Meta label="Severity" value={selected.severity} t={t} />
              <Meta label="Priority score" value={String(selected.priorityScore)} t={t} />
              <Meta label="Status" value={selected.status} t={t} />
              <Meta
                label="Linked"
                value={[...(selected.linkedRequirementIds ?? []), ...(selected.linkedComponentIds ?? [])].join(' · ') || '—'}
                t={t}
              />
              <div style={{ marginTop: 12, fontSize: 12, color: t.text }}>
                <div style={{ color: t.textMuted, fontSize: 11 }}>Mitigation</div>
                {selected.mitigation}
              </div>
              <div data-testid="risk-verification-tests" style={{ marginTop: 12, fontSize: 12, color: t.textSec }}>
                Verification tests: {(selected.verificationTestIds ?? []).join(', ') || '—'}
              </div>
              <div data-testid="risk-mitigation-verification" style={{ marginTop: 8, fontSize: 11, color: t.textMuted }}>
                Mitigation verification:{' '}
                {String(
                  (selected as { mitigationVerificationStatus?: string }).mitigationVerificationStatus ??
                    'proposed',
                )}
                {(selected as { mitigationVerifiedByTests?: string[] }).mitigationVerifiedByTests?.length
                  ? ` by ${(selected as { mitigationVerifiedByTests?: string[] }).mitigationVerifiedByTests!.join(', ')}`
                  : ''}
                {selected.status === 'monitoring'
                  ? ' — lifecycle remains monitoring without physical hardware evidence'
                  : ' — lifecycle not auto-closed unless mitigationVerificationSufficient'}
              </div>
              {selected.residualRisk ? (
                <div data-testid="risk-residual" style={{ marginTop: 12, fontSize: 12, color: t.textMuted }}>
                  Residual: {selected.residualRisk}
                </div>
              ) : null}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function Meta({
  label,
  value,
  t,
}: {
  label: string;
  value: string;
  t: ReturnType<typeof themeColors>;
}) {
  return (
    <div style={{ marginTop: 6, fontSize: 12, color: t.textSec }}>
      {label}: <span style={{ color: t.text }}>{value}</span>
    </div>
  );
}
