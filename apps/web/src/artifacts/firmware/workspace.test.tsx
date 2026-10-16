import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { FirmwareWorkspace } from './workspace';

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
      data-testid="firmware-monaco-editor"
      data-path={path}
      value={value}
      onChange={(event) => onChange?.(event.target.value)}
    />
  ),
  DiffEditor: ({
    original,
    modified,
    path,
  }: {
    original: string;
    modified: string;
    path?: string;
  }) => (
    <div data-testid="firmware-diff-monaco" data-path={path}>
      <pre data-testid="firmware-diff-original">{original}</pre>
      <pre data-testid="firmware-diff-modified">{modified}</pre>
    </div>
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

describe('FirmwareWorkspace', () => {
  beforeEach(() => {
    vi.stubGlobal('confirm', vi.fn(() => true));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('loads binding, empty tree, creates/opens/edits/saves/deletes through Phase 14 APIs', async () => {
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
            artifactId: 'art_firmware',
            artifactType: 'firmware',
            workspaceId: 'ws_firmware',
            baseArtifactVersion: 1,
            baseProjectStateVersion: 1,
            capabilities: {
              filesystem: true,
              snapshots: true,
              execution: true,
              logs: true,
            },
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

      if (url.includes('/workspace/file') && method === 'GET') {
        const path = new URL(url).searchParams.get('path') ?? '';
        return jsonResponse({
          encoding: 'utf-8',
          content: files.get(path) ?? '',
          sizeBytes: (files.get(path) ?? '').length,
        });
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
        expect(body.baseArtifactVersion).toBe(1);
        expect(body.baseProjectStateVersion).toBe(1);
        expect(body.requestedBy.actorId).toBe('user_local');
        files.set(body.path, body.content);
        draftVersion.current += 1;
        return jsonResponse({
          draft: { draftVersion: draftVersion.current },
          workspace: {
            baseArtifactVersion: 1,
            baseProjectStateVersion: 1,
          },
          file: { path: body.path },
        });
      }

      if (url.includes('/workspace/file') && method === 'DELETE') {
        const parsed = new URL(url);
        const path = parsed.searchParams.get('path') ?? '';
        expect(parsed.searchParams.get('actorId')).toBe('user_local');
        expect(Number(parsed.searchParams.get('expectedDraftVersion'))).toBe(draftVersion.current);
        files.delete(path);
        draftVersion.current += 1;
        return jsonResponse({
          draft: { draftVersion: draftVersion.current },
          workspace: {
            baseArtifactVersion: 1,
            baseProjectStateVersion: 1,
          },
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

      return jsonResponse({ error: { code: 'NOT_FOUND', message: url } }, 404);
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<FirmwareWorkspace projectId="proj_abcdefghijklmnop" isDark={false} />);

    await waitFor(() => {
      expect(screen.getByTestId('firmware-workspace')).toBeInTheDocument();
    });
    expect(screen.getByTestId('firmware-file-tree-empty')).toBeInTheDocument();
    expect(screen.getByTestId('firmware-editor-empty')).toHaveTextContent(/empty/i);
    expect(screen.getByTestId('firmware-generate-scaffold')).toBeInTheDocument();
    expect(screen.getByTestId('firmware-generate-scaffold-empty')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('firmware-create-toggle'));
    fireEvent.change(screen.getByTestId('firmware-create-path'), {
      target: { value: 'src/main.cpp' },
    });
    fireEvent.click(screen.getByTestId('firmware-create-submit'));

    await waitFor(() => {
      expect(screen.getByTestId('firmware-tree-file-src/main.cpp')).toBeInTheDocument();
    });
    expect(files.get('src/main.cpp')).toBe('');

    fireEvent.click(screen.getByTestId('firmware-tree-file-src/main.cpp'));
    await waitFor(() => {
      expect(screen.getByTestId('firmware-monaco-editor')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId('firmware-monaco-editor'), {
      target: { value: 'int main() { return 0; }\n' },
    });
    expect(screen.getByTestId('firmware-dirty-src/main.cpp')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('firmware-save'));
    await waitFor(() => {
      expect(files.get('src/main.cpp')).toBe('int main() { return 0; }\n');
    });
    await waitFor(() => {
      expect(screen.queryByTestId('firmware-dirty-src/main.cpp')).not.toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('firmware-delete'));
    await waitFor(() => {
      expect(files.has('src/main.cpp')).toBe(false);
    });
    await waitFor(() => {
      expect(screen.getByTestId('firmware-file-tree-empty')).toBeInTheDocument();
    });
  });

  it('surfaces lease errors without silent overwrite', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method ?? 'GET').toUpperCase();
      if (url.includes('/workspace/runtime')) {
        return jsonResponse({
          binding: {
            schemaVersion: '1.0.0',
            projectId: 'proj_abcdefghijklmnop',
            artifactId: 'art_firmware',
            artifactType: 'firmware',
            workspaceId: 'ws_firmware',
            baseArtifactVersion: 1,
            baseProjectStateVersion: 1,
            capabilities: { filesystem: true },
            filesystemEnabled: true,
          },
          draft: { draftVersion: 1 },
        });
      }
      if (url.includes('/workspace/files')) {
        return jsonResponse({ files: [{ path: 'a.txt', sizeBytes: 1 }] });
      }
      if (url.includes('/workspace/file') && method === 'GET') {
        return jsonResponse({ encoding: 'utf-8', content: 'a', sizeBytes: 1 });
      }
      if (url.includes('/artifact-commands')) {
        return jsonResponse(
          {
            error: {
              code: 'DRAFT_EDIT_LEASE_HELD',
              message: 'Lease held by another editor',
            },
          },
          409,
        );
      }
      if (url.includes('/workspace/file') && method === 'PUT') {
        throw new Error('should not write without lease');
      }
      return jsonResponse({}, 404);
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<FirmwareWorkspace projectId="proj_abcdefghijklmnop" isDark={false} />);
    await waitFor(() => screen.getByTestId('firmware-tree-file-a.txt'));
    fireEvent.click(screen.getByTestId('firmware-tree-file-a.txt'));
    await waitFor(() => screen.getByTestId('firmware-monaco-editor'));
    fireEvent.change(screen.getByTestId('firmware-monaco-editor'), {
      target: { value: 'changed' },
    });
    fireEvent.click(screen.getByTestId('firmware-save'));
    await waitFor(() => {
      expect(screen.getByTestId('firmware-status-banner')).toHaveTextContent(/lease/i);
    });
  });

  it('shows unsupported preview for binary payloads', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/workspace/runtime')) {
        return jsonResponse({
          binding: {
            schemaVersion: '1.0.0',
            projectId: 'proj_abcdefghijklmnop',
            artifactId: 'art_firmware',
            artifactType: 'firmware',
            workspaceId: 'ws_firmware',
            baseArtifactVersion: 1,
            baseProjectStateVersion: 1,
            capabilities: { filesystem: true },
            filesystemEnabled: true,
          },
          draft: { draftVersion: 1 },
        });
      }
      if (url.includes('/workspace/files')) {
        return jsonResponse({ files: [{ path: 'blob.bin', sizeBytes: 4 }] });
      }
      if (url.includes('/workspace/file')) {
        return jsonResponse({
          encoding: 'base64',
          contentBase64: 'AAAA',
          sizeBytes: 4,
        });
      }
      return jsonResponse({}, 404);
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<FirmwareWorkspace projectId="proj_abcdefghijklmnop" isDark={false} />);
    await waitFor(() => screen.getByTestId('firmware-tree-file-blob.bin'));
    fireEvent.click(screen.getByTestId('firmware-tree-file-blob.bin'));
    await waitFor(() => {
      expect(screen.getByTestId('firmware-unsupported-preview')).toBeInTheDocument();
    });
  });

  it('generates firmware scaffold through the scaffold API', async () => {
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
            artifactId: 'art_firmware',
            artifactType: 'firmware',
            workspaceId: 'ws_firmware',
            baseArtifactVersion: 1,
            baseProjectStateVersion: 1,
            capabilities: { filesystem: true },
            filesystemEnabled: true,
          },
          draft: { draftVersion: draftVersion.current },
        });
      }
      if (url.includes('/workspace/files') && method === 'GET') {
        return jsonResponse({
          files: [...files.keys()].map((path) => ({
            path,
            sizeBytes: files.get(path)?.length ?? 0,
          })),
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
      if (url.includes('/workspace/scaffold') && method === 'POST') {
        const body = JSON.parse(String(init?.body ?? '{}')) as {
          expectedDraftVersion: number;
          baseArtifactVersion: number;
          baseProjectStateVersion: number;
        };
        expect(body.expectedDraftVersion).toBe(draftVersion.current);
        expect(body.baseArtifactVersion).toBe(1);
        expect(body.baseProjectStateVersion).toBe(1);
        files.set(
          'platformio.ini',
          '[env:nexus]\nplatform = espressif32\nboard = esp32dev\nframework = arduino\nmonitor_speed = 115200\n',
        );
        files.set(
          'src/main.cpp',
          '#include <Arduino.h>\n\nvoid setup() {\n    Serial.begin(115200);\n}\n\nvoid loop() {\n}\n',
        );
        draftVersion.current += 2;
        return jsonResponse({
          status: 'generated',
          generationId: 'gen_testscaffold0001',
          generationKind: 'scaffold',
          primaryPath: 'src/main.cpp',
          generatedFiles: [
            { path: 'platformio.ini', contentHash: 'sha256:aa' },
            { path: 'src/main.cpp', contentHash: 'sha256:bb' },
          ],
          draft: { draftVersion: draftVersion.current },
          workspace: {
            baseArtifactVersion: 1,
            baseProjectStateVersion: 1,
          },
          binding: {
            schemaVersion: '1.0.0',
            projectId: 'proj_abcdefghijklmnop',
            artifactId: 'art_firmware',
            artifactType: 'firmware',
            workspaceId: 'ws_firmware',
            baseArtifactVersion: 1,
            baseProjectStateVersion: 1,
            capabilities: { filesystem: true },
            filesystemEnabled: true,
          },
        });
      }
      if (url.includes('/artifact-commands') && method === 'POST') {
        return jsonResponse({
          status: 'accepted',
          resultPayload: { editLease: { leaseToken: 'tok_test' } },
        });
      }
      return jsonResponse({ error: { code: 'NOT_FOUND', message: url } }, 404);
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<FirmwareWorkspace projectId="proj_abcdefghijklmnop" isDark={false} />);
    await waitFor(() => screen.getByTestId('firmware-generate-scaffold-empty'));
    fireEvent.click(screen.getByTestId('firmware-generate-scaffold-empty'));

    await waitFor(() => {
      expect(screen.getByTestId('firmware-tree-file-platformio.ini')).toBeInTheDocument();
      expect(screen.getByTestId('firmware-tree-file-src/main.cpp')).toBeInTheDocument();
    });
    await waitFor(() => {
      const editor = screen.getByTestId('firmware-monaco-editor') as HTMLTextAreaElement;
      expect(editor.value).toContain('Serial.begin(115200)');
    });
  });

  it('proposes, previews, applies, and surfaces stale patch conflicts', async () => {
    const draftVersion = { current: 1 };
    const files = new Map<string, string>([
      ['platformio.ini', 'monitor_speed = 115200\n'],
      ['src/main.cpp', '#include <Arduino.h>\n'],
    ]);
    let staleApply = false;

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method ?? 'GET').toUpperCase();

      if (url.includes('/workspace/runtime') && method === 'GET') {
        return jsonResponse({
          binding: {
            schemaVersion: '1.0.0',
            projectId: 'proj_abcdefghijklmnop',
            artifactId: 'art_firmware',
            artifactType: 'firmware',
            workspaceId: 'ws_firmware',
            baseArtifactVersion: 1,
            baseProjectStateVersion: 1,
            capabilities: { filesystem: true },
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
      if (url.includes('/workspace/file') && method === 'GET') {
        const path = new URL(url).searchParams.get('path') ?? '';
        return jsonResponse({
          encoding: 'utf-8',
          content: files.get(path) ?? '',
          sizeBytes: (files.get(path) ?? '').length,
        });
      }
      if (url.includes('/workspace/patch/propose') && method === 'POST') {
        return jsonResponse({
          status: 'proposed',
          proposal: {
            proposalId: 'fwpatch_test000000000001',
            baseSnapshotId: 'snap_test000000000001',
            requestedChange: 'Change serial baud to 9600.',
            status: 'proposed',
            operations: [
              {
                operationType: 'replace-file',
                path: 'platformio.ini',
                expectedBaseHash: 'sha256:abc',
                content: 'monitor_speed = 9600\n',
                contentHash: 'sha256:def',
              },
            ],
          },
        });
      }
      if (url.includes('/workspace/patch/apply') && method === 'POST') {
        if (staleApply) {
          return jsonResponse(
            {
              error: {
                code: 'FIRMWARE_PATCH_STALE',
                message: 'Workspace content changed since proposal base',
              },
            },
            409,
          );
        }
        const body = JSON.parse(String(init?.body ?? '{}')) as { proposalId: string };
        expect(body.proposalId).toBe('fwpatch_test000000000001');
        files.set('platformio.ini', 'monitor_speed = 9600\n');
        draftVersion.current += 1;
        return jsonResponse({
          status: 'applied',
          draft: { draftVersion: draftVersion.current },
          workspace: { baseArtifactVersion: 1, baseProjectStateVersion: 1 },
        });
      }
      if (url.includes('/workspace/patch/discard') && method === 'POST') {
        return jsonResponse({ status: 'discarded' });
      }
      if (url.includes('/artifact-commands') && method === 'POST') {
        return jsonResponse({
          status: 'accepted',
          resultPayload: { editLease: { leaseToken: 'tok_test' } },
        });
      }
      return jsonResponse({ error: { code: 'NOT_FOUND', message: url } }, 404);
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<FirmwareWorkspace projectId="proj_abcdefghijklmnop" isDark={false} />);
    await waitFor(() => screen.getByTestId('firmware-patch-toggle'));
    fireEvent.click(screen.getByTestId('firmware-patch-toggle'));
    fireEvent.change(screen.getByTestId('firmware-patch-request'), {
      target: { value: 'Change serial baud to 9600.' },
    });
    fireEvent.click(screen.getByTestId('firmware-patch-propose'));

    await waitFor(() => screen.getByTestId('firmware-patch-summary'));
    expect(screen.getByTestId('firmware-patch-operations')).toHaveTextContent('replace-file');
    expect(screen.getByTestId('firmware-diff-host')).toBeInTheDocument();
    expect(screen.getByTestId('firmware-diff-modified')).toHaveTextContent('9600');

    fireEvent.click(screen.getByTestId('firmware-patch-apply'));
    await waitFor(() => {
      expect(files.get('platformio.ini')).toBe('monitor_speed = 9600\n');
    });

    staleApply = true;
    fireEvent.click(screen.getByTestId('firmware-patch-toggle'));
    fireEvent.change(screen.getByTestId('firmware-patch-request'), {
      target: { value: 'Change serial baud to 9600.' },
    });
    fireEvent.click(screen.getByTestId('firmware-patch-propose'));
    await waitFor(() => screen.getByTestId('firmware-patch-apply'));
    fireEvent.click(screen.getByTestId('firmware-patch-apply'));
    await waitFor(() => {
      expect(screen.getByTestId('firmware-status-banner')).toHaveTextContent(/stale/i);
    });
  });

  it('blocks compile when workspace is dirty and starts output panel when clean', async () => {
    const draftVersion = { current: 1 };
    const files = new Map<string, string>([
      ['platformio.ini', '[env:nexus]\n'],
      ['src/main.cpp', 'void setup() {}\n'],
    ]);
    let runStatus = 'running';
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method ?? 'GET').toUpperCase();

      if (url.includes('/workspace/runtime') && method === 'GET') {
        return jsonResponse({
          binding: {
            schemaVersion: '1.0.0',
            projectId: 'proj_abcdefghijklmnop',
            artifactId: 'art_firmware',
            artifactType: 'firmware',
            workspaceId: 'ws_firmware',
            baseArtifactVersion: 1,
            baseProjectStateVersion: 1,
            capabilities: { filesystem: true, execution: true, logs: true },
            filesystemEnabled: true,
          },
          draft: { draftVersion: draftVersion.current },
        });
      }
      if (url.includes('/workspace/files')) {
        return jsonResponse({
          files: [...files.keys()].map((path) => ({ path, sizeBytes: files.get(path)?.length ?? 0 })),
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
      if (url.includes('/workspace/file') && method === 'PUT') {
        const body = JSON.parse(String(init?.body ?? '{}')) as {
          path: string;
          content: string;
        };
        files.set(body.path, body.content);
        draftVersion.current += 1;
        return jsonResponse({
          draft: { draftVersion: draftVersion.current },
          workspace: { baseArtifactVersion: 1, baseProjectStateVersion: 1 },
          file: { path: body.path },
        });
      }
      if (url.includes('/workspace/compile') && method === 'POST') {
        return jsonResponse({
          operation: 'firmware.compile',
          executionSnapshotId: 'snap_compile000001',
          executionRun: {
            schemaVersion: '1.0.0',
            executionRunId: 'run_compile000001',
            projectId: 'proj_abcdefghijklmnop',
            status: 'running',
          },
        });
      }
      if (url.includes('/executions/run_compile000001') && method === 'GET' && !url.includes('/logs')) {
        return jsonResponse({
          executionRun: {
            schemaVersion: '1.0.0',
            executionRunId: 'run_compile000001',
            projectId: 'proj_abcdefghijklmnop',
            status: runStatus,
            runtimeIdentity: { runtimeKind: 'process' },
          },
        });
      }
      if (url.includes('/executions/run_compile000001/logs')) {
        return jsonResponse({
          chunks: [
            {
              schemaVersion: '1.0.0',
              sequence: 1,
              stream: 'stdout',
              content: 'src/main.cpp:1:1: warning: unused function\nSUCCESS\n',
            },
          ],
        });
      }
      if (url.includes('/outputs')) {
        return jsonResponse({ items: [] });
      }
      if (url.includes('/artifact-commands') && method === 'POST') {
        return jsonResponse({
          status: 'accepted',
          resultPayload: { editLease: { leaseToken: 'tok_test' } },
        });
      }
      return jsonResponse({ error: { code: 'NOT_FOUND', message: url } }, 404);
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<FirmwareWorkspace projectId="proj_abcdefghijklmnop" isDark={false} />);
    await waitFor(() => screen.getByTestId('firmware-tree-file-src/main.cpp'));
    fireEvent.click(screen.getByTestId('firmware-tree-file-src/main.cpp'));
    await waitFor(() => screen.getByTestId('firmware-monaco-editor'));
    fireEvent.change(screen.getByTestId('firmware-monaco-editor'), {
      target: { value: 'void setup() { Serial.begin(115200); }\n' },
    });

    expect(screen.getByTestId('firmware-compile')).toBeDisabled();
    expect(screen.getByTestId('firmware-dirty-src/main.cpp')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('firmware-save'));
    await waitFor(() => {
      expect(screen.getByTestId('firmware-compile')).not.toBeDisabled();
    });

    runStatus = 'completed';
    fireEvent.click(screen.getByTestId('firmware-compile'));
    await waitFor(() => {
      expect(screen.getByTestId('firmware-output-panel')).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByTestId('firmware-diagnostics')).toBeInTheDocument();
    });
  });
});
