/**
 * Phase 16G — Analysis results panel with rich previews, cancel, runtime identity.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import type { ExecutionRun, ProducedOutput } from '@nexus/contracts';
import {
  cancelExecution,
  compareAnalysisOutputs,
  getExecution,
  getExecutionLogs,
  listProducedOutputs,
  previewAnalysisOutput,
  promoteExecutionEvidence,
} from '../../api/client';
import { CancelExecution } from '../../components/execution/CancelExecution';
import { ExecutionLogViewer } from '../../components/execution/ExecutionLogViewer';
import { ExecutionStatus } from '../../components/execution/ExecutionStatus';
import { RuntimeIdentitySummary } from '../../components/execution/RuntimeIdentitySummary';
import { themeColors } from '../../lib/theme';

export type AnalysisExecutionSession = {
  executionRunId: string;
  executionSnapshotId?: string;
  operation: string;
  baselineExecutionRunId?: string;
};

type LogChunk = {
  sequence: number;
  stream: 'stdout' | 'stderr' | 'system';
  content: string;
  truncated?: boolean;
};

type PreviewState = {
  outputId: string;
  previewKind: string;
  text?: string;
  contentBase64?: string;
  truncated?: boolean;
  name?: string;
};

type HashComparison = {
  name: string;
  status: string;
  baselineDigest?: string | null;
  rerunDigest?: string | null;
};

type Props = {
  projectId: string;
  session: AnalysisExecutionSession | null;
  isDark: boolean;
  onClear?: () => void;
  /** Actor used when promoting run outputs into Test Plan (Phase 17F). */
  actor?: { schemaVersion: string; actorId: string; actorType: string; displayName: string };
};

const TERMINAL = new Set(['completed', 'completed-with-warnings', 'failed', 'cancelled', 'timed-out', 'stale']);

const MAX_CSV_ROWS = 50;
const MAX_CSV_COLS = 12;

function terminalStatuses(status: string | undefined): boolean {
  return Boolean(status && TERMINAL.has(status));
}

function parseCsvPreview(text: string): { headers: string[]; rows: string[][]; truncated: boolean } {
  const lines = text.split(/\r?\n/).filter((line) => line.length > 0);
  if (lines.length === 0) return { headers: [], rows: [], truncated: false };
  const parseLine = (line: string) => line.split(',').map((cell) => cell.trim());
  const headers = parseLine(lines[0]).slice(0, MAX_CSV_COLS);
  const body = lines.slice(1);
  const truncated = body.length > MAX_CSV_ROWS || parseLine(lines[0]).length > MAX_CSV_COLS;
  const rows = body.slice(0, MAX_CSV_ROWS).map((line) => parseLine(line).slice(0, MAX_CSV_COLS));
  return { headers, rows, truncated };
}

function formatJsonPreview(text: string): string {
  try {
    return JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    return text;
  }
}

export function AnalysisOutputPanel({ projectId, session, isDark, onClear, actor }: Props) {
  const t = themeColors(isDark);
  const [run, setRun] = useState<ExecutionRun | null>(null);
  const [chunks, setChunks] = useState<LogChunk[]>([]);
  const [logTruncated, setLogTruncated] = useState(false);
  const [outputs, setOutputs] = useState<ProducedOutput[]>([]);
  const [preview, setPreview] = useState<PreviewState | null>(null);
  const [comparisons, setComparisons] = useState<HashComparison[]>([]);
  const [polling, setPolling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const afterSeq = useRef(0);
  const promotedRuns = useRef(new Set<string>());

  const poll = useCallback(async () => {
    if (!session) return;
    setPolling(true);
    try {
      const detail = await getExecution(projectId, session.executionRunId);
      setRun(detail.executionRun);
      const logs = await getExecutionLogs(projectId, session.executionRunId, afterSeq.current);
      if (Array.isArray(logs.chunks) && logs.chunks.length > 0) {
        const next = logs.chunks as LogChunk[];
        setChunks((prev) => [...prev, ...next]);
        afterSeq.current = Math.max(afterSeq.current, ...next.map((c) => c.sequence));
      }
      setLogTruncated(Boolean(logs.logTruncated));
      if (terminalStatuses(detail.executionRun.status)) {
        const listed = await listProducedOutputs(projectId);
        const mine = listed.filter((item) => item.executionRunId === session.executionRunId);
        setOutputs(mine);
        if (session.baselineExecutionRunId) {
          const compared = await compareAnalysisOutputs(projectId, {
            baselineExecutionRunId: session.baselineExecutionRunId,
            rerunExecutionRunId: session.executionRunId,
          });
          const rows = Array.isArray(compared.comparisons)
            ? (compared.comparisons as HashComparison[])
            : [];
          setComparisons(rows);
        }
        // Phase 17F product path: promote ProducedOutputs into Test Plan once outputs exist.
        if (
          (detail.executionRun.status === 'completed' ||
            detail.executionRun.status === 'completed-with-warnings') &&
          !promotedRuns.current.has(session.executionRunId)
        ) {
          promotedRuns.current.add(session.executionRunId);
          try {
            await promoteExecutionEvidence(projectId, {
              executionRunId: session.executionRunId,
              requestedBy: actor,
              accept: true,
            });
          } catch {
            // Idempotent retry via Evidence Explorer / API; do not block results UI.
          }
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Polling failed');
    } finally {
      setPolling(false);
    }
  }, [actor, projectId, session]);

  useEffect(() => {
    if (!session) {
      setRun(null);
      setChunks([]);
      setOutputs([]);
      setPreview(null);
      setComparisons([]);
      setError(null);
      afterSeq.current = 0;
      return;
    }
    afterSeq.current = 0;
    setChunks([]);
    setOutputs([]);
    setPreview(null);
    setComparisons([]);
    setError(null);
    void poll();
  }, [session, poll]);

  useEffect(() => {
    if (!session || !run || terminalStatuses(run.status)) return;
    const id = window.setInterval(() => void poll(), 500);
    return () => window.clearInterval(id);
  }, [session, run, poll]);

  const openPreview = async (outputId: string) => {
    try {
      const payload = await previewAnalysisOutput(projectId, outputId);
      setPreview({
        outputId,
        previewKind: String(payload.previewKind ?? 'unknown'),
        text: typeof payload.text === 'string' ? payload.text : undefined,
        contentBase64: typeof payload.contentBase64 === 'string' ? payload.contentBase64 : undefined,
        truncated: Boolean(payload.truncated),
        name: typeof payload.name === 'string' ? payload.name : undefined,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load output preview');
    }
  };

  if (!session) {
    return (
      <div
        data-testid="analysis-output-panel-empty"
        style={{
          flex: '0 0 160px',
          borderTop: `1px solid ${t.border}`,
          background: t.surface2,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: t.textMuted,
          fontSize: 12,
          padding: 12,
        }}
      >
        Analysis results will appear here after running.
      </div>
    );
  }

  return (
    <div
      data-testid="analysis-output-panel"
      style={{
        flex: '0 0 280px',
        borderTop: `1px solid ${t.border}`,
        background: t.surface2,
        display: 'flex',
        flexDirection: 'column',
        fontSize: 12,
        overflow: 'hidden',
        minHeight: 0,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '6px 10px',
          borderBottom: `1px solid ${t.border}`,
          background: t.bg,
          flexShrink: 0,
        }}
      >
        <span style={{ fontWeight: 600, color: t.text }}>Run output</span>
        {run ? <ExecutionStatus status={run.status} /> : null}
        {session.executionSnapshotId ? (
          <span data-testid="analysis-run-snapshot" style={{ color: t.textMuted }}>
            snapshot {session.executionSnapshotId.slice(0, 12)}…
          </span>
        ) : null}
        {run?.runtimeIdentity ? (
          <RuntimeIdentitySummary identity={run.runtimeIdentity} />
        ) : null}
        {polling ? <span style={{ color: t.textMuted }}>refreshing…</span> : null}
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
          {run && !terminalStatuses(run.status) ? (
            <CancelExecution
              disabled={false}
              onCancel={() =>
                void cancelExecution(projectId, session.executionRunId).then(() => poll())
              }
            />
          ) : null}
          {onClear ? (
            <button type="button" data-testid="analysis-output-clear" onClick={onClear}>
              Clear
            </button>
          ) : null}
        </div>
      </div>

      {error ? (
        <div style={{ padding: '4px 10px', color: '#ef4444', fontSize: 11 }}>{error}</div>
      ) : null}

      <div style={{ flex: 1, overflow: 'auto', padding: 8, minHeight: 0 }}>
        <ExecutionLogViewer chunks={chunks} truncated={logTruncated} />

        {outputs.length > 0 ? (
          <div data-testid="analysis-produced-outputs" style={{ marginTop: 8 }}>
            <div style={{ fontWeight: 600, color: t.textMuted, marginBottom: 4 }}>
              Outputs ({outputs.length})
            </div>
            <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
              {outputs.map((o) => (
                <li key={o.outputId} style={{ marginBottom: 4 }}>
                  <button
                    type="button"
                    data-testid={`analysis-output-${o.outputId}`}
                    onClick={() => void openPreview(o.outputId)}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: t.cobalt,
                      cursor: 'pointer',
                      padding: 0,
                      fontSize: 12,
                    }}
                  >
                    {o.name ?? o.outputId}
                  </button>
                  {o.outputType ? (
                    <span style={{ color: t.textMuted }}> · {o.outputType}</span>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {comparisons.length > 0 ? (
          <div data-testid="analysis-hash-comparisons" style={{ marginTop: 8 }}>
            <div style={{ fontWeight: 600, color: t.textMuted, marginBottom: 4 }}>
              Rerun hash comparison
            </div>
            {comparisons.map((row) => (
              <div key={row.name} data-testid={`analysis-hash-${row.status}`} style={{ color: t.text }}>
                {row.name}: {row.status}
              </div>
            ))}
          </div>
        ) : null}

        {preview ? (
          <div
            data-testid="analysis-output-preview"
            data-preview-kind={preview.previewKind}
            style={{
              marginTop: 8,
              border: `1px solid ${t.border}`,
              borderRadius: 6,
              padding: 8,
              background: t.bg,
            }}
          >
            <div style={{ fontSize: 11, color: t.textMuted, marginBottom: 6 }}>
              Preview · {preview.name ?? preview.outputId}
              {preview.truncated ? ' (truncated)' : ''}
            </div>
            {preview.previewKind === 'image-png' && preview.contentBase64 ? (
              <img
                data-testid="analysis-preview-png"
                alt={preview.name ?? 'plot'}
                src={`data:image/png;base64,${preview.contentBase64}`}
                style={{ maxWidth: '100%', maxHeight: 160 }}
              />
            ) : null}
            {preview.previewKind === 'json' && preview.text ? (
              <pre data-testid="analysis-preview-json" style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: 11 }}>
                {formatJsonPreview(preview.text).slice(0, 8000)}
              </pre>
            ) : null}
            {preview.previewKind === 'csv' && preview.text ? (
              <CsvTable text={preview.text} isDark={isDark} />
            ) : null}
            {(preview.previewKind === 'text' || preview.previewKind === 'unknown') && preview.text ? (
              <pre data-testid="analysis-preview-text" style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: 11 }}>
                {preview.text.slice(0, 8000)}
              </pre>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function CsvTable({ text, isDark }: { text: string; isDark: boolean }) {
  const t = themeColors(isDark);
  const { headers, rows, truncated } = parseCsvPreview(text);
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
      {truncated ? (
        <div style={{ color: t.textMuted, marginTop: 4 }}>Table truncated</div>
      ) : null}
    </div>
  );
}
