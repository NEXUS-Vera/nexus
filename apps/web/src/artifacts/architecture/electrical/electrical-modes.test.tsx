import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import {
  getCircuitSimulationPreview,
  getCircuitSimulationSupport,
  getProducedOutput,
  listExecutions,
  listProducedOutputs,
} from '../../../api/client';
import { ElectricalModeTabs } from './ElectricalModeTabs';
import { ElectricalSimulationView } from './simulation/ElectricalSimulationView';

vi.mock('../../../api/client', () => ({
  ApiClientError: class ApiClientError extends Error {
    status = 500;
    body = null;
  },
  getCircuitSimulationSupport: vi.fn(),
  getCircuitSimulationPreview: vi.fn(),
  listExecutions: vi.fn(),
  listProducedOutputs: vi.fn(),
  getProducedOutput: vi.fn(),
  validateCircuitSimulation: vi.fn(),
  getCircuitSimulationExportUrl: vi.fn(() => '/export'),
}));

describe('ElectricalModeTabs', () => {
  it('switches design and simulation modes', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<ElectricalModeTabs mode="design" isDark={false} onChange={onChange} />);
    await user.click(screen.getByTestId('electrical-mode-simulation'));
    expect(onChange).toHaveBeenCalledWith('simulation');
  });
});

describe('ElectricalSimulationView states', () => {
  it('renders unsupported state without a misleading run affordance', async () => {
    vi.mocked(getCircuitSimulationSupport).mockResolvedValue({
      schemaVersion: '1.0.0',
      projectId: 'proj_1',
      artifactId: 'art_1',
      providerAvailability: {
        providerId: 'wokwi',
        status: 'READY',
        available: true,
        lintAvailable: true,
      },
      assessment: {
        schemaVersion: '1.0.0',
        capabilityId: 'circuit-simulation',
        providerId: 'wokwi',
        status: 'UNSUPPORTED',
        firmwareRequired: false,
        surrogateUsed: false,
        findings: [
          {
            findingId: 'f1',
            reasonCode: 'UNMAPPED_COMPONENT',
            message: 'FX-ENV-100 has no simulation model mapped',
            mappingType: 'unsupported',
          },
        ],
      },
    });
    vi.mocked(getCircuitSimulationPreview).mockRejectedValue(new Error('unsupported'));
    vi.mocked(listExecutions).mockResolvedValue([]);
    vi.mocked(listProducedOutputs).mockResolvedValue([]);

    render(
      <ElectricalSimulationView
        projectId="proj_1"
        isDark={false}
        onRunSimulation={async () => undefined}
      />,
    );

    expect(await screen.findByTestId('simulation-unsupported-state')).toBeInTheDocument();
    expect(screen.getByTestId('run-circuit-simulation')).toBeDisabled();
  });

  it('renders surrogate-ready mapping preview and serial output', async () => {
    vi.mocked(getCircuitSimulationSupport).mockResolvedValue({
      schemaVersion: '1.0.0',
      projectId: 'proj_1',
      artifactId: 'art_1',
      providerAvailability: {
        providerId: 'wokwi',
        status: 'READY',
        available: true,
        lintAvailable: true,
      },
      assessment: {
        schemaVersion: '1.0.0',
        capabilityId: 'circuit-simulation',
        providerId: 'wokwi',
        status: 'SUPPORTED',
        firmwareRequired: false,
        surrogateUsed: true,
        findings: [],
      },
    });
    vi.mocked(getCircuitSimulationPreview).mockResolvedValue({
      schemaVersion: '1.0.0',
      providerId: 'wokwi',
      status: 'SUPPORTED',
      surrogateUsed: true,
      mappings: [
        {
          providerPartId: 'esp',
          providerPartType: 'board-esp32-devkit-c-v4',
          mappingType: 'surrogate',
          pinProfile: [{ sourcePin: '21', providerPin: 'D21' }],
          sourceReferences: [{ entityType: 'component-candidate', displayLabel: 'FX-MCU-32' }],
        },
        {
          providerPartId: 'imu',
          providerPartType: 'wokwi-mpu6050',
          mappingType: 'surrogate',
          pinProfile: [{ sourcePin: 'SDA', providerPin: 'SDA' }],
          sourceReferences: [{ entityType: 'component-candidate', displayLabel: 'FX-IMU-200' }],
        },
      ],
      connections: [
        {
          id: 'c1',
          sourcePartId: 'esp',
          targetPartId: 'imu',
          sourcePin: 'D21',
          targetPin: 'SDA',
          label: 'I2C',
        },
      ],
      findings: [],
    });
    vi.mocked(listExecutions).mockResolvedValue([
      {
        schemaVersion: '1.0.0',
        executionRunId: 'exec_1',
        projectId: 'proj_1',
        artifactId: 'art_1',
        capability: 'circuit-simulation',
        providerId: 'wokwi',
        status: 'succeeded',
        startedAt: '2026-08-10T10:00:00Z',
        completedAt: '2026-08-10T10:00:05Z',
        baseArtifactVersion: 1,
      } as never,
    ]);
    vi.mocked(listProducedOutputs).mockResolvedValue([
      {
        schemaVersion: '1.0.0',
        outputId: 'out_1',
        projectId: 'proj_1',
        artifactId: 'art_1',
        workspaceId: 'ws_1',
        executionRunId: 'exec_1',
        outputType: 'log',
        name: 'serial.log',
        mediaType: 'text/plain',
        contentDigest: 'sha',
        createdAt: '2026-08-10T10:00:05Z',
        evidenceStatus: 'unverified',
        supports: [],
        content: {
          kind: 'inline-structured',
          structuredResult: { text: 'NEXUS_WOKWI_READY\n' },
        },
      } as never,
    ]);
    vi.mocked(getProducedOutput).mockResolvedValue({
      schemaVersion: '1.0.0',
      outputId: 'out_1',
      projectId: 'proj_1',
      artifactId: 'art_1',
      workspaceId: 'ws_1',
      executionRunId: 'exec_1',
      outputType: 'log',
      name: 'serial.log',
      mediaType: 'text/plain',
      contentDigest: 'sha',
      createdAt: '2026-08-10T10:00:05Z',
      evidenceStatus: 'unverified',
      supports: [],
      content: {
        kind: 'inline-structured',
        structuredResult: { text: 'NEXUS_WOKWI_READY\n' },
      },
    } as never);

    render(
      <ElectricalSimulationView
        projectId="proj_1"
        isDark={false}
        currentArtifactVersion={1}
        onRunSimulation={async () => undefined}
      />,
    );

    expect(await screen.findByTestId('simulation-visual-graph')).toBeInTheDocument();
    expect(screen.getByText(/Surrogate hardware/i)).toBeInTheDocument();
    expect(await screen.findByTestId('simulation-serial-output')).toHaveTextContent(
      'NEXUS_WOKWI_READY',
    );
    expect(screen.getByTestId('run-circuit-simulation')).not.toBeDisabled();
  });
});
