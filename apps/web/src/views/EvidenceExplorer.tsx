/**
 * Evidence State explorer — Requirement → Test → Evidence chain (Phase 17F).
 * Does not duplicate a second evidence database; reads verification projection.
 */
import { useEffect, useState } from 'react';
import { themeColors } from '../lib/theme';
import { getVerificationEvidenceChain } from '../api/client';

type ChainRow = {
  requirementId: string;
  verificationState?: string;
  testId: string;
  testStatus?: string;
  applicability?: {
    state: string;
    reasons: Array<{
      reason: string;
      triggerArtifactType: string;
      fromVersion: number;
      toVersion: number;
    }>;
  };
  assessment?: string;
  assessmentAuthority?: string;
  actualResult?: string;
  criterion?: Record<string, unknown>;
  evidenceReferences?: Array<{ evidenceId?: string; sourceId?: string; sourceLocator?: string }>;
  executionRunId?: string;
  finding?: string;
};

type Props = {
  projectId: string;
  isDark: boolean;
  onOpenTestPlan?: (testId: string) => void;
  onOpenAnalysis?: () => void;
  onInspectRun?: (runId: string) => void;
};

export function EvidenceExplorer({ projectId, isDark, onOpenTestPlan, onOpenAnalysis, onInspectRun }: Props) {
  const t = themeColors(isDark);
  const [rows, setRows] = useState<ChainRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getVerificationEvidenceChain(projectId)
      .then((payload) => {
        if (cancelled) return;
        setRows((payload.chains as ChainRow[]) ?? []);
        setError(null);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Failed to load evidence chain');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  return (
    <div data-testid="evidence-explorer" style={{ flex: 1, overflow: 'auto', padding: 16, background: t.bg }}>
      <h2 style={{ margin: '0 0 8px', fontSize: 16, color: t.text }}>Evidence State</h2>
      <p style={{ margin: '0 0 16px', fontSize: 12, color: t.textMuted }}>
        Requirement → TestCase → EvidenceReference. Deterministic assessments are authoritative;
        generated explanations are secondary.
      </p>
      {loading ? <div style={{ color: t.textMuted }}>Loading…</div> : null}
      {error ? <div style={{ color: '#b91c1c' }}>{error}</div> : null}
      <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
        {rows.map((row) => (
          <li
            key={`${row.requirementId}-${row.testId}`}
            data-testid={`evidence-chain-${row.requirementId}-${row.testId}`}
            style={{
              border: `1px solid ${t.border}`,
              borderRadius: 8,
              padding: 12,
              marginBottom: 10,
              background: t.surface,
            }}
          >
            <div style={{ fontWeight: 650, color: t.text }}>
              {row.requirementId} · {row.testId} · {row.verificationState ?? '—'}
            </div>
            <div style={{ fontSize: 12, color: t.textSec, marginTop: 6 }}>
              Assessment: {row.assessment ?? '—'} · Authority: {row.assessmentAuthority ?? 'none'}
            </div>
            {row.applicability && row.applicability.state !== 'CURRENT' ? (
              <div style={{ fontSize: 12, color: t.text, marginTop: 6 }}>
                Applicability: {row.applicability.state}
                {row.applicability.reasons.map((reason, index) => (
                  <div key={index}>
                    {reason.reason} · {reason.triggerArtifactType} v{reason.fromVersion} → v{reason.toVersion}
                  </div>
                ))}
              </div>
            ) : null}
            {row.actualResult ? (
              <div style={{ fontSize: 12, color: t.text, marginTop: 4 }}>Actual: {row.actualResult}</div>
            ) : null}
            {row.criterion ? (
              <div style={{ fontSize: 11, color: t.textMuted, marginTop: 4 }}>
                Criterion: <code>{JSON.stringify(row.criterion)}</code>
              </div>
            ) : null}
            <div style={{ fontSize: 11, color: t.textSec, marginTop: 6 }}>
              Evidence:{' '}
              {(row.evidenceReferences ?? [])
                .map((e) => e.evidenceId || e.sourceId || e.sourceLocator)
                .filter(Boolean)
                .join(', ') || '—'}
            </div>
            {row.finding ? (
              <div style={{ fontSize: 11, fontStyle: 'italic', color: t.textMuted, marginTop: 6 }}>
                Explanation (non-authoritative): {row.finding}
              </div>
            ) : null}
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              {onOpenTestPlan ? (
                <button type="button" onClick={() => onOpenTestPlan(row.testId)} style={{ cursor: 'pointer' }}>
                  Open Test Plan
                </button>
              ) : null}
              {onInspectRun && row.executionRunId ? (
                <button type="button" onClick={() => onInspectRun(row.executionRunId!)} style={{ cursor: 'pointer' }}>
                  Inspect Run Logs
                </button>
              ) : null}
              {onOpenAnalysis ? (
                <button type="button" onClick={onOpenAnalysis} style={{ cursor: 'pointer' }}>
                  Open Analysis
                </button>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
      {!loading && !error && rows.length === 0 ? (
        <div style={{ color: t.textMuted, fontSize: 13 }}>No verification evidence chains yet.</div>
      ) : null}
    </div>
  );
}
