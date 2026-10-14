import { useCallback, useEffect, useState } from 'react';
import {
  createWorkspaceRuntimeSnapshot,
  listWorkspaceRuntimeSnapshots,
  readWorkspaceSnapshotFile,
  restoreWorkspaceRuntimeSnapshot,
} from '../../api/client';
import { themeColors } from '../../lib/theme';
import { FirmwareMonacoEditor } from './MonacoEditor';

export type SnapshotRow = {
  snapshotId: string;
  reason: string;
  createdAt: string;
  createdBy?: { displayName?: string; actorType?: string };
  snapshotVersion?: number;
};

type Props = {
  projectId: string;
  isDark: boolean;
  hasDirtyBuffers: boolean;
  onRequireCleanWorkspace: () => boolean;
  onRestored: () => Promise<void>;
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

export function FirmwareHistoryPanel({
  projectId,
  isDark,
  hasDirtyBuffers,
  onRequireCleanWorkspace,
  onRestored,
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
      const listed = await listWorkspaceRuntimeSnapshots(projectId, 'firmware');
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
      await createWorkspaceRuntimeSnapshot(projectId, 'firmware', {
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
      await restoreWorkspaceRuntimeSnapshot(projectId, 'firmware', snapshotId, {
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

  const previewFile = async (snapshotId: string, path: string) => {
    setBusy(true);
    try {
      const payload = await readWorkspaceSnapshotFile(projectId, 'firmware', snapshotId, path);
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
    <aside
      data-testid="firmware-history-panel"
      style={{
        width: 280,
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
          padding: '8px 10px',
          borderBottom: `1px solid ${t.border}`,
          display: 'flex',
          gap: 8,
          alignItems: 'center',
        }}
      >
        <strong style={{ fontSize: 12, color: t.text }}>History</strong>
        <button
          type="button"
          data-testid="firmware-create-snapshot"
          disabled={busy}
          onClick={() => void createSnapshot()}
          style={{ marginLeft: 'auto', fontSize: 11 }}
        >
          Create snapshot
        </button>
      </div>
      {message ? (
        <div style={{ padding: '6px 10px', fontSize: 11, color: t.textSec }}>{message}</div>
      ) : null}
      <div style={{ flex: 1, overflow: 'auto', padding: '4px 0' }}>
        {loading ? (
          <div style={{ padding: 10, fontSize: 11, color: t.textMuted }}>Loading…</div>
        ) : snapshots.length === 0 ? (
          <div data-testid="firmware-history-empty" style={{ padding: 10, fontSize: 11, color: t.textMuted }}>
            No snapshots yet
          </div>
        ) : (
          <ul data-testid="firmware-history-list" style={{ listStyle: 'none', margin: 0, padding: 0 }}>
            {snapshots.map((snap) => (
              <li key={snap.snapshotId}>
                <button
                  type="button"
                  data-testid={`firmware-history-item-${snap.snapshotId}`}
                  onClick={() => setSelectedId(snap.snapshotId)}
                  style={{
                    display: 'block',
                    width: '100%',
                    textAlign: 'left',
                    border: 'none',
                    background: selectedId === snap.snapshotId ? t.surface2 : 'transparent',
                    padding: '8px 10px',
                    cursor: 'pointer',
                    color: t.text,
                  }}
                >
                  <div style={{ fontSize: 11, fontWeight: 600 }}>{snap.reason}</div>
                  <div style={{ fontSize: 10, color: t.textMuted }}>
                    {snap.snapshotId.slice(0, 14)}… · {snap.createdAt}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      {selected ? (
        <div
          data-testid="firmware-history-detail"
          style={{
            borderTop: `1px solid ${t.border}`,
            padding: '8px 10px',
            display: 'flex',
            flexDirection: 'column',
            gap: 6,
            maxHeight: '45%',
          }}
        >
          <div style={{ fontSize: 11, color: t.textSec }}>
            {selected.reason} · v{selected.snapshotVersion ?? '?'}
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            <button
              type="button"
              data-testid="firmware-restore-snapshot"
              disabled={busy}
              onClick={() => void restoreSnapshot(selected.snapshotId)}
            >
              Restore
            </button>
            <button
              type="button"
              data-testid="firmware-preview-platformio-ini"
              disabled={busy}
              onClick={() => void previewFile(selected.snapshotId, 'platformio.ini')}
            >
              Preview platformio.ini
            </button>
            <button
              type="button"
              data-testid="firmware-preview-main-cpp"
              disabled={busy}
              onClick={() => void previewFile(selected.snapshotId, 'src/main.cpp')}
            >
              Preview main.cpp
            </button>
          </div>
          {previewPath ? (
            <div data-testid="firmware-snapshot-preview" style={{ minHeight: 120, flex: 1 }}>
              <div style={{ fontSize: 10, color: t.textMuted, marginBottom: 4 }}>{previewPath}</div>
              <FirmwareMonacoEditor
                path={previewPath}
                content={previewContent}
                isDark={isDark}
                readOnly
                onChange={() => undefined}
              />
            </div>
          ) : null}
        </div>
      ) : null}
    </aside>
  );
}
