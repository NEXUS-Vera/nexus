import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { AnalysisOutputPanel } from './AnalysisOutputPanel';

vi.mock('../../api/client', () => ({
  getExecution: vi.fn(async () => ({
    executionRun: {
      executionRunId: 'run_1',
      status: 'completed',
      runtimeIdentity: { runtimeKind: 'process', securityLevel: 'limited' },
    },
  })),
  getExecutionLogs: vi.fn(async () => ({
    chunks: [{ sequence: 1, stream: 'stdout', content: 'SUCCESS\n' }],
    logTruncated: false,
  })),
  listProducedOutputs: vi.fn(async () => [
    {
      outputId: 'out_json',
      executionRunId: 'run_1',
      name: 'outputs/summary.json',
      outputType: 'structured-result',
    },
    {
      outputId: 'out_csv',
      executionRunId: 'run_1',
      name: 'outputs/processed.csv',
      outputType: 'structured-result',
    },
    {
      outputId: 'out_png',
      executionRunId: 'run_1',
      name: 'outputs/accel_plot.png',
      outputType: 'file-reference',
    },
  ]),
  previewAnalysisOutput: vi.fn(async (_projectId: string, outputId: string) => {
    if (outputId === 'out_json') {
      return { previewKind: 'json', text: '{"status":"ok"}', name: 'outputs/summary.json' };
    }
    if (outputId === 'out_csv') {
      return {
        previewKind: 'csv',
        text: 'time_s,accel_x\n0,0.1\n1,0.2\n',
        name: 'outputs/processed.csv',
      };
    }
    return {
      previewKind: 'image-png',
      contentBase64: 'iVBORw0KGgo=',
      name: 'outputs/accel_plot.png',
    };
  }),
  compareAnalysisOutputs: vi.fn(async () => ({
    comparisons: [{ name: 'outputs/summary.json', status: 'match' }],
  })),
  cancelExecution: vi.fn(async () => ({
    executionRun: { executionRunId: 'run_1', status: 'cancelled' },
  })),
}));

describe('AnalysisOutputPanel', () => {
  it('renders logs, outputs, runtime identity, and previews', async () => {
    render(
      <AnalysisOutputPanel
        projectId="proj_1"
        isDark={false}
        session={{
          executionRunId: 'run_1',
          operation: 'run',
          executionSnapshotId: 'snap_abc',
          baselineExecutionRunId: 'run_0',
        }}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId('analysis-output-panel')).toBeTruthy();
    });
    expect(screen.getByTestId('execution-status')).toBeTruthy();
    expect(screen.getByTestId('runtime-identity')).toBeTruthy();
    expect(screen.getByTestId('analysis-run-snapshot')).toBeTruthy();
    expect(screen.getByTestId('analysis-produced-outputs')).toBeTruthy();

    fireEvent.click(screen.getByTestId('analysis-output-out_json'));
    await waitFor(() => {
      expect(screen.getByTestId('analysis-preview-json')).toBeTruthy();
    });

    fireEvent.click(screen.getByTestId('analysis-output-out_csv'));
    await waitFor(() => {
      expect(screen.getByTestId('analysis-preview-csv')).toBeTruthy();
    });

    fireEvent.click(screen.getByTestId('analysis-output-out_png'));
    await waitFor(() => {
      expect(screen.getByTestId('analysis-preview-png')).toBeTruthy();
    });

    await waitFor(() => {
      expect(screen.getByTestId('analysis-hash-comparisons')).toBeTruthy();
    });
  });
});
