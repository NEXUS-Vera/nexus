import { useEffect, useRef, useState } from 'react';
import type { ExecutionRun } from '@nexus/contracts';
import { advanceRepair, getExecution, getExecutionLogs, startRepair, type RepairState } from '../../api/client';
import { ExecutionLogViewer, type ExecutionLogChunkView } from './ExecutionLogViewer';

// Defense in depth for diagnostic text; never render workflow/error objects wholesale.
export function redactDiagnostics(text: string): string {
  return text
    .replace(/((?:[\w-]*(?:key|token|secret|password)[\w-]*|authorization)["']?\s*[:=]\s*)[^\r\n]+/gi, '$1[REDACTED]')
    .replace(/\bBearer\s+[^\s]+/gi, 'Bearer [REDACTED]')
    .replace(/\bsk-[\w-]+/g, '[REDACTED]');
}

export function RunLogModal({ projectId, runId, onClose, repair, setRepair, onReviewPatch }: {
  projectId: string; runId: string; onClose: () => void;
  onReviewPatch?: (proposalId: string) => void;
  repair?: RepairState; setRepair: (repair: RepairState) => void;
}) {
  const dialog = useRef<HTMLDivElement>(null);
  const [run, setRun] = useState<ExecutionRun>();
  const [logs, setLogs] = useState<ExecutionLogChunkView[]>([]);
  const [truncated, setTruncated] = useState(false);
  const [error, setError] = useState('');
  const [loadError, setLoadError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    dialog.current?.focus();
    return () => previous?.focus();
  }, []);
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [detail, result] = await Promise.all([getExecution(projectId, runId), getExecutionLogs(projectId, runId)]);
        if (cancelled) return;
        setRun(detail.executionRun);
        // Redact after joining: credentials may cross log-chunk boundaries.
        setLogs([{ sequence: 1, stream: 'system', content: redactDiagnostics(result.chunks.map(chunk => chunk.content).join('')) }]);
        setTruncated(Boolean(result.logTruncated));
        setLoadError('');
      } catch {
        if (!cancelled) setLoadError('Unable to load run logs.');
      }
    }
    void load();
    const timer = window.setInterval(() => void load(), 2000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [projectId, runId]);
  async function diagnose() {
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      const current = repair ?? await startRepair(projectId, {
        executionRunId: runId, target: run?.capability === 'python-kernel' ? 'analysis' : 'firmware', maxAttempts: 3,
      });
      setRepair(current);
      setRepair(await advanceRepair(projectId, current.repairId, current.revision));
    } catch { setError('Repair request failed. Inspect the run and try again.'); }
    finally { setBusy(false); }
  }
  const attempts = repair?.attempts.length ?? 1;
  const stopped = repair && ['exhausted', 'cancelled', 'rejected', 'unavailable', 'stopped', 'completed'].includes(repair.status);
  return (
    <div style={{ position: 'fixed', inset: 0, background: '#0008', zIndex: 200, display: 'grid', placeItems: 'center' }}>
      <div ref={dialog} role="dialog" aria-modal="true" aria-label="Run logs" tabIndex={-1}
        style={{ background: 'var(--nx-surface, white)', color: 'var(--nx-text, #111)', padding: 20, width: 'min(800px, 90vw)', maxHeight: '85vh', overflow: 'auto' }}
        onKeyDown={event => {
          if (event.key === 'Escape') onClose();
          if (event.key === 'Tab') {
            const buttons = Array.from(dialog.current?.querySelectorAll<HTMLButtonElement>('button:not(:disabled)') ?? []);
            const first = buttons[0]; const last = buttons[buttons.length - 1];
            if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.current)) { event.preventDefault(); last?.focus(); }
            else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
          }
        }}>
        <h2>Run logs</h2>
        <button type="button" onClick={onClose}>Close run logs</button>
        <p>Status: {run?.status ?? 'Loading…'}</p>
        {(error || loadError) && <p role="alert">{error || loadError}</p>}
        <ExecutionLogViewer chunks={logs} truncated={truncated} />
        <button type="button" disabled={!run || busy || Boolean(stopped) || attempts >= 3 || !['failed', 'timed-out', 'completed', 'completed-with-warnings'].includes(run.status)} onClick={() => void diagnose()}>
          Diagnose &amp; Repair (Attempt {attempts} of 3)
        </button>
        {repair?.status === 'review' && repair.target === 'firmware' && repair.proposalId && onReviewPatch && (
          <button type="button" onClick={() => onReviewPatch(repair.proposalId!)}>Review repair patch in Workspace</button>
        )}
        {repair && <p role="status">Repair: {repair.status}. {repair.status === 'review' ? 'Review and apply or reject the proposed correction in its workspace before continuing.' : ''}</p>}
      </div>
    </div>
  );
}
