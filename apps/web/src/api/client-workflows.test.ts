import { afterEach, describe, expect, it, vi } from 'vitest';
import * as api from './client';

const actor = { schemaVersion: '1.0.0', actorId: 'actor_02USERACTOR000000000000001', actorType: 'user' } as const;
const projectId = 'proj_02PHASE11PROJ000000000001';
const content: api.ExecutionPlanArtifact['content'] = {
  configuration: {
    analysisProfileId: 'python-analysis-v1', buildProfileId: 'platformio-arduino-esp32-v1',
    components: [{ candidateId: 'esp32', componentRoleId: 'mcu' }, { candidateId: 'mpu6050', componentRoleId: 'imu' }],
    i2c: { connectionId: 'i2c', sdaPin: 21, sclPin: 22 },
  },
  plan: {
    schemaVersion: '1.0.0', status: 'proposed', basisProjectStateVersion: 1,
    sourceArtifacts: [{ artifactId: 'requirements', artifactVersion: 1 }],
    requirements: [{ artifactId: 'requirements', entityId: 'R7' }], assumptions: [], components: [], interfaces: [], openDecisionIds: [],
    workspaces: [{ artifactType: 'firmware', availability: 'planned', workspaceKey: 'firmware' }],
    verificationObjectives: [{ objectiveId: 'noise', requirementId: 'R7', method: 'analysis', acceptanceCriteria: ['RMS < 0.1 g'], workspaceKey: 'firmware' }],
    steps: [{ stepId: 'compile', title: 'Compile firmware', dependsOn: [], objectiveIds: ['noise'], requiresApproval: true, workspaceKeys: ['firmware'] }],
  },
};
const artifact: api.ExecutionPlanArtifact = {
  schemaVersion: '1.0.0', artifactType: 'execution-plan', artifactId: 'art_plan', artifactVersion: 1,
  projectId, content, contentSchemaVersion: '1.0.0', approvalStatus: 'awaiting-user', lifecycleStatus: 'ready', evidenceStatus: 'unverified',
  createdAt: '2026-10-24T12:00:00Z', updatedAt: '2026-10-24T12:00:00Z', createdBy: actor, sourceTurnId: 'turn_init', workflowRunId: 'wf_init',
};
const result: import('@nexus/contracts').ArtifactCommandResult = {
  schemaVersion: '1.0.0', commandId: 'cmd_02PHASE11CMD00000000000001', commandRunId: 'cmdrun_review', status: 'completed',
  projectId, artifactId: artifact.artifactId, proposalId: 'prop_plan', startedAt: artifact.createdAt,
  outputReferences: [], evidenceReferences: [], issueReferences: [],
};
const decision: api.RevisionDecision = {
  schemaVersion: '1.0.0', commandId: result.commandId, requestedAt: artifact.createdAt, requestedBy: actor,
  workspaceId: 'ws_plan', artifactId: artifact.artifactId, baseArtifactVersion: 1, baseProjectStateVersion: 1, proposalId: 'prop_plan',
};
const repair: api.RepairState = {
  schemaVersion: '1.0.0', repairId: 'repair_loop', projectId, revision: 1, status: 'inspect', target: 'firmware',
  maxAttempts: 3, requireReal: true, evidenceMode: 'real-requested', attempts: [{ runIds: ['exec_failed'] }],
  runId: 'exec_failed', stage: 'compile', rerunFirmwareTests: false,
};

function mockResponse(payload: unknown, status = 200) {
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(payload), { status }));
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}
function expectRequest(mock: ReturnType<typeof mockResponse>, path: string, body?: unknown) {
  expect(mock).toHaveBeenCalledTimes(1);
  const [url, init] = mock.mock.calls[0] as [string, RequestInit];
  expect(url).toBe(`http://127.0.0.1:8000${path}`);
  expect(new Headers(init.headers).get('Authorization')).toBe('Bearer nexus-dev-session-token');
  if (body === undefined) {
    expect(init.method ?? 'GET').toBe('GET');
    expect(init.body).toBeUndefined();
  } else {
    expect(init.method).toBe('POST');
    expect(new Headers(init.headers).get('Content-Type')).toBe('application/json');
    expect(JSON.parse(init.body as string)).toEqual(body);
  }
}
afterEach(() => vi.unstubAllGlobals());

describe('W8 workflow client payloads', () => {
  it('reads the execution-plan artifact envelope', async () => {
    const mock = mockResponse(artifact);
    expect(await api.getExecutionPlan(projectId)).toEqual(artifact);
    expectRequest(mock, `/v1/projects/${projectId}/artifacts/execution-plan`);
  });
  it('proposes explicit plan/configuration with version guards and actor', async () => {
    const body: api.ProposeExecutionPlanInput = { baseProjectStateVersion: 1, basePlanVersion: 1, ...content, requestedBy: actor };
    const response: api.ExecutionPlanProposal = {
      schemaVersion: '1.0.0', content, commandResult: result,
      workspace: { schemaVersion: '1.0.0', workspaceId: 'ws_plan', projectId, artifactId: artifact.artifactId, artifactType: 'execution-plan', workspaceType: 'structured-document', status: 'ready', baseArtifactVersion: 1, baseProjectStateVersion: 1, createdBy: actor, createdAt: artifact.createdAt, updatedAt: artifact.updatedAt, runtimeCapabilityRequirements: [], externalWorkspaceReferences: [] },
    };
    const mock = mockResponse(response);
    expect(await api.proposeExecutionPlan(projectId, body)).toEqual(response);
    expectRequest(mock, `/v1/projects/${projectId}/execution-plan/propose`, body);
  });
  it('omits an optional plan and lets the backend compose it', async () => {
    const body = { baseProjectStateVersion: 1, basePlanVersion: 0, configuration: content.configuration };
    const mock = mockResponse({});
    await api.proposeExecutionPlan(projectId, body);
    expectRequest(mock, `/v1/projects/${projectId}/execution-plan/propose`, body);
  });
  it('retries materialization using the approved artifact and state basis', async () => {
    const body = { planArtifactId: artifact.artifactId, baseProjectStateVersion: 2, requestedBy: actor };
    const response: api.MaterializationResult = { schemaVersion: '1.0.0', status: 'materialized', planArtifactId: artifact.artifactId, executionMode: 'deterministic-scaffold' };
    const mock = mockResponse(response);
    expect(await api.materializeExecutionPlan(projectId, body)).toEqual(response);
    expectRequest(mock, `/v1/projects/${projectId}/execution-plan/materialize`, body);
  });
  for (const accept of [true, false]) {
    for (const reason of [undefined, 'Pinout needs review']) {
      it(`${accept ? 'accepts' : 'rejects'} a revision with reason ${String(reason)}`, async () => {
        const mock = mockResponse(result);
        const call = accept ? api.acceptArtifactRevision : api.rejectArtifactRevision;
        expect(await call(projectId, { ...decision, reason })).toEqual(result);
        const { proposalId, ...envelope } = decision;
        expectRequest(mock, `/v1/projects/${projectId}/artifact-commands`, {
          ...envelope, projectId, commandType: accept ? 'artifact.accept-revision' : 'artifact.reject-revision',
          input: { proposalId, ...(accept && reason === undefined ? {} : { reason: reason ?? 'rejected' }) },
        });
      });
    }
  }
  it('starts repair with explicit real-mode and attempt options', async () => {
    const body = { executionRunId: 'exec_failed', target: 'firmware' as const, maxAttempts: 2, requireReal: false, requestedBy: actor };
    const response = { ...repair, maxAttempts: 2, requireReal: false, evidenceMode: 'regression' };
    const mock = mockResponse(response);
    expect(await api.startRepair(projectId, body)).toEqual(response);
    expectRequest(mock, `/v1/projects/${projectId}/repair`, { ...body, action: 'start' });
  });
  it('leaves repair defaults to the backend', async () => {
    const body = { executionRunId: 'exec_failed', target: 'analysis' as const };
    const mock = mockResponse({ ...repair, target: 'analysis', stage: 'analyze' });
    await api.startRepair(projectId, body);
    expectRequest(mock, `/v1/projects/${projectId}/repair`, { ...body, action: 'start' });
  });
  it('gets repair via POST rather than an invented GET endpoint', async () => {
    const mock = mockResponse(repair);
    expect(await api.getRepair(projectId, repair.repairId)).toEqual(repair);
    expectRequest(mock, `/v1/projects/${projectId}/repair`, { action: 'get', repairId: repair.repairId });
  });
  for (const cancel of [false, true]) {
    it(`${cancel ? 'cancels' : 'advances'} repair with a revision guard`, async () => {
      const response = { ...repair, revision: 2, status: cancel ? 'cancelled' : 'review', proposalId: 'patch_review' };
      const mock = mockResponse(response);
      expect(await api.advanceRepair(projectId, repair.repairId, 1, cancel, actor)).toEqual(response);
      expectRequest(mock, `/v1/projects/${projectId}/repair`, { action: cancel ? 'cancel' : 'advance', repairId: repair.repairId, revision: 1, requestedBy: actor });
    });
  }
  it.each(['fixture', 'llm'])('reads %s provider and storage fields without inferring toolchain availability', async (initializationProvider) => {
    const response = { status: 'ok', initializationProvider, storageBackend: 'sqlite' };
    const mock = mockResponse(response);
    expect(await api.getHealthz()).toEqual(response);
    expectRequest(mock, '/healthz');
  });
  it.each([409, 422])('preserves workflow errors (%s)', async (status) => {
    const body = { error: { code: 'REPAIR_CONFLICT', message: 'Stale repair revision' } };
    mockResponse(body, status);
    await expect(api.advanceRepair(projectId, repair.repairId, 0)).rejects.toMatchObject({ status, body });
  });
});
