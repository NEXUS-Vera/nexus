/**
 * Data view — engineering inputs with provenance (not a second catalog).
 */
import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { readWorkspaceRuntimeFile } from '../../api/client';
import { themeColors } from '../../lib/theme';
import type { WorkspaceFileMeta } from '../firmware/file-tree';

type Props = {
  projectId: string;
  isDark: boolean;
  files: WorkspaceFileMeta[];
  uploadSlot: ReactNode;
  onOpenPath?: (path: string) => void;
};

type CsvMeta = {
  columns: string[];
  rowCount: number;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function estimateCsvMeta(text: string): CsvMeta {
  const lines = text.split(/\r?\n/).filter((line) => line.length > 0);
  if (lines.length === 0) return { columns: [], rowCount: 0 };
  const columns = lines[0].split(',').map((c) => c.trim()).filter(Boolean);
  return { columns, rowCount: Math.max(0, lines.length - 1) };
}

export function AnalysisDataView({
  projectId,
  isDark,
  files,
  uploadSlot,
  onOpenPath,
}: Props) {
  const t = themeColors(isDark);
  const dataFiles = useMemo(
    () => files.filter((f) => f.path === 'data' || f.path.startsWith('data/')),
    [files],
  );
  const [selected, setSelected] = useState<string | null>(null);
  const [csvMeta, setCsvMeta] = useState<CsvMeta | null>(null);
  const [previewText, setPreviewText] = useState<string | null>(null);
  const [contentHash, setContentHash] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!selected && dataFiles.length > 0) {
      setSelected(dataFiles[0].path);
    }
  }, [dataFiles, selected]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!selected) {
        setCsvMeta(null);
        setPreviewText(null);
        setContentHash(null);
        return;
      }
      setError(null);
      try {
        const payload = await readWorkspaceRuntimeFile(projectId, 'analysis', selected);
        if (cancelled) return;
        const content = typeof payload.content === 'string' ? payload.content : '';
        setPreviewText(content.slice(0, 4000));
        const mediaType = typeof payload.mediaType === 'string' ? payload.mediaType : '';
        setCsvMeta(
          selected.endsWith('.csv') || mediaType.includes('csv')
            ? estimateCsvMeta(content)
            : null,
        );
        const hash =
          (isRecord(payload) && typeof payload.contentHash === 'string' && payload.contentHash) ||
          (isRecord(payload) && typeof payload.contentDigest === 'string' && payload.contentDigest) ||
          null;
        setContentHash(hash);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to inspect data file');
          setCsvMeta(null);
          setPreviewText(null);
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [projectId, selected]);

  const selectedMeta = dataFiles.find((f) => f.path === selected) ?? null;

  return (
    <div
      data-testid="analysis-data-view"
      style={{ flex: 1, display: 'flex', minHeight: 0, overflow: 'hidden' }}
    >
      <aside
        style={{
          width: 260,
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
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
            color: t.textMuted,
            borderBottom: `1px solid ${t.border}`,
          }}
        >
          Inputs ({dataFiles.length})
        </div>
        <div style={{ padding: 10, borderBottom: `1px solid ${t.border}` }}>{uploadSlot}</div>
        <ul style={{ listStyle: 'none', margin: 0, padding: 8, overflow: 'auto', flex: 1 }}>
          {dataFiles.length === 0 ? (
            <li data-testid="analysis-data-empty" style={{ color: t.textMuted, fontSize: 12, padding: 8 }}>
              No analysis inputs yet
            </li>
          ) : (
            dataFiles.map((file) => (
              <li key={file.path}>
                <button
                  type="button"
                  data-testid={`analysis-data-file-${file.path}`}
                  onClick={() => setSelected(file.path)}
                  style={{
                    width: '100%',
                    textAlign: 'left',
                    border: 'none',
                    background: selected === file.path ? t.cobaltSelected : 'transparent',
                    color: t.text,
                    borderRadius: 6,
                    padding: '8px 10px',
                    cursor: 'pointer',
                    fontSize: 12,
                  }}
                >
                  {file.path.replace(/^data\//, '')}
                </button>
              </li>
            ))
          )}
        </ul>
      </aside>
      <section style={{ flex: 1, overflow: 'auto', padding: 16, minWidth: 0 }}>
        {!selectedMeta ? (
          <div style={{ color: t.textMuted, fontSize: 13 }}>
            Upload a CSV/JSON dataset or import a ProducedOutput to begin.
          </div>
        ) : (
          <div data-testid="analysis-data-detail">
            <h3 style={{ margin: '0 0 8px', color: t.text, fontSize: 16 }}>
              {selectedMeta.path.replace(/^data\//, '')}
            </h3>
            <div style={{ fontSize: 12, color: t.textSec, display: 'grid', gap: 4 }}>
              <div>
                Path: <code>{selectedMeta.path}</code>
              </div>
              <div data-testid="analysis-data-source">
                Source:{' '}
                {selectedMeta.origin === 'GENERATED' ||
                selectedMeta.origin === 'PRODUCED_OUTPUT' ||
                selectedMeta.origin === 'produced-output'
                  ? 'ProducedOutput / imported'
                  : selectedMeta.origin === 'USER' || selectedMeta.origin === 'UPLOAD'
                    ? selectedMeta.path.includes('stationary_imu')
                      ? 'Fixture dataset'
                      : 'User upload'
                    : selectedMeta.origin === 'FIXTURE'
                      ? 'Fixture dataset'
                      : selectedMeta.origin ?? 'Workspace file'}
              </div>
              <div>Media type: {selectedMeta.mediaType ?? '—'}</div>
              <div>
                Size:{' '}
                {typeof selectedMeta.sizeBytes === 'number'
                  ? `${selectedMeta.sizeBytes} bytes`
                  : '—'}
              </div>
              <div data-testid="analysis-data-hash">Hash: {contentHash ?? '—'}</div>
              {csvMeta ? (
                <>
                  <div data-testid="analysis-data-rows">Rows: {csvMeta.rowCount}</div>
                  <div data-testid="analysis-data-columns">
                    Columns: {csvMeta.columns.join(', ') || '—'}
                  </div>
                </>
              ) : null}
            </div>
            {error ? (
              <div style={{ color: '#b91c1c', marginTop: 12, fontSize: 12 }}>{error}</div>
            ) : null}
            {previewText ? (
              <pre
                data-testid="analysis-data-preview"
                style={{
                  marginTop: 14,
                  padding: 10,
                  borderRadius: 8,
                  border: `1px solid ${t.border}`,
                  background: t.bg,
                  fontSize: 11,
                  overflow: 'auto',
                  maxHeight: 280,
                }}
              >
                {previewText}
              </pre>
            ) : null}
            {onOpenPath ? (
              <button
                type="button"
                style={{ marginTop: 12 }}
                onClick={() => onOpenPath(selectedMeta.path)}
              >
                Open in Code
              </button>
            ) : null}
          </div>
        )}
      </section>
    </div>
  );
}
