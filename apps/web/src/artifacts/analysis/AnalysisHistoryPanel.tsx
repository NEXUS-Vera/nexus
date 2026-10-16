/**
 * Phase 16F/16I — Analysis snapshot history.
 *
 * Lists workspace snapshots with restore and historical Rerun.
 * Rerun executes the immutable snapshot (not current workspace state).
 */
import { useCallback, useEffect, useState } from 'react';
import {
  createWorkspaceRuntimeSnapshot,
  listWorkspaceRuntimeSnapshots,
  readWorkspaceSnapshotFile,
  restoreWorkspaceRuntimeSnapshot,
  rerunAnalysis,
} from '../../api/client';
import { themeColors } from '../../lib/theme';
import { AnalysisMonacoEditor } from './MonacoEditor';

export type SnapshotRow = {
  snapshotId: string;
  reason: string;
  createdAt: string;
  createdBy?: { displayName?: string; actorType?: string };
  snapshotVersion?: number;
};

type ExecSession = {
  executionRunId: string;
  executionSnapshotId?: string;
  operation: string;
};

type Props = {
  projectId: string;
  isDark: boolean;
  hasDirtyBuffers: boolean;
  onRequireCleanWorkspace: () => boolean;
  onRestored: () => Promise<void>;
  onRerun: (session: ExecSession) => void;
  actor: Record<string, unknown>;
};

function parseSnapshots(payload: Record<string, unknown>): SnapshotRow[] {
  const rows = payload.snapshots;
  if (!Array.isArray(rows)) return [];
  return rows
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object')
    .map((item) => ({
      snapshotId: String(item.snapshotId ?? ''),
      reason: String(item.reason ?? ''),
      createdAt: String(item.createdAt ?? ''),
      createdBy:
        item.createdBy && typeof item.createdBy === 'object'
          ? (item.createdBy as SnapshotRow['createdBy'])
          : undefined,
      snapshotVersion:
        typeof item.snapshotVersion === 'number' ? item.snapshotVersion : undefined,
    }))
    .filter((item) => item.snapshotId.length > 0)
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return Boolean(v) && typeof v === 'object' && !Array.isArray(v);
}

function humanReason(reason: string): string {
  const key = reason.trim().toLowerCase();
  if (key === 'manual') return 'Manual snapshot';
  if (key === 'before-analysis-run' || key === 'before_analysis_run') return 'Before analysis run';
  if (key === 'before-restore' || key === 'before_restore') return 'Before restore';
  if (key === 'patch-base' || key === 'patch_base' || key === 'patch base') return 'Patch base';
  if (key.includes('verif')) return reason;
  return reason || 'Snapshot';
}

export function AnalysisHistoryPanel({
  projectId,
  isDark,
  hasDirtyBuffers,
  onRequireCleanWorkspace,
  onRestored,
  onRerun,
  actor,
}: Props) {
  const t = themeColors(isDark);
  const [snapshots, setSnapshots] = useState<SnapshotRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [previewPath, setPreviewPath] = useState<string | null>(null);
  const [previewContent, setPreviewContent] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const listed = await listWorkspaceRuntimeSnapshots(projectId, 'analysis');
      setSnapshots(parseSnapshots(listed));
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const createSnapshot = async () => {
    if (hasDirtyBuffers && !onRequireCleanWorkspace()) return;
    setBusy(true);
    setMessage(null);
    try {
      await createWorkspaceRuntimeSnapshot(projectId, 'analysis', {
        reason: 'manual',
        requestedBy: actor,
      });
      setMessage('Snapshot created');
      await refresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Failed to create snapshot');
    } finally {
      setBusy(false);
    }
  };

  const restoreSnapshot = async (snapshotId: string) => {
    if (hasDirtyBuffers && !onRequireCleanWorkspace()) return;
    setBusy(true);
    setMessage(null);
    try {
      await restoreWorkspaceRuntimeSnapshot(projectId, 'analysis', snapshotId, {
        requestedBy: actor,
      });
      setMessage('Snapshot restored');
      await onRestored();
      await refresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Failed to restore snapshot');
    } finally {
      setBusy(false);
    }
  };

  const rerunSnapshot = async (snapshotId: string) => {
    setBusy(true);
    setMessage(null);
    try {
      const result = await rerunAnalysis(projectId, {
        snapshotId,
        requestedBy: actor,
      });
      const run = isRecord(result.executionRun) ? result.executionRun : null;
      const runId = run && typeof run.executionRunId === 'string' ? run.executionRunId : null;
      if (!runId) throw new Error('Rerun did not return an execution run.');
      setMessage(`Historical Rerun started (${runId.slice(-8)})`);
      onRerun({
        executionRunId: runId,
        executionSnapshotId: snapshotId,
        operation: 'run',
      });
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Failed to rerun snapshot');
    } finally {
      setBusy(false);
    }
  };

  const previewFile = async (snapshotId: string, path: string) => {
    setBusy(true);
    try {
      const payload = await readWorkspaceSnapshotFile(projectId, 'analysis', snapshotId, path);
      setSelectedId(snapshotId);
      setPreviewPath(path);
      setPreviewContent(typeof payload.content === 'string' ? payload.content : '');
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Failed to load snapshot file');
    } finally {
      setBusy(false);
    }
  };

  const selected = snapshots.find((s) => s.snapshotId === selectedId) ?? null;

  return (
    <div
      data-testid="analysis-history-panel"
      style={{
        flex: 1,
        minHeight: 0,
        display: 'flex',
        background: t.bg,
      }}
    >
      <aside
        style={{
          width: 320,
          flexShrink: 0,
          borderRight: `1px solid ${t.border}`,
          background: t.surface,
          display: 'flex',
          flexDirection: 'column',
          minHeight: 0,
        }}
      >
        <div
          style={{
            padding: '10px 12px',
            borderBottom: `1px solid ${t.border}`,
            display: 'flex',
            gap: 8,
            alignItems: 'center',
          }}
        >
          <strong style={{ fontSize: 12, color: t.text }}>History</strong>
          <button
            type="button"
            data-testid="analysis-create-snapshot"
            disabled={busy}
            onClick={() => void createSnapshot()}
            style={{ marginLeft: 'auto', fontSize: 11 }}
          >
            Create snapshot
          </button>
        </div>

        {message ? (
          <div
            data-testid="analysis-history-message"
            style={{ padding: '6px 12px', fontSize: 11, color: t.textSec }}
          >
            {message}
          </div>
        ) : null}

        <div style={{ flex: 1, overflow: 'auto', padding: '4px 0' }}>
          {loading ? (
            <div style={{ padding: 12, fontSize: 12, color: t.textMuted }}>Loading…</div>
          ) : snapshots.length === 0 ? (
            <div
              data-testid="analysis-history-empty"
              style={{ padding: 12, fontSize: 12, color: t.textMuted }}
            >
              No snapshots yet. Run Current creates an immutable snapshot before execution.
            </div>
          ) : (
            <ul
              data-testid="analysis-history-list"
              style={{ listStyle: 'none', margin: 0, padding: 0 }}
            >
              {snapshots.map((snap) => (
                <li key={snap.snapshotId}>
                  <button
                    type="button"
                    data-testid={`analysis-history-item-${snap.snapshotId}`}
                    onClick={() => {
                      setSelectedId(snap.snapshotId);
                      setPreviewPath(null);
                    }}
                    style={{
                      display: 'block',
                      width: '100%',
                      textAlign: 'left',
                      border: 'none',
                      background: selectedId === snap.snapshotId ? t.cobaltSelected : 'transparent',
                      padding: '10px 12px',
                      cursor: 'pointer',
                      color: t.text,
                    }}
                  >
                    <div style={{ fontSize: 12, fontWeight: 650 }}>{humanReason(snap.reason)}</div>
                    <div style={{ fontSize: 11, color: t.textMuted, marginTop: 2 }}>
                      Snapshot {snap.snapshotId.slice(0, 16)}…
                      {snap.snapshotVersion != null ? ` · v${snap.snapshotVersion}` : ''}
                    </div>
                    <div style={{ fontSize: 10, color: t.textMuted, marginTop: 2 }}>
                      {snap.createdAt}
                      {snap.createdBy?.displayName ? ` · ${snap.createdBy.displayName}` : ''}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>

      <section style={{ flex: 1, minWidth: 0, overflow: 'auto', padding: 16 }}>
        {!selected ? (
          <div data-testid="analysis-history-placeholder" style={{ color: t.textMuted, fontSize: 13 }}>
            Select a snapshot to restore, inspect files, or Rerun the historical immutable state.
          </div>
        ) : (
          <div data-testid="analysis-history-detail" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div>
              <h3 style={{ margin: 0, fontSize: 16, color: t.text }}>{humanReason(selected.reason)}</h3>
              <div style={{ marginTop: 6, fontSize: 12, color: t.textSec, display: 'grid', gap: 4 }}>
                <div>
                  Snapshot: <code>{selected.snapshotId}</code>
                </div>
                <div>Created: {selected.createdAt}</div>
                <div>
                  Actor:{' '}
                  {selected.createdBy?.displayName ??
                    selected.createdBy?.actorType ??
                    '—'}
                </div>
                {selected.snapshotVersion != null ? (
                  <div>Version: {selected.snapshotVersion}</div>
                ) : null}
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button
                type="button"
                data-testid="analysis-restore-snapshot"
                disabled={busy}
                onClick={() => void restoreSnapshot(selected.snapshotId)}
              >
                Restore
              </button>
              <button
                type="button"
                data-testid="analysis-rerun-snapshot"
                disabled={busy}
                onClick={() => void rerunSnapshot(selected.snapshotId)}
              >
                Rerun
              </button>
              <button
                type="button"
                data-testid="analysis-preview-analysis-py"
                disabled={busy}
                onClick={() => void previewFile(selected.snapshotId, 'analysis.py')}
              >
                Preview analysis.py
              </button>
              <button
                type="button"
                data-testid="analysis-preview-readme"
                disabled={busy}
                onClick={() => void previewFile(selected.snapshotId, 'README.md')}
              >
                Preview README.md
              </button>
            </div>
            <p style={{ margin: 0, fontSize: 12, color: t.textMuted }}>
              Rerun executes this snapshot only — it does not use the current workspace draft.
            </p>
            {previewPath ? (
              <div data-testid="analysis-snapshot-preview" style={{ minHeight: 220 }}>
                <div style={{ fontSize: 11, color: t.textMuted, marginBottom: 6 }}>{previewPath}</div>
                <AnalysisMonacoEditor
                  path={previewPath}
                  content={previewContent}
                  isDark={isDark}
                  readOnly
                  onChange={() => undefined}
                />
              </div>
            ) : null}
          </div>
        )}
      </section>
    </div>
  );
}
