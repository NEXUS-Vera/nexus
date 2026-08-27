import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ExecutionRun, ProducedOutput } from '@nexus/contracts';
import {
  cancelExecution,
  getExecution,
  getExecutionLogs,
  listProducedOutputs,
  promoteExecutionEvidence,
} from '../../api/client';
import { CancelExecution } from '../../components/execution/CancelExecution';
import { ExecutionLogViewer } from '../../components/execution/ExecutionLogViewer';
import { ExecutionOutputs } from '../../components/execution/ExecutionOutputs';
import { ExecutionStatus } from '../../components/execution/ExecutionStatus';
import { RuntimeIdentitySummary } from '../../components/execution/RuntimeIdentitySummary';
import { themeColors } from '../../lib/theme';
import { parseCompilerDiagnostics, type CompilerDiagnostic } from './diagnostics';

export type FirmwareExecutionSession = {
  executionRunId: string;
  operation: 'compile' | 'test';
  executionSnapshotId?: string;
};

type Props = {
  projectId: string;
  isDark: boolean;
  session: FirmwareExecutionSession | null;
  onClear: () => void;
  onOpenFile?: (path: string, line: number) => void;
  actor?: { schemaVersion: string; actorId: string; actorType: string; displayName: string };
};

type LogChunk = {
  sequence: number;
  stream: 'stdout' | 'stderr' | 'system';
  content: string;
  truncated?: boolean;
};

function terminalStatuses(status: string | undefined): boolean {
  return status === 'completed' || status === 'failed' || status === 'cancelled' || status === 'timed-out';
}

export function FirmwareOutputPanel({
  projectId,
  isDark,
  session,
  onClear,
  onOpenFile,
  actor,
}: Props) {
  const t = themeColors(isDark);
  const [run, setRun] = useState<ExecutionRun | null>(null);
  const [chunks, setChunks] = useState<LogChunk[]>([]);
  const [logTruncated, setLogTruncated] = useState(false);
  const [outputs, setOutputs] = useState<ProducedOutput[]>([]);
  const [polling, setPolling] = useState(false);
  const afterSeq = useRef(0);
  const promotedRuns = useRef(new Set<string>());

  const poll = useCallback(async () => {
    if (!session) return;
    setPolling(true);
    try {
      const detail = await getExecution(projectId, session.executionRunId);
      setRun(detail.executionRun);
      const logs = await getExecutionLogs(
        projectId,
        session.executionRunId,
        afterSeq.current,
      );
      if (Array.isArray(logs.chunks)) {
        const next = logs.chunks as LogChunk[];
        if (next.length > 0) {
          setChunks((prev) => [...prev, ...next]);
          afterSeq.current = Math.max(afterSeq.current, ...next.map((c) => c.sequence));
        }
      }
      setLogTruncated(Boolean(logs.logTruncated));
      if (detail.executionRun.status === 'completed') {
        const listed = await listProducedOutputs(projectId);
        const mine = listed.filter(
          (item) => item.executionRunId === session.executionRunId,
        );
        setOutputs(mine);
        if (!promotedRuns.current.has(session.executionRunId)) {
          promotedRuns.current.add(session.executionRunId);
          try {
            await promoteExecutionEvidence(projectId, {
              executionRunId: session.executionRunId,
              requestedBy: actor,
              accept: true,
            });
          } catch {
            // Non-blocking; verification can be retried via API / Evidence Explorer.
          }
        }
      }
    } finally {
      setPolling(false);
    }
  }, [actor, projectId, session]);

  useEffect(() => {
    if (!session) {
      setRun(null);
      setChunks([]);
      setOutputs([]);
      afterSeq.current = 0;
      return;
    }
    afterSeq.current = 0;
    setChunks([]);
    void poll();
  }, [session, poll]);

  useEffect(() => {
    if (!session || !run || terminalStatuses(run.status)) return;
    const id = window.setInterval(() => void poll(), 500);
    return () => window.clearInterval(id);
  }, [session, run, poll]);

  const rawLogText = useMemo(
    () => chunks.map((chunk) => chunk.content).join(''),
    [chunks],
  );
  const diagnostics: CompilerDiagnostic[] = useMemo(
    () => parseCompilerDiagnostics(rawLogText),
    [rawLogText],
  );

  if (!session) {
    return (
      <div
        data-testid="firmware-output-panel-empty"
        style={{
          height: 160,
          borderTop: `1px solid ${t.border}`,
          background: t.surface2,
          color: t.textMuted,
          fontSize: 11,
          display: 'flex',
          alignItems: 'center',
          padding: '0 12px',
        }}
      >
        Compile or test output will appear here
      </div>
    );
  }

  return (
    <div
      data-testid="firmware-output-panel"
      style={{
        height: 220,
        borderTop: `1px solid ${t.border}`,
        background: t.surface2,
        display: 'flex',
        flexDirection: 'column',
        minHeight: 0,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '6px 12px',
          borderBottom: `1px solid ${t.border}`,
          fontSize: 11,
        }}
      >
        <span style={{ fontWeight: 600, color: t.text }}>
          {session.operation === 'compile' ? 'Compile' : 'Test'} output
        </span>
        {run ? <ExecutionStatus status={run.status} /> : null}
        {session.executionSnapshotId ? (
          <span style={{ color: t.textMuted }}>
            snapshot {session.executionSnapshotId.slice(0, 12)}…
          </span>
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
          <button type="button" data-testid="firmware-output-clear" onClick={onClear}>
            Clear
          </button>
        </div>
      </div>
      <div style={{ flex: 1, overflow: 'auto', padding: 8 }}>
        <ExecutionLogViewer chunks={chunks} truncated={logTruncated} />
        {diagnostics.length > 0 ? (
          <ul data-testid="firmware-diagnostics" style={{ fontSize: 11, marginTop: 8 }}>
            {diagnostics.map((diag, index) => (
              <li key={`${diag.path}:${diag.line}:${index}`}>
                <button
                  type="button"
                  data-testid={`firmware-diagnostic-${index}`}
                  onClick={() => onOpenFile?.(diag.path, diag.line)}
                  style={{ background: 'none', border: 'none', color: t.cobalt, cursor: 'pointer' }}
                >
                  {diag.path}:{diag.line}:{diag.column} {diag.severity}: {diag.message}
                </button>
              </li>
            ))}
          </ul>
        ) : null}
        {outputs.length > 0 ? (
          <div data-testid="firmware-produced-outputs">
            <ExecutionOutputs outputs={outputs} />
          </div>
        ) : null}
        {run && run.runtimeIdentity ? (
          <RuntimeIdentitySummary identity={run.runtimeIdentity} />
        ) : null}
      </div>
    </div>
  );
}
