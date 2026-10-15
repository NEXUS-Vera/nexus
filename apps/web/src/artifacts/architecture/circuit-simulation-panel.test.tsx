import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ExecutionRun, ProducedOutput } from '@nexus/contracts';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  getCircuitSimulationSupport,
  listExecutions,
  listProducedOutputs,
  type CircuitSimulationSupportResponse,
  validateCircuitSimulation,
} from '../../api/client';
import { CircuitSimulationPanel } from './circuit-simulation-panel';

vi.mock('../../api/client', () => ({
  ApiClientError: class ApiClientError extends Error {},
  getCircuitSimulationExportUrl: (projectId: string) =>
    `http://api.test/v1/projects/${projectId}/artifacts/electrical-architecture/circuit-simulation/export`,
  getCircuitSimulationSupport: vi.fn(),
  listExecutions: vi.fn(),
  listProducedOutputs: vi.fn(),
  validateCircuitSimulation: vi.fn(),
}));

const readySupport: CircuitSimulationSupportResponse = {
  schemaVersion: '1.0.0',
  projectId: 'proj_1',
  artifactId: 'artifact_electrical',
  providerAvailability: {
    providerId: 'wokwi',
    status: 'READY',
    available: true,
    lintAvailable: true,
    message: 'Provider is healthy.',
  },
  assessment: {
    schemaVersion: '1.0.0',
    capabilityId: 'circuit-simulation',
    providerId: 'wokwi',
    status: 'SURROGATE_REQUIRED',
    firmwareRequired: false,
    surrogateUsed: true,
    findings: [
      {
        findingId: 'finding_1',
        mappingType: 'surrogate',
        message: 'Temperature sensor uses a provider surrogate.',
        reasonCode: 'SURROGATE',
      },
    ],
    mappings: [],
  },
};

const run = {
  schemaVersion: '1.0.0',
  executionRunId: 'run_1',
  executionRequestId: 'request_1',
  projectId: 'proj_1',
  artifactId: 'artifact_electrical',
  workspaceId: 'workspace_1',
  inputSnapshotId: 'snapshot_1',
  baseArtifactVersion: 1,
  baseProjectStateVersion: 1,
  capability: 'circuit-simulation',
  providerId: 'wokwi',
  status: 'completed',
  startedAt: '2026-08-08T10:00:00Z',
  completedAt: '2026-08-08T10:00:01Z',
  outputReferences: ['output_1'],
  evidenceReferences: [],
} as ExecutionRun;

const output = {
  schemaVersion: '1.0.0',
  outputId: 'output_1',
  projectId: 'proj_1',
  artifactId: 'artifact_electrical',
  workspaceId: 'workspace_1',
  executionRunId: 'run_1',
  outputType: 'log',
  name: 'Serial log',
  mediaType: 'text/plain',
  contentDigest: 'sha256:test',
  createdAt: '2026-08-08T10:00:01Z',
  evidenceStatus: 'tested',
  supports: [],
  content: { kind: 'inline-structured', structuredResult: { text: 'NEXUS_WOKWI_READY' } },
} as ProducedOutput;

const workspaceOutput = {
  ...output,
  outputId: 'output_2',
  outputType: 'file-reference',
  name: 'provider-workspace-manifest',
  mediaType: 'application/json',
} as ProducedOutput;

describe('CircuitSimulationPanel', () => {
  beforeEach(() => {
    vi.mocked(getCircuitSimulationSupport).mockResolvedValue(readySupport);
    vi.mocked(listExecutions).mockResolvedValue([run]);
    vi.mocked(listProducedOutputs).mockResolvedValue([output, workspaceOutput]);
    vi.mocked(validateCircuitSimulation).mockResolvedValue({
      ok: true,
      findings: [],
      workspaceDigest: 'sha256:workspace',
    });
  });

  it('shows health, surrogate disclosure, findings, and fidelity limits', async () => {
    render(
      <CircuitSimulationPanel projectId="proj_1" isDark={false} onRunSimulation={vi.fn()} />,
    );

    expect(await screen.findByText(/Provider: READY/i)).toBeInTheDocument();
    expect(screen.getByText(/Surrogate model is being used/i)).toBeInTheDocument();
    expect(screen.getByText(/Temperature sensor uses a provider surrogate/i)).toBeInTheDocument();
    expect(screen.getByText(/does not verify real component compatibility/i)).toBeInTheDocument();
  });

  it('disables simulation when firmware is required', async () => {
    vi.mocked(getCircuitSimulationSupport).mockResolvedValue({
      ...readySupport,
      assessment: {
        ...readySupport.assessment,
        status: 'FIRMWARE_REQUIRED',
        firmwareRequired: true,
        surrogateUsed: false,
      },
    });
    render(
      <CircuitSimulationPanel projectId="proj_1" isDark={false} onRunSimulation={vi.fn()} />,
    );

    await screen.findByText(/Firmware: required/i);
    expect(screen.getByTestId('run-circuit-simulation')).toBeDisabled();
  });

  it('runs when ready and exposes validation, outputs, and export', async () => {
    const user = userEvent.setup();
    const onRunSimulation = vi.fn().mockResolvedValue(undefined);
    vi.mocked(getCircuitSimulationSupport).mockResolvedValue({
      ...readySupport,
      assessment: {
        ...readySupport.assessment,
        status: 'SUPPORTED',
        firmwareRequired: false,
        surrogateUsed: false,
        findings: [],
      },
    });
    render(
      <CircuitSimulationPanel
        projectId="proj_1"
        isDark={false}
        onRunSimulation={onRunSimulation}
      />,
    );

    const runButton = await screen.findByTestId('run-circuit-simulation');
    await waitFor(() => expect(runButton).toBeEnabled());
    await user.click(runButton);
    expect(onRunSimulation).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole('button', { name: /validate representation/i }));
    expect(await screen.findByTestId('simulation-validation-result')).toHaveTextContent(
      /passed/i,
    );

    await user.click(screen.getByRole('button', { name: /inspect outputs/i }));
    expect(screen.getByTestId('simulation-outputs')).toHaveTextContent('Serial log');
    expect(screen.getByRole('link', { name: /export workspace/i })).toHaveAttribute(
      'href',
      expect.stringContaining('/circuit-simulation/export'),
    );
  });
});
