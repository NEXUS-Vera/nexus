import { useState } from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type {
  Artifact,
  ArtifactCommandResult,
  ProducedOutput,
  WorkspaceDescriptor,
} from '@nexus/contracts';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import electricalFixture from '../../../../../packages/contracts/examples/valid/phase-13-electrical-architecture/electrical-architecture-artifact.json';
import { getWorkspace, listProducedOutputs, submitArtifactCommand } from '../../api/client';
import { ArchitectureWorkspace } from './workspace';

vi.mock('../../api/client', () => ({
  ApiClientError: class ApiClientError extends Error {
    status = 500;
    body = null;
  },
  createWorkspace: vi.fn(),
  ensureLayeredArchitecture: vi.fn(),
  getWorkspace: vi.fn(),
  submitArtifactCommand: vi.fn(),
  getCircuitSimulationSupport: vi.fn(),
  getCircuitSimulationPreview: vi.fn(),
  listExecutions: vi.fn(),
  listProducedOutputs: vi.fn(),
  getProducedOutput: vi.fn(),
  validateCircuitSimulation: vi.fn(),
  getCircuitSimulationExportUrl: vi.fn(() => '/export'),
}));

vi.mock('./electrical/simulation/ElectricalSimulationView', () => ({
  ElectricalSimulationView: ({
    onRunSimulation,
  }: {
    onRunSimulation: () => Promise<void>;
  }) => {
    const [error, setError] = useState<string | null>(null);
    return (
      <>
        <button
          type="button"
          onClick={() => void onRunSimulation().catch((err: Error) => setError(err.message))}
        >
          Test run simulation
        </button>
        {error && <div role="alert">{error}</div>}
      </>
    );
  },
}));

vi.mock('./electrical/ElectricalGraphCanvas', () => ({
  ElectricalGraphCanvas: () => <div data-testid="electrical-graph-canvas" />,
}));

vi.mock('../../lib/engineering-graph/EngineeringGraphCanvas', () => ({
  EngineeringGraphCanvas: () => <div data-testid="graph-canvas" />,
}));

const artifact = electricalFixture as unknown as Extract<
  Artifact,
  { artifactType: 'electrical-architecture' }
>;

const workspace = {
  schemaVersion: '1.0.0',
  workspaceId: 'workspace_1',
  projectId: artifact.projectId,
  artifactId: artifact.artifactId,
  artifactType: 'electrical-architecture',
  baseArtifactVersion: artifact.artifactVersion,
  baseProjectStateVersion: 3,
  status: 'active',
  createdAt: '2026-08-08T10:00:00Z',
  updatedAt: '2026-08-08T10:00:00Z',
} as unknown as WorkspaceDescriptor;

function result(
  commandId: string,
  overrides: Partial<ArtifactCommandResult> = {},
): ArtifactCommandResult {
  return {
    schemaVersion: '1.0.0',
    commandId,
    commandRunId: `run_${commandId}`,
    projectId: artifact.projectId,
    artifactId: artifact.artifactId,
    status: 'completed',
    startedAt: '2026-08-08T10:00:00Z',
    completedAt: '2026-08-08T10:00:01Z',
    evidenceReferences: [],
    issueReferences: [],
    outputReferences: [],
    ...overrides,
  };
}

describe('architecture circuit simulation command flow', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(getWorkspace).mockResolvedValue(workspace);
    vi.mocked(listProducedOutputs).mockResolvedValue([
      { outputId: 'out_bin0000000000000', name: '.pio/build/nexus/firmware.bin' },
      { outputId: 'out_log0000000000000', name: 'serial.log' },
      { outputId: 'out_elf0000000000000', name: '.pio/build/nexus/firmware.elf' },
    ] as ProducedOutput[]);
    vi.mocked(submitArtifactCommand)
      .mockResolvedValueOnce(
        result('lease', {
          resultPayload: {
            editLease: {
              leaseToken: 'lease-token',
            },
          },
        }),
      )
      .mockResolvedValueOnce(result('snapshot', { snapshotId: 'snapshot_1' }))
      .mockResolvedValueOnce(result('execute', { executionRunId: 'execution_1' }))
      .mockResolvedValue(result('release'));
  });

  it.each([false, true])(
    'snapshots and submits the newest firmware ELF and current readiness marker (rebuild: %s)',
    async (rebuild) => {
      if (rebuild) {
        vi.mocked(listProducedOutputs).mockResolvedValue([
          { outputId: 'out_stale', name: '.pio/build/nexus/firmware.elf' },
          { outputId: 'out_elf0000000000000', name: '.pio/build/nexus/firmware.elf' },
          { outputId: 'out_log', name: 'serial.log' },
        ] as ProducedOutput[]);
      }
      const user = userEvent.setup();
      const { unmount } = render(
        <ArchitectureWorkspace
          projectId={artifact.projectId}
          viewId="electrical"
          artifact={artifact}
          isDark={false}
          electricalMode="simulation"
        />,
      );

      await user.click(screen.getByRole('button', { name: 'Test run simulation' }));
      await waitFor(() => expect(submitArtifactCommand).toHaveBeenCalledTimes(3));

      expect(listProducedOutputs).toHaveBeenCalledWith(artifact.projectId);
      const commands = vi.mocked(submitArtifactCommand).mock.calls.map((call) => call[1]);
      expect(commands[0]).toMatchObject({
        commandType: 'workspace.acquire-edit-lease',
        workspaceId: workspace.workspaceId,
      });
      expect(commands[1]).toMatchObject({
        commandType: 'workspace.create-snapshot',
        workspaceId: workspace.workspaceId,
      });
      expect(commands[2]).toMatchObject({
        commandType: 'artifact.execute',
        input: {
          snapshotId: 'snapshot_1',
          capability: 'circuit-simulation',
          executionMode: 'simulate',
          firmwareOutputId: 'out_elf0000000000000',
          expectedText: 'NEXUS_MPU_READY',
        },
      });
      expect(commands.some((command) => command.commandType === 'artifact.propose-revision')).toBe(
        false,
      );
      unmount();
      expect(submitArtifactCommand).toHaveBeenLastCalledWith(
        artifact.projectId,
        expect.objectContaining({ commandType: 'workspace.release-edit-lease' }),
      );
    },
  );

  it('shows the build message without acquiring a lease or submitting commands when no ELF exists', async () => {
    vi.mocked(listProducedOutputs).mockResolvedValue([
      { outputId: 'out_bin', name: '.pio/build/nexus/firmware.bin' },
    ] as ProducedOutput[]);
    const user = userEvent.setup();
    render(
      <ArchitectureWorkspace
        projectId={artifact.projectId}
        viewId="electrical"
        artifact={artifact}
        isDark={false}
        electricalMode="simulation"
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Test run simulation' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Build firmware before running circuit simulation.',
    );
    expect(listProducedOutputs).toHaveBeenCalledWith(artifact.projectId);
    expect(submitArtifactCommand).not.toHaveBeenCalled();
  });
});
