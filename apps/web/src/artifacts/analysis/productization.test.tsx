import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AnalysisWorkspace } from './workspace';
import { AnalysisResultsView } from './AnalysisResultsView';
import { parseInvestigation } from './modes';
import { WORKFLOW_GROUPS, ARTIFACT_REGISTRY, ARTIFACT_ORDER } from '../registry';

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

describe('Analysis productization', () => {
  beforeEach(() => {
    vi.stubGlobal('confirm', vi.fn(() => true));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('keeps exactly one Analysis nav entry', () => {
    const build = WORKFLOW_GROUPS.find((g) => g.label === 'BUILD');
    expect(build?.artifacts.filter((k) => ARTIFACT_REGISTRY[k].label === 'Analysis')).toEqual([
      'analysis',
    ]);
    expect(ARTIFACT_ORDER.filter((k) => k === 'analysis')).toHaveLength(1);
  });

  it('parses exploration investigation with no requirement links', () => {
    const parsed = parseInvestigation({
      schemaVersion: '1.0.0',
      title: 'Explore stationary IMU behavior',
      purpose: 'exploration',
      question: 'What patterns exist in the stationary MPU6050 dataset?',
      linkedRequirementIds: [],
      linkedComponentIds: [],
      linkedTestPlanIds: [],
      linkedEvidenceIds: [],
      lifecycleStage: 'INPUTS',
    });
    expect(parsed?.purpose).toBe('exploration');
    expect(parsed?.linkedRequirementIds).toEqual([]);
  });

  it('defaults to Results empty state and opens Code on demand', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method ?? 'GET').toUpperCase();
      if (url.includes('/workspace/runtime') && method === 'GET') {
        return jsonResponse({
          binding: {
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
      if (url.includes('nexus/investigation.json')) {
        return jsonResponse({ error: { code: 'NOT_FOUND', message: 'missing' } }, 404);
      }
      return jsonResponse({ error: { code: 'NOT_FOUND', message: url } }, 404);
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<AnalysisWorkspace projectId="proj_abcdefghijklmnop" isDark={false} />);
    await waitFor(() => expect(screen.getByTestId('analysis-results-empty')).toBeInTheDocument());
    expect(screen.getByTestId('analysis-mode-results')).toHaveAttribute('aria-selected', 'true');
    fireEvent.click(screen.getByTestId('analysis-mode-code'));
    await waitFor(() => expect(screen.getByTestId('analysis-editor-empty')).toBeInTheDocument());
    expect(screen.getByTestId('analysis-create-toggle')).toBeInTheDocument();
  });

  it('renders golden verification Results with deterministic PASS', async () => {
    const summary = {
      accel_x_rms_noise_g: 0.015676464092948383,
      threshold_g: 0.1,
      operator: '<',
      assessment: 'PASS',
      authority: 'deterministic-code',
      metricId: 'accel_x_rms_noise_g',
      requirementId: 'R7',
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/executions/') && url.includes('/logs')) {
        return jsonResponse({ chunks: [], logTruncated: false });
      }
      if (url.includes('/executions/')) {
        return jsonResponse({
          executionRun: {
            schemaVersion: '1.0.0',
            executionRunId: 'exec_golden',
            status: 'completed',
            runtimeIdentity: { runtimeKind: 'process', runtimeVersion: '1' },
          },
        });
      }
      if (url.includes('/preview') && url.includes('out_summary')) {
        return jsonResponse({
          previewKind: 'json',
          text: JSON.stringify(summary),
          name: 'outputs/summary.json',
        });
      }
      if (url.includes('/preview') && url.includes('out_plot')) {
        return jsonResponse({
          previewKind: 'image-png',
          contentBase64: 'iVBORw0KGgo=',
          name: 'outputs/accel_plot.png',
        });
      }
      if (url.includes('/preview') && url.includes('out_csv')) {
        return jsonResponse({
          previewKind: 'csv',
          text: 'time_s,accel_x_g\n0.0,0.01\n0.02,0.02\n',
          name: 'outputs/processed.csv',
        });
      }
      if (url.includes('/outputs') && !url.includes('/preview')) {
        return jsonResponse({
          items: [
            {
              outputId: 'out_summary',
              executionRunId: 'exec_golden',
              name: 'outputs/summary.json',
            },
            {
              outputId: 'out_plot',
              executionRunId: 'exec_golden',
              name: 'outputs/accel_plot.png',
            },
            {
              outputId: 'out_csv',
              executionRunId: 'exec_golden',
              name: 'outputs/processed.csv',
            },
          ],
        });
      }
      return jsonResponse({ error: { code: 'NOT_FOUND', message: url } }, 404);
    });
    vi.stubGlobal('fetch', fetchMock);

    render(
      <AnalysisResultsView
        projectId="proj_abcdefghijklmnop"
        isDark={false}
        investigation={{
          title: 'IMU Stationary Noise Verification',
          purpose: 'verification',
          question: 'Does stationary MPU6050 accel_x RMS noise satisfy R7?',
          linkedRequirementIds: ['R7'],
          linkedComponentIds: ['MPU6050'],
          linkedTestPlanIds: [],
          linkedEvidenceIds: [],
          lifecycleStage: 'VERIFY',
          stageVocabulary: ['INPUTS', 'TRANSFORM', 'METRICS', 'VISUALIZATION', 'VERIFY'],
          verificationCriterion: {
            metricId: 'accel_x_rms_noise_g',
            operator: '<',
            threshold: 0.1,
            unit: 'g',
          },
        }}
        session={{
          executionRunId: 'exec_golden',
          executionSnapshotId: 'snap_golden',
          operation: 'run',
        }}
        hasCode
        hasData
        onRunCurrent={() => undefined}
        onOpenCode={() => undefined}
        onOpenData={() => undefined}
      />,
    );

    await waitFor(() =>
      expect(screen.getByTestId('analysis-assessment-value')).toHaveTextContent('PASS'),
    );
    expect(screen.getByTestId('analysis-investigation-title')).toHaveTextContent(
      'IMU Stationary Noise Verification',
    );
    expect(screen.getByTestId('analysis-investigation-links')).toHaveTextContent('R7');
    expect(screen.getByTestId('analysis-assessment-authority')).toHaveTextContent(/Deterministic/i);
    expect(screen.getByTestId('analysis-metric-row')).toHaveTextContent(/0\.0157/);
    expect(screen.getByTestId('analysis-metric-row')).toHaveTextContent(/0\.1/);
    expect(screen.getByTestId('analysis-preview-png')).toBeInTheDocument();
    expect(screen.getByTestId('analysis-preview-csv')).toBeInTheDocument();
    expect(screen.getByTestId('analysis-finding')).toBeInTheDocument();
  });

  it('renders exploration header without inventing requirement links', () => {
    render(
      <AnalysisResultsView
        projectId="proj_abcdefghijklmnop"
        isDark={false}
        investigation={{
          title: 'Explore stationary IMU behavior',
          purpose: 'exploration',
          question: 'What patterns exist in the stationary MPU6050 dataset?',
          linkedRequirementIds: [],
          linkedComponentIds: [],
          linkedTestPlanIds: [],
          linkedEvidenceIds: [],
          lifecycleStage: 'INPUTS',
          stageVocabulary: ['INPUTS', 'TRANSFORM', 'METRICS', 'VISUALIZATION', 'VERIFY'],
        }}
        session={null}
        hasCode
        hasData
        onRunCurrent={() => undefined}
        onOpenCode={() => undefined}
        onOpenData={() => undefined}
      />,
    );
    expect(screen.getByTestId('analysis-investigation-links')).toHaveTextContent(
      'No linked requirement',
    );
    expect(screen.getByTestId('analysis-investigation-purpose')).toHaveTextContent('Exploration');
    expect(screen.getByTestId('analysis-stage-INPUTS')).toBeInTheDocument();
  });

  it('renders INCONCLUSIVE when verification metric is missing', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/logs')) return jsonResponse({ chunks: [], logTruncated: false });
      if (url.includes('/executions/')) {
        return jsonResponse({
          executionRun: {
            schemaVersion: '1.0.0',
            executionRunId: 'exec_missing',
            status: 'completed',
          },
        });
      }
      if (url.includes('/preview')) {
        return jsonResponse({
          previewKind: 'json',
          text: JSON.stringify({
            assessment: 'INCONCLUSIVE',
            reason: 'Expected metric accel_x_rms_noise_g was not produced.',
          }),
          name: 'outputs/summary.json',
        });
      }
      if (url.includes('/outputs')) {
        return jsonResponse({
          items: [
            {
              outputId: 'out_summary',
              executionRunId: 'exec_missing',
              name: 'outputs/summary.json',
            },
          ],
        });
      }
      return jsonResponse({ error: { code: 'NOT_FOUND', message: url } }, 404);
    });
    vi.stubGlobal('fetch', fetchMock);
    render(
      <AnalysisResultsView
        projectId="proj_abcdefghijklmnop"
        isDark={false}
        investigation={{
          title: 'IMU Stationary Noise Verification',
          purpose: 'verification',
          linkedRequirementIds: ['R7'],
          linkedComponentIds: [],
          linkedTestPlanIds: [],
          linkedEvidenceIds: [],
          verificationCriterion: {
            metricId: 'accel_x_rms_noise_g',
            operator: '<',
            threshold: 0.1,
            unit: 'g',
          },
        }}
        session={{ executionRunId: 'exec_missing', operation: 'run' }}
        hasCode
        hasData
        onRunCurrent={() => undefined}
        onOpenCode={() => undefined}
        onOpenData={() => undefined}
      />,
    );
    await waitFor(() =>
      expect(screen.getByTestId('analysis-assessment-value')).toHaveTextContent('INCONCLUSIVE'),
    );
    expect(screen.getByTestId('analysis-assessment-inconclusive-reason')).toHaveTextContent(
      /Expected metric/,
    );
  });

  it('opens Data and History modes from Analysis workspace', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method ?? 'GET').toUpperCase();
      if (url.includes('/workspace/runtime') && method === 'GET') {
        return jsonResponse({
          binding: {
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
        return jsonResponse({
          files: [
            {
              path: 'analysis.py',
              sizeBytes: 100,
              mediaType: 'text/x-python',
              origin: 'GENERATED',
            },
            {
              path: 'data/stationary_imu.csv',
              sizeBytes: 4000,
              mediaType: 'text/csv',
              origin: 'USER',
            },
          ],
        });
      }
      if (url.includes('nexus/investigation.json')) {
        return jsonResponse({
          content: JSON.stringify({
            title: 'IMU Stationary Noise Verification',
            purpose: 'verification',
            linkedRequirementIds: ['R7'],
            linkedComponentIds: ['MPU6050'],
            lifecycleStage: 'VERIFY',
          }),
        });
      }
      if (url.includes('stationary_imu.csv')) {
        return jsonResponse({
          content:
            'time_s,accel_x_g,accel_y_g,accel_z_g\n' +
            Array.from({ length: 200 }, (_, i) => `${(i * 0.02).toFixed(2)},0.01,0.02,1.0`).join(
              '\n',
            ),
          contentHash: 'sha256:fixture',
          mediaType: 'text/csv',
        });
      }
      if (url.includes('/snapshots')) {
        return jsonResponse({
          snapshots: [
            {
              snapshotId: 'snap_before_run',
              reason: 'before-analysis-run',
              createdAt: '2026-01-01T00:00:00Z',
              snapshotVersion: 2,
              createdBy: { displayName: 'User' },
            },
          ],
        });
      }
      if (url.includes('/outputs')) {
        return jsonResponse({ items: [] });
      }
      return jsonResponse({ error: { code: 'NOT_FOUND', message: url } }, 404);
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<AnalysisWorkspace projectId="proj_abcdefghijklmnop" isDark={false} />);
    await waitFor(() => expect(screen.getByTestId('analysis-mode-results')).toBeInTheDocument());

    fireEvent.click(screen.getByTestId('analysis-mode-data'));
    await waitFor(() => expect(screen.getByTestId('analysis-data-view')).toBeInTheDocument());
    await waitFor(() => expect(screen.getByTestId('analysis-data-rows')).toHaveTextContent('200'));
    expect(screen.getByTestId('analysis-data-columns')).toHaveTextContent('time_s');
    expect(screen.getByTestId('analysis-data-hash')).toHaveTextContent('sha256:fixture');

    fireEvent.click(screen.getByTestId('analysis-mode-history'));
    await waitFor(() => expect(screen.getByTestId('analysis-history-list')).toBeInTheDocument());
    expect(screen.getByText('Before analysis run')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('analysis-mode-code'));
    await waitFor(() => expect(screen.getByTestId('analysis-monaco-editor')).toBeInTheDocument());
  });
});
