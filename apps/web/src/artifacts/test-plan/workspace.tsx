/**
 * Test Plan workspace — requirement coverage first (Phase 17E).
 */
import { useMemo, useState } from 'react';
import type { Artifact } from '@nexus/contracts';
import { themeColors } from '../../lib/theme';

type TestPlanArtifact = Extract<Artifact, { artifactType: 'test-plan' }>;

type Props = {
  artifact: TestPlanArtifact;
  isDark: boolean;
  selectedTestId: string | null;
  onSelectTest: (id: string) => void;
  requirementStatements?: Record<string, string>;
};

const STATUS_TONE: Record<string, string> = {
  passed: '#15803d',
  failed: '#b91c1c',
  blocked: '#b45309',
  inconclusive: '#64748b',
  ready: '#1d4ed8',
  planned: '#64748b',
  running: '#7c3aed',
};

export function TestPlanWorkspace({
  artifact,
  isDark,
  selectedTestId,
  onSelectTest,
  requirementStatements = {},
}: Props) {
  const t = themeColors(isDark);
  const content = artifact.content;
  const cases = content.testCases ?? [];
  const summary = content.coverageSummary;
  const [tab, setTab] = useState<'coverage' | 'tests'>('coverage');

  const coverageRows = useMemo(() => {
    type Case = (typeof cases)[number];
    const byReq = new Map<string, Case[]>();
    for (const c of cases) {
      for (const rid of c.linkedRequirementIds ?? []) {
        const list = byReq.get(rid) ?? [];
        list.push(c);
        byReq.set(rid, list);
      }
    }
    const reqIds = [
      ...new Set([...Object.keys(requirementStatements), ...byReq.keys()]),
    ].sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
    return reqIds.map((reqId) => {
      const tests = byReq.get(reqId) ?? [];
      if (tests.length === 0) {
        return {
          reqId,
          tests,
          state: 'UNCOVERED',
          methods: [] as string[],
        };
      }
      const statuses = tests.map((x) => x.status);
      const assessments = tests.map((x) => x.assessment);
      let state = 'UNVERIFIED';
      if (assessments.includes('FAIL') || statuses.includes('failed')) state = 'FAILED';
      else if (tests.every((x) => x.status === 'passed' || x.assessment === 'PASS')) state = 'VERIFIED';
      else if (statuses.includes('blocked')) state = 'BLOCKED';
      else if (assessments.includes('INCONCLUSIVE') || statuses.includes('inconclusive')) {
        state = 'INCONCLUSIVE';
      }
      return {
        reqId,
        tests,
        state,
        methods: [...new Set(tests.map((x) => x.verificationMethod))],
      };
    });
  }, [cases, requirementStatements]);

  const selected =
    cases.find((c) => c.testId === selectedTestId || c.displayId === selectedTestId) ?? cases[0];

  return (
    <div data-testid="workspace-test-plan" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
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
        <strong style={{ color: t.text }}>{content.title ?? 'Test Plan'}</strong>
        <span data-testid="test-plan-coverage-summary">
          Coverage: {summary.coveredRequirements} / {summary.totalRequirements} requirements covered
        </span>
        <span>Verified: {summary.verifiedRequirements}</span>
        <span>Failed: {summary.failedRequirements}</span>
        <span>Blocked: {summary.blockedRequirements}</span>
        <span>Unverified: {summary.unverifiedRequirements}</span>
        <span>Uncovered: {summary.uncoveredRequirements}</span>
      </div>

      <div style={{ display: 'flex', gap: 8, padding: '8px 16px', borderBottom: `1px solid ${t.border}` }}>
        <button type="button" data-testid="test-plan-tab-coverage" onClick={() => setTab('coverage')} style={tabBtn(tab === 'coverage', t)}>
          Requirement coverage
        </button>
        <button type="button" data-testid="test-plan-tab-tests" onClick={() => setTab('tests')} style={tabBtn(tab === 'tests', t)}>
          Test cases
        </button>
      </div>

      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: 'minmax(0,1.1fr) minmax(0,1fr)', overflow: 'hidden' }}>
        <div style={{ overflow: 'auto', borderRight: `1px solid ${t.border}`, background: t.bg }}>
          {tab === 'coverage' ? (
            <table data-testid="test-plan-coverage-table" style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ color: t.textMuted, textAlign: 'left' }}>
                  <th style={{ padding: 8 }}>Requirement</th>
                  <th style={{ padding: 8 }}>Tests</th>
                  <th style={{ padding: 8 }}>Method</th>
                  <th style={{ padding: 8 }}>State</th>
                </tr>
              </thead>
              <tbody>
                {coverageRows.map((row) => (
                  <tr key={row.reqId} data-testid={`test-plan-coverage-${row.reqId}`}>
                    <td style={{ padding: 8, color: t.text }}>
                      <div>{row.reqId}</div>
                      <div style={{ color: t.textMuted, fontSize: 11 }}>
                        {requirementStatements[row.reqId] ?? ''}
                      </div>
                    </td>
                    <td style={{ padding: 8 }}>
                      {row.tests.length === 0 ? (
                        <span data-testid={`test-plan-uncovered-${row.reqId}`} style={{ color: t.textMuted }}>
                          —
                        </span>
                      ) : (
                        row.tests.map((c) => (
                          <button
                            key={c.testId}
                            type="button"
                            data-testid={`test-plan-select-${c.displayId}`}
                            onClick={() => {
                              setTab('tests');
                              onSelectTest(c.displayId);
                            }}
                            style={{ marginRight: 6, cursor: 'pointer' }}
                          >
                            {c.displayId}
                          </button>
                        ))
                      )}
                    </td>
                    <td style={{ padding: 8, color: t.textSec }}>{row.methods.join(', ')}</td>
                    <td style={{ padding: 8, fontWeight: 650, color: stateColor(row.state) }}>{row.state}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <ul style={{ listStyle: 'none', margin: 0, padding: 8 }}>
              {cases.map((c) => (
                <li key={c.testId}>
                  <button
                    type="button"
                    data-testid={`test-plan-case-${c.displayId}`}
                    onClick={() => onSelectTest(c.displayId)}
                    style={{
                      width: '100%',
                      textAlign: 'left',
                      border: 'none',
                      background: selected?.testId === c.testId ? t.cobaltSelected : 'transparent',
                      padding: '10px 12px',
                      cursor: 'pointer',
                      color: t.text,
                      borderRadius: 6,
                    }}
                  >
                    <div style={{ fontWeight: 650 }}>
                      {c.displayId} — {c.title}
                    </div>
                    <div style={{ fontSize: 11, color: STATUS_TONE[c.status] ?? t.textMuted }}>
                      {c.status.toUpperCase()}
                      {c.assessment ? ` · ${c.assessment}` : ''}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <section style={{ overflow: 'auto', padding: 16 }} data-testid="test-plan-detail">
          {!selected ? (
            <div style={{ color: t.textMuted }}>Select a test case.</div>
          ) : (
            <div>
              <h3 style={{ margin: '0 0 8px', color: t.text }}>
                {selected.displayId} — {selected.title}
              </h3>
              <Meta label="Linked requirements" value={(selected.linkedRequirementIds ?? []).join(' · ') || '—'} t={t} />
              <Meta label="Linked components" value={(selected.linkedComponentIds ?? []).join(' · ') || '—'} t={t} />
              <Meta label="Method" value={selected.verificationMethod} t={t} />
              <Meta label="Expected" value={selected.expectedResult} t={t} />
              {selected.criterion ? (
                <div data-testid="test-plan-criterion" style={{ marginTop: 10, fontSize: 12, color: t.textSec }}>
                  Criterion:{' '}
                  <code>{JSON.stringify(selected.criterion)}</code>
                </div>
              ) : null}
              {selected.actualResult ? (
                <Meta label="Actual" value={selected.actualResult} t={t} />
              ) : null}
              <div
                data-testid="test-plan-assessment"
                style={{
                  marginTop: 12,
                  border: `1px solid ${t.border}`,
                  borderRadius: 8,
                  padding: 12,
                  background: t.surface,
                }}
              >
                <div style={{ fontSize: 11, color: t.textMuted }}>Assessment</div>
                <div
                  style={{
                    fontSize: 20,
                    fontWeight: 700,
                    color: STATUS_TONE[selected.status] ?? t.text,
                  }}
                >
                  {selected.assessment ?? selected.status.toUpperCase()}
                </div>
                <div data-testid="test-plan-assessment-authority" style={{ fontSize: 10, color: t.textMuted, marginTop: 6 }}>
                  Authority:{' '}
                  {selected.assessmentAuthority === 'deterministic-code'
                    ? 'Deterministic'
                    : selected.assessmentAuthority ?? '—'}
                </div>
              </div>
              {selected.finding ? (
                <div data-testid="test-plan-finding" style={{ marginTop: 12, fontStyle: 'italic', color: t.textSec, fontSize: 13 }}>
                  <div style={{ fontSize: 10, letterSpacing: '0.06em', color: t.textMuted }}>FINDING (explanatory)</div>
                  {selected.finding}
                </div>
              ) : null}
              <div data-testid="test-plan-evidence" style={{ marginTop: 12, fontSize: 12, color: t.textSec }}>
                Evidence: {(selected.evidenceReferences ?? []).map((e) => e.evidenceId).join(', ') || '—'}
              </div>
              {selected.executionRunId ? (
                <Meta label="Execution run" value={selected.executionRunId} t={t} />
              ) : null}
              {(selected.procedure ?? []).length > 0 ? (
                <div style={{ marginTop: 12 }}>
                  <div style={{ fontSize: 11, color: t.textMuted }}>Procedure</div>
                  <ol style={{ margin: '4px 0 0', paddingLeft: 18, color: t.text, fontSize: 12 }}>
                    {selected.procedure!.map((step) => (
                      <li key={step}>{step}</li>
                    ))}
                  </ol>
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

function tabBtn(active: boolean, t: ReturnType<typeof themeColors>) {
  return {
    border: `1px solid ${t.border}`,
    background: active ? t.cobaltSelected : t.surface,
    borderRadius: 6,
    padding: '4px 10px',
    cursor: 'pointer',
    fontSize: 12,
    color: t.text,
  } as const;
}

function stateColor(state: string): string {
  if (state === 'VERIFIED') return '#15803d';
  if (state === 'FAILED') return '#b91c1c';
  if (state === 'BLOCKED') return '#b45309';
  return '#64748b';
}
