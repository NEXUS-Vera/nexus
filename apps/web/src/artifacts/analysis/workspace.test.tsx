import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AnalysisWorkspace } from './workspace';

vi.mock('@monaco-editor/react', () => ({
  default: ({
    value,
    onChange,
    path,
  }: {
    value: string;
    onChange?: (value: string | undefined) => void;
    path?: string;
  }) => (
    <textarea
      data-testid="analysis-monaco-editor"
      data-path={path}
      value={value}
      onChange={(event) => onChange?.(event.target.value)}
    />
  ),
}));

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  } as Response;
}

describe('AnalysisWorkspace', () => {
  beforeEach(() => {
    vi.stubGlobal('confirm', vi.fn(() => true));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('loads empty workspace state into Results, then Code empty panel', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method ?? 'GET').toUpperCase();

      if (url.includes('/workspace/runtime') && method === 'GET') {
        return jsonResponse({
          binding: {
            schemaVersion: '1.0.0',
            projectId: 'proj_abcdefghijklmnop',
            artifactId: 'art_analysis',
            artifactType: 'analysis',
            workspaceId: 'ws_analysis',
            baseArtifactVersion: 1,
            baseProjectStateVersion: 1,
            capabilities: { filesystem: true },
            filesystemEnabled: true,
          },
          draft: { draftVersion: 1 },
        });
      }

      if (url.includes('/workspace/files') && method === 'GET') {
        return jsonResponse({ files: [] });
      }

      return jsonResponse({ error: { code: 'NOT_FOUND', message: url } }, 404);
    });

    vi.stubGlobal('fetch', fetchMock);
    render(<AnalysisWorkspace projectId="proj_abcdefghijklmnop" isDark={false} />);

    await waitFor(() => expect(screen.getByTestId('analysis-workspace')).toBeInTheDocument());
    expect(screen.getByTestId('analysis-results-empty')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('analysis-mode-code'));
    await waitFor(() => expect(screen.getByTestId('analysis-editor-empty')).toBeInTheDocument());
    expect(screen.getByTestId('analysis-create-toggle')).toBeInTheDocument();
  });

  it('creates a file, edits it, saves, and clears dirty state', async () => {
    const draftVersion = { current: 1 };
    const files = new Map<string, string>();
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method ?? 'GET').toUpperCase();

      if (url.includes('/workspace/runtime') && method === 'GET') {
        return jsonResponse({
          binding: {
            schemaVersion: '1.0.0',
            projectId: 'proj_abcdefghijklmnop',
            artifactId: 'art_analysis',
            artifactType: 'analysis',
            workspaceId: 'ws_analysis',
            baseArtifactVersion: 1,
            baseProjectStateVersion: 1,
            capabilities: { filesystem: true, execution: true, snapshots: true },
            filesystemEnabled: true,
          },
          draft: { draftVersion: draftVersion.current },
        });
      }

      if (url.includes('/workspace/files') && method === 'GET') {
        return jsonResponse({
          files: [...files.keys()].map((path) => ({ path, sizeBytes: files.get(path)?.length ?? 0 })),
        });
      }

      if (url.includes('/artifact-commands') && method === 'POST') {
        const body = JSON.parse(String(init?.body ?? '{}')) as { commandType: string };
        if (body.commandType === 'workspace.acquire-edit-lease') {
          return jsonResponse({
            status: 'accepted',
            resultPayload: { editLease: { leaseToken: 'tok_test' } },
          });
        }
        return jsonResponse({ status: 'accepted' });
      }

      if (url.includes('/workspace/file') && method === 'PUT') {
        const body = JSON.parse(String(init?.body ?? '{}')) as {
          path: string;
          content: string;
          expectedDraftVersion: number;
          baseArtifactVersion: number;
          baseProjectStateVersion: number;
          requestedBy: { actorId: string };
        };
        expect(body.expectedDraftVersion).toBe(draftVersion.current);
        files.set(body.path, body.content);
        draftVersion.current += 1;
        return jsonResponse({
          draft: { draftVersion: draftVersion.current },
          workspace: { baseArtifactVersion: 1, baseProjectStateVersion: 1 },
          file: { path: body.path },
        });
      }

      if (url.includes('/workspace/file') && method === 'GET') {
        const path = new URL(url).searchParams.get('path') ?? '';
        return jsonResponse({
          encoding: 'utf-8',
          content: files.get(path) ?? '',
          sizeBytes: (files.get(path) ?? '').length,
        });
      }

      return jsonResponse({ error: { code: 'NOT_FOUND', message: url } }, 404);
    });

    vi.stubGlobal('fetch', fetchMock);
    render(<AnalysisWorkspace projectId="proj_abcdefghijklmnop" isDark={false} />);
    await waitFor(() => screen.getByTestId('analysis-mode-code'));
    fireEvent.click(screen.getByTestId('analysis-mode-code'));
    await waitFor(() => screen.getByTestId('analysis-create-toggle'));

    fireEvent.click(screen.getByTestId('analysis-create-toggle'));
    fireEvent.change(screen.getByTestId('analysis-create-path'), {
      target: { value: 'src/analysis.py' },
    });
    fireEvent.click(screen.getByTestId('analysis-create-submit'));

    await waitFor(() => expect(screen.getByTestId('analysis-monaco-editor')).toBeInTheDocument());
    fireEvent.change(screen.getByTestId('analysis-monaco-editor'), {
      target: { value: 'print(\"hi\")\\n' },
    });
    expect(screen.getByTestId('analysis-dirty-src/analysis.py')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('analysis-save'));
    await waitFor(() => {
      expect(files.get('src/analysis.py')).toBe('print(\"hi\")\\n');
      expect(screen.queryByTestId('analysis-dirty-src/analysis.py')).not.toBeInTheDocument();
    });
  });

  it('shows controlled unsupported preview for binary content', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method ?? 'GET').toUpperCase();

      if (url.includes('/workspace/runtime') && method === 'GET') {
        return jsonResponse({
          binding: {
            schemaVersion: '1.0.0',
            projectId: 'proj_abcdefghijklmnop',
            artifactId: 'art_analysis',
            artifactType: 'analysis',
            workspaceId: 'ws_analysis',
            baseArtifactVersion: 1,
            baseProjectStateVersion: 1,
            capabilities: { filesystem: true },
            filesystemEnabled: true,
          },
          draft: { draftVersion: 1 },
        });
      }
      if (url.includes('/workspace/files') && method === 'GET') {
        return jsonResponse({ files: [{ path: 'data.parquet', sizeBytes: 4 }] });
      }
      if (url.includes('/workspace/file') && method === 'GET') {
        return jsonResponse({
          encoding: 'base64',
          contentBase64: 'AAAA',
          sizeBytes: 4,
        });
      }
      return jsonResponse({ error: { code: 'NOT_FOUND', message: url } }, 404);
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<AnalysisWorkspace projectId="proj_abcdefghijklmnop" isDark={false} />);

    await waitFor(() => screen.getByTestId('analysis-mode-code'));
    fireEvent.click(screen.getByTestId('analysis-mode-code'));
    await waitFor(() => screen.getByTestId('analysis-tree-file-data.parquet'));
    fireEvent.click(screen.getByTestId('analysis-tree-file-data.parquet'));
    await waitFor(() => expect(screen.getByTestId('analysis-unsupported-preview')).toBeInTheDocument());
  });
});

