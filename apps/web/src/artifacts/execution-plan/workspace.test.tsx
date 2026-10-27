import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from '../../../../../packages/contracts/examples/valid/project-initialization-result/project-initialization-result.json';
import App from '../../App';
import { WORKFLOW_GROUPS } from '../registry';

const projectId = fixture.project.projectId;
const content = {
  plan: { steps: [], requirements: [], verificationObjectives: [] },
  configuration: { components: [], i2c: { connectionId: 'i2c', sdaPin: 21, sclPin: 22 }, buildProfileId: 'platformio-arduino-esp32-v1', analysisProfileId: 'python-analysis-v1' },
};
const workspace = { workspaceId: 'ws_plan', artifactId: 'art_plan', baseArtifactVersion: 2, baseProjectStateVersion: fixture.project.currentStateVersion };
const result = { schemaVersion: '1.0.0', commandId: 'cmd_test', commandRunId: 'run_test', projectId, artifactId: 'art_plan', status: 'completed', proposalId: 'prop_plan', startedAt: '2026-10-26T00:00:00Z', outputReferences: [], evidenceReferences: [], issueReferences: [] };

function setup({ loadFailure = false, decisionFailure = false, createFailure = false } = {}) {
  const projectState = structuredClone(fixture);
  const component = projectState.artifacts.find((a) => a.artifactType === 'component-plan')!;
  Object.assign(component.content, { candidates: [
    { candidateId: 'candidate_mcu', componentRoleId: 'role_mcu', specifications: [{ specKey: 'gpio-sda', value: 25 }, { specKey: 'gpio-scl', value: 26 }] },
    { candidateId: 'candidate_imu', componentRoleId: 'role_imu', specifications: [] },
  ] });
  projectState.artifacts.push({ artifactType: 'electrical-architecture', content: {
    nodes: [{ nodeId: 'mcu', componentCandidateId: 'candidate_mcu' }, { nodeId: 'imu', componentCandidateId: 'candidate_imu' }],
    connections: [{ connectionId: 'bus_project', interfaceType: 'i2c', fromNodeId: 'mcu', toNodeId: 'imu' }],
  } } as never);
  const fetchMock = vi.fn(async (input: RequestInfo | URL, ..._options: [RequestInit?]) => {
    const url = String(input);
    let body: unknown = projectState;
    let status = 200;
    if (url.endsWith('/history')) body = { turns: [], workflowRuns: [], artifactRevisions: [], veraResponses: [] };
    else if (url.endsWith('/artifacts/execution-plan')) {
      body = { artifactType: 'execution-plan', artifactVersion: 2, content };
      if (loadFailure) { status = 404; body = { error: { code: 'NOT_FOUND', message: 'No execution plan available.' } }; }
    } else if (url.endsWith('/execution-plan/propose')) {
      body = { content, workspace, commandResult: result };
      if (createFailure) { status = 422; body = { error: { code: 'COMMAND_VALIDATION_FAILED', message: 'Only ESP32-DEVKIT-V1 + MPU6050 materialization is supported.' } }; }
    }
    else if (url.endsWith('/artifact-commands')) {
      body = result;
      if (decisionFailure) { status = 409; body = { error: { code: 'CONFLICT', message: 'Stale plan basis.' } }; }
    }
    return { ok: status === 200, status, text: async () => JSON.stringify(body) };
  });
  vi.stubGlobal('fetch', fetchMock);
  render(<MemoryRouter initialEntries={[`/projects/${projectId}`]}><App /></MemoryRouter>);
  return fetchMock;
}

beforeEach(() => { vi.restoreAllMocks(); });

describe('Execution Plan rail and API integration', () => {
  it.each(['', 'Change the wiring'])('opens the review from FOUNDATION and rejects in one click with reason %j', async (reason) => {
    const user = userEvent.setup();
    const fetchMock = setup();
    expect(WORKFLOW_GROUPS.find((group) => group.label === 'FOUNDATION')?.artifacts).toContain('execution-plan');
    await user.click(await screen.findByRole('button', { name: 'Execution Plan' }));
    expect(await screen.findByRole('region', { name: 'Execution plan review' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Create Execution Plan' })).not.toBeInTheDocument();
    expect(screen.getByTestId('workspace-execution-plan-shell')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Next Action/ })).toBeInTheDocument();
    if (reason) {
      const box = screen.getByRole('textbox', { name: 'Rejection reason (optional)' });
      // jsdom gives every resize handle zero-size bounds, intercepting pointer focus.
      box.focus();
      await user.keyboard(reason);
      expect(screen.getByRole('textbox', { name: 'Rejection reason (optional)' })).toHaveValue(reason);
    }
    await user.click(screen.getByRole('button', { name: 'Reject plan' }));
    expect(await screen.findByText('Plan rejected.')).toBeInTheDocument();
    const commands = fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/artifact-commands'));
    expect(commands).toHaveLength(1);
    expect(JSON.parse(commands[0][1]!.body as string)).toMatchObject({
      commandType: 'artifact.reject-revision', artifactId: 'art_plan', workspaceId: 'ws_plan',
      baseArtifactVersion: 2, baseProjectStateVersion: fixture.project.currentStateVersion,
      input: { proposalId: 'prop_plan', reason: reason || 'rejected' },
    });
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('/materialize'))).toBe(false);
  });

  it('accepts through the typed revision API', async () => {
    const fetchMock = setup();
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Execution Plan' }));
    await user.click(await screen.findByRole('button', { name: 'Accept plan' }));
    expect(await screen.findByText('Plan accepted.')).toBeInTheDocument();
    const command = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/artifact-commands'));
    expect(JSON.parse(command![1]!.body as string).commandType).toBe('artifact.accept-revision');
  });

  it('offers explicit creation only after a missing-plan response', async () => {
    setup({ loadFailure: true });
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Execution Plan' }));
    expect(await screen.findByRole('button', { name: 'Create Execution Plan' })).toBeEnabled();
    expect(screen.queryByRole('button', { name: 'Reject plan' })).not.toBeInTheDocument();
  });

  it('creates a review with project-derived configuration by keyboard, without accepting it', async () => {
    const fetchMock = setup({ loadFailure: true });
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Execution Plan' }));
    const create = await screen.findByRole('button', { name: 'Create Execution Plan' });
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/execution-plan/propose'))).toBe(false);
    create.focus();
    await user.keyboard('{Enter}');
    expect(await screen.findByRole('region', { name: 'Execution plan review' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Create Execution Plan' })).not.toBeInTheDocument();
    const proposal = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/execution-plan/propose'))!;
    expect(JSON.parse(proposal[1]!.body as string)).toMatchObject({
      basePlanVersion: 0, baseProjectStateVersion: fixture.project.currentStateVersion,
      configuration: { components: [
        { candidateId: 'candidate_mcu', componentRoleId: 'role_mcu' },
        { candidateId: 'candidate_imu', componentRoleId: 'role_imu' },
      ], i2c: { connectionId: 'bus_project', sdaPin: 25, sclPin: 26 } },
    });
    await user.click(screen.getByRole('button', { name: 'Accept plan' }));
    expect(await screen.findByText('Plan accepted.')).toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/execution-plan/propose'))).toHaveLength(1);
  });

  it('allows a fresh proposal after rejecting an initial plan', async () => {
    const fetchMock = setup({ loadFailure: true });
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Execution Plan' }));
    await user.click(await screen.findByRole('button', { name: 'Create Execution Plan' }));
    await user.click(await screen.findByRole('button', { name: 'Reject plan' }));
    await user.click(await screen.findByRole('button', { name: 'Create Execution Plan' }));
    expect(await screen.findByRole('button', { name: 'Accept plan' })).toBeEnabled();
    expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/execution-plan/propose'))).toHaveLength(2);
  });

  it('surfaces unsupported project configuration and allows an explicit retry', async () => {
    const fetchMock = setup({ loadFailure: true, createFailure: true });
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Execution Plan' }));
    await user.click(await screen.findByRole('button', { name: 'Create Execution Plan' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Only ESP32-DEVKIT-V1 + MPU6050');
    expect(screen.getByRole('button', { name: 'Create Execution Plan' })).toBeEnabled();
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/artifact-commands'))).toBe(false);
  });

  it('shows conflicts and permits retry without creating a second proposal', async () => {
    const fetchMock = setup({ decisionFailure: true });
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Execution Plan' }));
    await user.click(await screen.findByRole('button', { name: 'Reject plan' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Stale plan basis.');
    await waitFor(() => expect(screen.getByRole('button', { name: 'Reject plan' })).toBeEnabled());
    await user.click(screen.getByRole('button', { name: 'Reject plan' }));
    await waitFor(() => expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/artifact-commands'))).toHaveLength(2));
    expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/execution-plan/propose'))).toHaveLength(1);
  });
});
