/**
 * Results-first Analysis experience: metrics, assessment, plots, tables, provenance.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ExecutionRun, ProducedOutput } from '@nexus/contracts';
import {
  cancelExecution,
  compareAnalysisOutputs,
  getExecution,
  getExecutionLogs,
  listProducedOutputs,
  previewAnalysisOutput,
} from '../../api/client';
import { CancelExecution } from '../../components/execution/CancelExecution';
import { ExecutionLogViewer } from '../../components/execution/ExecutionLogViewer';
import { ExecutionStatus } from '../../components/execution/ExecutionStatus';
import { RuntimeIdentitySummary } from '../../components/execution/RuntimeIdentitySummary';
import { themeColors } from '../../lib/theme';
import { AnalysisInvestigationHeader } from './AnalysisInvestigationHeader';
import type { AnalysisExecutionSession } from './AnalysisOutputPanel';
import {
  formatEngineeringNumber,
  type AnalysisInvestigation,
} from './modes';

type HashComparison = {
  name: string;
  status: string;
};

type PreviewState = {
  outputId: string;
  name?: string;
  previewKind: string;
  text?: string;
  contentBase64?: string;
  truncated?: boolean;
};

type Props = {
  projectId: string;
  isDark: boolean;
  investigation: AnalysisInvestigation | null;
  session: AnalysisExecutionSession | null;
  hasCode: boolean;
  hasData: boolean;
  onRunCurrent: () => void;
  onOpenCode: () => void;
  onOpenData: () => void;
  onGenerateScaffold?: () => void;
  running?: boolean;
};

const TERMINAL = new Set([
  'completed',
  'completed-with-warnings',
  'failed',
  'cancelled',
  'timed-out',
  'stale',
]);

const MAX_CSV_ROWS = 40;
const MAX_CSV_COLS = 10;

function isTerminal(status: string | undefined): boolean {
  return Boolean(status && TERMINAL.has(status));
}

function parseCsv(text: string): { headers: string[]; rows: string[][]; truncated: boolean } {
  const lines = text.split(/\r?\n/).filter((line) => line.length > 0);
  if (lines.length === 0) return { headers: [], rows: [], truncated: false };
  const parseLine = (line: string) => line.split(',').map((cell) => cell.trim());
  const headers = parseLine(lines[0]).slice(0, MAX_CSV_COLS);
  const body = lines.slice(1);
  const truncated = body.length > MAX_CSV_ROWS || parseLine(lines[0]).length > MAX_CSV_COLS;
  const rows = body.slice(0, MAX_CSV_ROWS).map((line) => parseLine(line).slice(0, MAX_CSV_COLS));
  return { headers, rows, truncated };
}

function metricFromSummary(summary: Record<string, unknown> | null): {
  metricLabel: string;
  metricValue: string;
  thresholdLabel: string;
  assessment: string | null;
  authority: string | null;
  finding: string | null;
  raw: Record<string, unknown> | null;
} {
  if (!summary) {
    return {
      metricLabel: 'Metric',
      metricValue: '—',
      thresholdLabel: '—',
      assessment: null,
      authority: null,
      finding: null,
      raw: null,
    };
  }
  const rms =
    typeof summary.accel_x_rms_noise_g === 'number'
      ? summary.accel_x_rms_noise_g
      : typeof summary.metricValue === 'number'
        ? summary.metricValue
        : null;
  const threshold =
    typeof summary.threshold_g === 'number'
      ? summary.threshold_g
      : typeof summary.threshold === 'number'
        ? summary.threshold
        : null;
  const operator = typeof summary.operator === 'string' ? summary.operator : '<';
  const unit =
    typeof summary.unit === 'string'
      ? summary.unit
      : threshold != null || rms != null
        ? 'g'
        : '';
  const assessment =
    typeof summary.assessment === 'string' ? summary.assessment.toUpperCase() : null;
  const authority =
    typeof summary.authority === 'string'
      ? summary.authority
      : assessment
        ? 'deterministic-code'
        : null;
  const finding =
    typeof summary.finding === 'string'
      ? summary.finding
      : typeof summary.note === 'string'
        ? summary.note
        : assessment === 'PASS' && rms != null && threshold != null
          ? `Stationary accel_x RMS remained below the required threshold (${formatEngineeringNumber(rms)} ${unit} ${operator} ${formatEngineeringNumber(threshold)} ${unit}).`
          : null;

  return {
    metricLabel:
      typeof summary.metricId === 'string'
        ? summary.metricId.replace(/_/g, ' ')
        : 'Accel X RMS Noise',
    metricValue:
      rms != null ? `${formatEngineeringNumber(rms)}${unit ? ` ${unit}` : ''}` : '—',
    thresholdLabel:
      threshold != null
        ? `${operator} ${formatEngineeringNumber(threshold)}${unit ? ` ${unit}` : ''}`
        : '—',
    assessment,
    authority,
    finding,
    raw: summary,
  };
}

export function AnalysisResultsView({
  projectId,
  isDark,
  investigation,
  session,
  hasCode,
  hasData,
  onRunCurrent,
  onOpenCode,
  onOpenData,
  onGenerateScaffold,
  running = false,
}: Props) {
  const t = themeColors(isDark);
  const [run, setRun] = useState<ExecutionRun | null>(null);
  const [outputs, setOutputs] = useState<ProducedOutput[]>([]);
  const [previews, setPreviews] = useState<Record<string, PreviewState>>({});
  const [chunks, setChunks] = useState<
    Array<{ sequence: number; stream: 'stdout' | 'stderr' | 'system'; content: string }>
  >([]);
  const [showExecution, setShowExecution] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [afterSeq, setAfterSeq] = useState(0);
  const [comparisons, setComparisons] = useState<HashComparison[]>([]);

  const refresh = useCallback(async () => {
    if (!session) return;
    try {
      const detail = await getExecution(projectId, session.executionRunId);
      setRun(detail.executionRun);
      const logs = await getExecutionLogs(projectId, session.executionRunId, afterSeq);
      if (Array.isArray(logs.chunks) && logs.chunks.length > 0) {
        const next = logs.chunks as Array<{
          sequence: number;
          stream: 'stdout' | 'stderr' | 'system';
          content: string;
        }>;
        setChunks((prev) => [...prev, ...next]);
        setAfterSeq(Math.max(afterSeq, ...next.map((c) => c.sequence)));
      }
      if (isTerminal(detail.executionRun.status)) {
        const listed = await listProducedOutputs(projectId);
        const mine = listed.filter((item) => item.executionRunId === session.executionRunId);
        setOutputs(mine);
        if (session.baselineExecutionRunId) {
          try {
            const compared = await compareAnalysisOutputs(projectId, {
              baselineExecutionRunId: session.baselineExecutionRunId,
              rerunExecutionRunId: session.executionRunId,
            });
            const rows = Array.isArray(compared.comparisons)
              ? (compared.comparisons as HashComparison[])
              : [];
            setComparisons(rows);
          } catch {
            setComparisons([]);
          }
        } else {
          setComparisons([]);
        }
        const nextPreviews: Record<string, PreviewState> = {};
        for (const item of mine) {
          const name = String(item.name ?? '');
          if (
            name.includes('summary.json') ||
            name.includes('accel_plot.png') ||
            name.includes('processed.csv') ||
            name.includes('note.txt') ||
            name.includes('results.json')
          ) {
            try {
              const payload = await previewAnalysisOutput(projectId, item.outputId);
              nextPreviews[name] = {
                outputId: item.outputId,
                name,
                previewKind: String(payload.previewKind ?? 'unknown'),
                text: typeof payload.text === 'string' ? payload.text : undefined,
                contentBase64:
                  typeof payload.contentBase64 === 'string'
                    ? payload.contentBase64
                    : undefined,
                truncated: Boolean(payload.truncated),
              };
            } catch {
              // preview optional
            }
          }
        }
        setPreviews(nextPreviews);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load analysis results');
    }
  }, [afterSeq, projectId, session]);

  useEffect(() => {
    setRun(null);
    setOutputs([]);
    setPreviews({});
    setChunks([]);
    setAfterSeq(0);
    setError(null);
    setComparisons([]);
    if (session) void refresh();
  }, [session]); // eslint-disable-line react-hooks/exhaustive-deps -- reset on session change

  useEffect(() => {
    if (!session || !run || isTerminal(run.status)) return;
    const id = window.setInterval(() => void refresh(), 500);
    return () => window.clearInterval(id);
  }, [session, run, refresh]);

  const summaryPreview = useMemo(() => {
    const entry = Object.entries(previews).find(([name]) => name.includes('summary.json'));
    if (!entry?.[1]?.text) return null;
    try {
      return JSON.parse(entry[1].text) as Record<string, unknown>;
    } catch {
      return null;
    }
  }, [previews]);

  const metrics = metricFromSummary(summaryPreview);
  const plot = Object.entries(previews).find(([name]) => name.includes('accel_plot.png'))?.[1];
  const csv = Object.entries(previews).find(([name]) => name.includes('processed.csv'))?.[1];
  const txt = Object.entries(previews).find(([name]) => name.includes('.txt'))?.[1];
  const purpose = investigation?.purpose ?? 'exploration';
  const hasCriterion = Boolean(
    investigation?.verificationCriterion ||
      (summaryPreview && (summaryPreview.threshold_g != null || summaryPreview.threshold != null)),
  );
  const runFailed =
    run?.status === 'failed' ||
    run?.status === 'cancelled' ||
    run?.status === 'timed-out' ||
    run?.status === 'stale';

  const comparisonLabel = (() => {
    if (!session?.baselineExecutionRunId) return null;
    if (comparisons.length === 0) return 'Not comparable';
    if (comparisons.every((c) => c.status === 'match')) return 'Outputs match';
    if (comparisons.some((c) => c.status === 'differ' || c.status === 'mismatch')) {
      return 'Outputs differ';
    }
    return 'Not comparable';
  })();

  const statusLabel = !session
    ? 'No run yet'
    : run && !isTerminal(run.status)
      ? 'Running'
      : runFailed
        ? 'Failed'
        : metrics.assessment === 'PASS' && purpose === 'verification'
          ? 'Verified'
          : metrics.assessment ?? (run?.status ? String(run.status) : 'Ready');

  if (!session) {
    return (
      <div data-testid="analysis-results-view" style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
        <AnalysisInvestigationHeader
          investigation={investigation}
          isDark={isDark}
          statusLabel={statusLabel}
        />
        <div
          data-testid="analysis-results-empty"
          style={{ padding: 24, maxWidth: 560, color: t.textSec, fontSize: 13, lineHeight: 1.5 }}
        >
          <h3 style={{ marginTop: 0, color: t.text, fontSize: 15 }}>No analysis results yet</h3>
          <p style={{ marginTop: 0 }}>
            Run Current executes a clean snapshot of the saved Analysis filesystem and produces
            deterministic outputs.
          </p>
          <ul style={{ paddingLeft: 18, margin: '0 0 16px' }}>
            {!hasCode ? <li>No analysis implementation yet — generate a scaffold or open Code.</li> : null}
            {!hasData ? <li>No analysis inputs yet — upload a dataset in Data.</li> : null}
            {hasCode && hasData ? <li>Code and data look ready — run a clean verification.</li> : null}
          </ul>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {!hasCode && onGenerateScaffold ? (
              <button type="button" data-testid="analysis-results-scaffold" onClick={onGenerateScaffold}>
                Generate Scaffold
              </button>
            ) : null}
            <button type="button" data-testid="analysis-results-open-data" onClick={onOpenData}>
              Data
            </button>
            <button type="button" data-testid="analysis-results-open-code" onClick={onOpenCode}>
              Edit Code
            </button>
            <button
              type="button"
              data-testid="analysis-results-run"
              disabled={!hasCode || running}
              onClick={onRunCurrent}
            >
              {running ? 'Running…' : 'Run Current'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  const assessmentTone =
    metrics.assessment === 'PASS'
      ? '#15803d'
      : metrics.assessment === 'FAIL'
        ? '#b91c1c'
        : t.textMuted;

  return (
    <div data-testid="analysis-results-view" style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
      <AnalysisInvestigationHeader
        investigation={investigation}
        isDark={isDark}
        statusLabel={statusLabel}
      />

      {error ? (
        <div style={{ padding: '8px 16px', color: '#b91c1c', fontSize: 12 }}>{error}</div>
      ) : null}

      <div style={{ padding: '16px 16px 24px', display: 'flex', flexDirection: 'column', gap: 16 }}>
        {run && !isTerminal(run.status) ? (
          <div data-testid="analysis-results-running" style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <ExecutionStatus status={run.status} />
            <CancelExecution
              disabled={false}
              onCancel={() =>
                void cancelExecution(projectId, session.executionRunId).then(() => refresh())
              }
            />
          </div>
        ) : null}

        {runFailed ? (
          <div
            data-testid="analysis-results-failed"
            style={{
              border: '1px solid #fecaca',
              borderRadius: 8,
              padding: '10px 12px',
              background: '#fef2f2',
              color: '#991b1b',
              fontSize: 12,
            }}
          >
            Analysis run {run?.status ?? 'failed'}.
            {run?.error?.message ? ` ${run.error.message}` : ' Inspect execution details for logs.'}
          </div>
        ) : null}

        {purpose === 'exploration' && !hasCriterion ? (
          <div
            data-testid="analysis-exploration-banner"
            style={{
              border: `1px solid ${t.border}`,
              borderRadius: 8,
              padding: '10px 12px',
              background: t.surface2,
              color: t.textSec,
              fontSize: 12,
            }}
          >
            Exploration result — no verification criterion. Computed values are not Evidence.
          </div>
        ) : null}

        {comparisonLabel ? (
          <div
            data-testid="analysis-hash-comparison-summary"
            style={{
              border: `1px solid ${t.border}`,
              borderRadius: 8,
              padding: '8px 12px',
              background: t.surface2,
              fontSize: 12,
              color: t.text,
            }}
          >
            Rerun comparison: <strong>{comparisonLabel}</strong>
          </div>
        ) : null}

        <div
          data-testid="analysis-metric-row"
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 10,
          }}
        >
          <MetricCard title={metrics.metricLabel} value={metrics.metricValue} isDark={isDark} />
          <MetricCard title="Requirement limit" value={metrics.thresholdLabel} isDark={isDark} />
          <div
            data-testid="analysis-assessment-card"
            style={{
              minWidth: 140,
              flex: '1 1 140px',
              border: `1px solid ${t.border}`,
              borderRadius: 8,
              padding: '10px 12px',
              background: t.surface,
            }}
          >
            <div style={{ fontSize: 11, color: t.textMuted, marginBottom: 4 }}>Assessment</div>
            <div
              data-testid="analysis-assessment-value"
              style={{ fontSize: 20, fontWeight: 700, color: assessmentTone }}
            >
              {purpose === 'exploration' && !hasCriterion && !metrics.assessment
                ? 'No verification criterion'
                : metrics.assessment ??
                  (runFailed
                    ? 'INCONCLUSIVE'
                    : hasCriterion
                      ? 'INCONCLUSIVE'
                      : '—')}
            </div>
            {metrics.assessment === 'INCONCLUSIVE' ||
            (!metrics.assessment && hasCriterion && isTerminal(run?.status)) ? (
              <div data-testid="analysis-assessment-inconclusive-reason" style={{ fontSize: 11, color: t.textSec, marginTop: 4 }}>
                {typeof summaryPreview?.reason === 'string'
                  ? summaryPreview.reason
                  : 'Expected metric was not produced or could not be assessed.'}
              </div>
            ) : null}
            {metrics.assessment && metrics.metricValue !== '—' && metrics.thresholdLabel !== '—' ? (
              <div data-testid="analysis-assessment-detail" style={{ fontSize: 11, color: t.textSec, marginTop: 4 }}>
                {metrics.metricValue} {metrics.thresholdLabel}
              </div>
            ) : null}
            <div
              data-testid="analysis-assessment-authority"
              style={{ fontSize: 10, color: t.textMuted, marginTop: 6, letterSpacing: '0.04em' }}
            >
              Authority:{' '}
              {metrics.assessment
                ? metrics.authority === 'deterministic-code' || !metrics.authority
                  ? 'Deterministic'
                  : metrics.authority
                : '—'}
            </div>
          </div>
        </div>

        {plot?.contentBase64 ? (
          <div
            data-testid="analysis-primary-plot"
            style={{
              border: `1px solid ${t.border}`,
              borderRadius: 8,
              padding: 12,
              background: t.surface,
            }}
          >
            <div style={{ fontSize: 12, fontWeight: 600, color: t.text, marginBottom: 8 }}>
              Visualization
            </div>
            <img
              data-testid="analysis-preview-png"
              alt={plot.name ?? 'Analysis plot'}
              src={`data:image/png;base64,${plot.contentBase64}`}
              style={{ maxWidth: '100%', height: 'auto', display: 'block' }}
            />
          </div>
        ) : null}

        {csv?.text ? (
          <div
            data-testid="analysis-processed-table"
            style={{
              border: `1px solid ${t.border}`,
              borderRadius: 8,
              padding: 12,
              background: t.surface,
            }}
          >
            <div style={{ fontSize: 12, fontWeight: 600, color: t.text, marginBottom: 8 }}>
              Processed table
            </div>
            <CsvBlock text={csv.text} isDark={isDark} />
          </div>
        ) : null}

        {txt?.text ? (
          <div
            data-testid="analysis-preview-txt"
            style={{
              border: `1px solid ${t.border}`,
              borderRadius: 8,
              padding: 12,
              background: t.surface,
              fontSize: 12,
              color: t.textSec,
              whiteSpace: 'pre-wrap',
            }}
          >
            {txt.text.slice(0, 4000)}
          </div>
        ) : null}

        {metrics.finding ? (
          <div
            data-testid="analysis-finding"
            style={{
              borderLeft: `3px solid ${t.border}`,
              padding: '4px 0 4px 12px',
              color: t.textSec,
              fontSize: 13,
              fontStyle: 'italic',
            }}
          >
            <div style={{ fontSize: 10, letterSpacing: '0.06em', color: t.textMuted, marginBottom: 4 }}>
              FINDING (explanatory)
            </div>
            {metrics.finding}
          </div>
        ) : null}

        <details
          data-testid="analysis-provenance"
          style={{
            border: `1px solid ${t.border}`,
            borderRadius: 8,
            padding: '8px 12px',
            background: t.surface2,
            fontSize: 12,
            color: t.textSec,
          }}
        >
          <summary style={{ cursor: 'pointer', color: t.text, fontWeight: 600 }}>
            Provenance
          </summary>
          <div style={{ marginTop: 8, display: 'grid', gap: 4 }}>
            <div>Run: {session.executionRunId}</div>
            {session.executionSnapshotId ? <div>Snapshot: {session.executionSnapshotId}</div> : null}
            {run?.runtimeIdentity ? (
              <div>
                Runtime: <RuntimeIdentitySummary identity={run.runtimeIdentity} />
              </div>
            ) : null}
            <div>Outputs: {outputs.map((o) => o.name).filter(Boolean).join(', ') || '—'}</div>
            {comparisonLabel ? <div>Hash comparison: {comparisonLabel}</div> : null}
          </div>
        </details>

        <div>
          <button
            type="button"
            data-testid="analysis-execution-toggle"
            onClick={() => setShowExecution((v) => !v)}
            style={{
              border: `1px solid ${t.border}`,
              background: t.surface,
              borderRadius: 6,
              padding: '6px 10px',
              fontSize: 12,
              cursor: 'pointer',
              color: t.text,
            }}
          >
            {showExecution ? 'Hide execution details' : 'Show execution details'}
          </button>
          {showExecution ? (
            <div
              data-testid="analysis-execution-details"
              style={{
                marginTop: 8,
                border: `1px solid ${t.border}`,
                borderRadius: 8,
                padding: 10,
                background: t.bg,
              }}
            >
              {run ? <ExecutionStatus status={run.status} /> : null}
              <ExecutionLogViewer chunks={chunks} truncated={false} />
              {summaryPreview ? (
                <pre
                  data-testid="analysis-preview-json"
                  style={{ marginTop: 8, fontSize: 11, whiteSpace: 'pre-wrap' }}
                >
                  {JSON.stringify(summaryPreview, null, 2).slice(0, 8000)}
                </pre>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function MetricCard({
  title,
  value,
  isDark,
}: {
  title: string;
  value: string;
  isDark: boolean;
}) {
  const t = themeColors(isDark);
  return (
    <div
      style={{
        minWidth: 140,
        flex: '1 1 140px',
        border: `1px solid ${t.border}`,
        borderRadius: 8,
        padding: '10px 12px',
        background: t.surface,
      }}
    >
      <div style={{ fontSize: 11, color: t.textMuted, marginBottom: 4 }}>{title}</div>
      <div style={{ fontSize: 18, fontWeight: 650, color: t.text }}>{value}</div>
    </div>
  );
}

function CsvBlock({ text, isDark }: { text: string; isDark: boolean }) {
  const t = themeColors(isDark);
  const { headers, rows, truncated } = parseCsv(text);
  return (
    <div data-testid="analysis-preview-csv">
      <table style={{ borderCollapse: 'collapse', fontSize: 11, width: '100%' }}>
        <thead>
          <tr>
            {headers.map((h) => (
              <th
                key={h}
                style={{
                  borderBottom: `1px solid ${t.border}`,
                  textAlign: 'left',
                  padding: '2px 4px',
                  color: t.textMuted,
                }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr key={idx}>
              {row.map((cell, cidx) => (
                <td key={cidx} style={{ padding: '2px 4px', color: t.text }}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {truncated ? <div style={{ color: t.textMuted, marginTop: 4 }}>Table truncated</div> : null}
    </div>
  );
}
