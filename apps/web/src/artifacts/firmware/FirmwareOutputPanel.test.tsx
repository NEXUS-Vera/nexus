import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FirmwareOutputPanel } from './FirmwareOutputPanel';

vi.mock('../../api/client', () => ({
  getExecution: vi.fn(),
  getExecutionLogs: vi.fn(),
  cancelExecution: vi.fn(),
  listProducedOutputs: vi.fn(),
}));

import {
  cancelExecution,
  getExecution,
  getExecutionLogs,
  listProducedOutputs,
} from '../../api/client';

describe('FirmwareOutputPanel', () => {
  it('renders incremental logs, diagnostics, outputs, and runtime identity', async () => {
    const openFile = vi.fn();
    vi.mocked(getExecution)
      .mockResolvedValueOnce({
        executionRun: {
          schemaVersion: '1.0.0',
          executionRunId: 'run1',
          projectId: 'proj',
          status: 'running',
        },
      } as never)
      .mockResolvedValueOnce({
        executionRun: {
          schemaVersion: '1.0.0',
          executionRunId: 'run1',
          projectId: 'proj',
          status: 'completed',
          runtimeIdentity: {
            runtimeKind: 'process',
            securityLevel: 'limited',
          },
        },
      } as never);
    vi.mocked(getExecutionLogs)
      .mockResolvedValueOnce({
        chunks: [
          {
            sequence: 1,
            stream: 'stdout',
            content: 'src/main.cpp:4:5: error: expected ; before }',
          },
        ],
      } as never)
      .mockResolvedValueOnce({
        chunks: [{ sequence: 2, stream: 'stdout', content: 'done' }],
      } as never);
    vi.mocked(listProducedOutputs).mockResolvedValue([
      {
        outputId: 'out1',
        executionRunId: 'run1',
        name: 'firmware.elf',
        sizeBytes: 123,
        contentHash: 'sha256:abc',
      },
    ] as never);
    vi.mocked(cancelExecution).mockResolvedValue({} as never);

    render(
      <FirmwareOutputPanel
        projectId="proj"
        isDark={false}
        session={{
          executionRunId: 'run1',
          operation: 'compile',
          toolchainMode: 'fixture',
          executionSnapshotId: 'snap123456789',
        }}
        onClear={() => {}}
        onOpenFile={openFile}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId('firmware-output-panel')).toBeInTheDocument();
      expect(screen.getByText(/Fixture execution.*no real build evidence/)).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText(/src\/main.cpp:4:5 error/i)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId('firmware-diagnostic-0'));
    expect(openFile).toHaveBeenCalledWith('src/main.cpp', 4);
    await waitFor(() => {
      expect(screen.getByTestId('firmware-produced-outputs')).toBeInTheDocument();
    });
  });

  it('cancels a running execution', async () => {
    vi.mocked(getExecution).mockResolvedValue({
      executionRun: {
        schemaVersion: '1.0.0',
        executionRunId: 'run2',
        projectId: 'proj',
        status: 'running',
      },
    } as never);
    vi.mocked(getExecutionLogs).mockResolvedValue({ chunks: [] } as never);
    vi.mocked(listProducedOutputs).mockResolvedValue([] as never);
    vi.mocked(cancelExecution).mockResolvedValue({} as never);

    render(
      <FirmwareOutputPanel
        projectId="proj"
        isDark={false}
        session={{ executionRunId: 'run2', operation: 'test' }}
        onClear={() => {}}
      />,
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));
    await waitFor(() => {
      expect(cancelExecution).toHaveBeenCalledWith('proj', 'run2');
    });
  });
});
