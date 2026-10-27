import { spawn, type ChildProcess } from 'node:child_process';
import { once } from 'node:events';
import { readFile } from 'node:fs/promises';
import { expect, test, type Locator } from '@playwright/test';

const GOLDEN_PROMPT =
  'Build an ESP32-based vibration monitor using an MPU6050. ' +
  'It should stream acceleration telemetry and analyze stationary sensor noise ' +
  'to verify that accel_x RMS noise stays below 0.10 g.';

// Start at Home and use the explicit proposal control; never seed an accepted plan.
test('W8 golden journey through the real API and SQLite', async ({ page, request }) => {
  test.skip(!process.env.NEXUS_W8_E2E, 'Run scripts/run-w8-e2e.sh for the isolated SQLite stack.');
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1366, height: 768 });
  const apiURL = process.env.VITE_API_BASE_URL!;
  let api: ChildProcess | undefined;
  const headers = {
    Authorization: `Bearer ${process.env.NEXUS_API_SESSION_TOKEN ?? 'nexus-dev-session-token'}`,
  };
  async function startAPI() {
    api = spawn(process.env.PYTHON!, [
      '-m', 'uvicorn', 'nexus_api.main:app', '--host', '127.0.0.1', '--port', '18000',
    ], { env: process.env, stdio: ['ignore', 'inherit', 'inherit'] });
    await expect.poll(async () => {
      if (api!.exitCode !== null) throw new Error(`API exited: ${api!.exitCode}`);
      try {
        const response = await request.get(`${apiURL}/healthz`, { headers });
        return response.ok() ? response.json() : null;
      } catch { return null; }
    }, { timeout: 30_000 }).toMatchObject({ storageBackend: 'sqlite', initializationProvider: 'fixture' });
  }
  async function stopAPI() {
    if (api && api.exitCode === null && api.signalCode === null) {
      const exited = once(api, 'exit');
      api.kill('SIGTERM');
      await exited;
    }
  }
  async function keyboardActivate(control: Locator) {
    await expect(control).toBeVisible();
    await expect(control).toBeEnabled();
    await control.scrollIntoViewIfNeeded();
    await expect(control).toBeInViewport();
    await control.focus();
    await expect(control).toBeFocused();
    await control.press('Enter');
  }
  try {
    await startAPI();
    await page.goto('/');
    await page.getByLabel(/Project idea/i).fill(GOLDEN_PROMPT);
    await keyboardActivate(page.getByRole('button', { name: /Create project/i }));
    await expect(page).toHaveURL(/\/projects\/proj_/, { timeout: 60_000 });
    const projectURL = page.url();
    const fixture = page.getByRole('button', { name: 'FIXTURE', exact: true });
    await keyboardActivate(fixture);
    await expect(page.getByRole('region', { name: 'Toolchain diagnostics' })).toContainText('Storage: sqlite');
    await expect(page.getByRole('button', { name: 'LIVE', exact: true })).toHaveCount(0);
    await keyboardActivate(page.getByRole('button', { name: 'Close diagnostics' }));

    await keyboardActivate(page.getByRole('button', { name: 'Execution Plan', exact: true }));
    await keyboardActivate(page.getByRole('button', { name: 'Create Execution Plan', exact: true }));
    await expect(page.getByRole('region', { name: 'Execution plan review' })).toBeVisible();

    for (const reason of ['', 'Review the wiring before execution']) {
      await page.getByRole('textbox', { name: 'Rejection reason (optional)' }).fill(reason);
      await keyboardActivate(page.getByRole('button', { name: 'Reject plan', exact: true }));
      await expect(page.getByRole('status').filter({ hasText: 'Plan rejected.' })).toBeVisible();
      await keyboardActivate(page.getByRole('button', { name: 'Create Execution Plan', exact: true }));
    }
    await keyboardActivate(page.getByRole('button', { name: 'Accept plan', exact: true }));

    const pid = new URL(projectURL).hash.match(/projects\/([^?]+)/)![1];
    const root = `${apiURL}/v1/projects/${pid}`;
    const actor = { schemaVersion: '1.0.0', actorType: 'user', actorId: 'user_local', displayName: 'User' };
    async function body(response: { ok(): boolean; text(): Promise<string>; json(): Promise<any> }) {
      expect(response.ok(), await response.text()).toBeTruthy();
      return response.json();
    }
    await expect.poll(async () => {
      const state = await body(await request.get(root, { headers }));
      return state.artifacts.find((a: { artifactType: string }) => a.artifactType === 'execution-plan')?.approvalStatus;
    }).toBe('user-approved');

    // Controlled user-authored input through real file APIs; no model or tool success is fabricated.
    async function writeAnalysis(path: string, content: Buffer) {
      const runtime = await body(await request.get(`${root}/artifacts/analysis/workspace/runtime`, { headers }));
      const binding = runtime.binding;
      const lease = await body(await request.post(`${root}/artifact-commands`, { headers, data: {
        schemaVersion: '1.0.0', commandId: `cmd_${crypto.randomUUID().replaceAll('-', '')}`,
        commandType: 'workspace.acquire-edit-lease', projectId: pid,
        artifactId: binding.artifactId, workspaceId: binding.workspaceId,
        baseArtifactVersion: binding.baseArtifactVersion,
        baseProjectStateVersion: binding.baseProjectStateVersion,
        requestedBy: actor, requestedAt: new Date().toISOString(), input: {},
      } }));
      expect(lease.status).toBe('completed');
      await body(await request.put(`${root}/workspaces/${binding.workspaceId}/file`, { headers, data: {
        path, contentBase64: content.toString('base64'), requestedBy: actor,
        origin: 'USER', writePolicy: 'USER_EDITABLE',
        expectedDraftVersion: runtime.draft.draftVersion,
        baseArtifactVersion: binding.baseArtifactVersion,
        baseProjectStateVersion: binding.baseProjectStateVersion,
      } }));
    }
    await writeAnalysis('analysis.py', Buffer.from(
      "from threading import Event\nprint('W8 cancellation probe running', flush=True)\nEvent().wait(300)\n",
    ));
    await keyboardActivate(page.getByRole('button', { name: 'Analysis', exact: true }));
    const runButton = page.getByRole('button', { name: 'Run Current', exact: true }).first();
    const cancelledStart = page.waitForResponse(r => r.url().endsWith('/workspace/run') && r.request().method() === 'POST');
    await keyboardActivate(runButton);
    const cancelledRun = (await body(await cancelledStart)).executionRun.executionRunId;
    await keyboardActivate(page.getByRole('button', { name: 'Cancel execution', exact: true }));
    await expect.poll(async () => (await body(await request.get(`${root}/executions/${cancelledRun}`, { headers }))).executionRun.status, { timeout: 15_000 }).toBe('cancelled');

    const golden = '../../packages/board/tests/golden/esp32_imu_vibration_monitor';
    await writeAnalysis('analysis.py', await readFile(`${golden}/analysis.py`));
    await writeAnalysis('data/stationary_imu.csv', await readFile(`${golden}/stationary_imu.csv`));
    // Reload picks up the user edits and current optimistic-concurrency guards.
    await page.reload();
    const completedStart = page.waitForResponse(r => r.url().endsWith('/workspace/run') && r.request().method() === 'POST');
    await keyboardActivate(page.getByRole('button', { name: 'Run Current', exact: true }).first());
    const evidenceRun = (await body(await completedStart)).executionRun.executionRunId;
    await expect.poll(async () => (await body(await request.get(`${root}/executions/${evidenceRun}`, { headers }))).executionRun.status,
      { timeout: 30_000 }).toBe('completed');
    const promoted = await body(await request.post(`${root}/verify/promote-execution`, { headers, data: {
      executionRunId: evidenceRun, requestedBy: actor, accept: true,
    } }));
    expect(promoted.accepted).toBe(true);
    const persistedState = await body(await request.get(root, { headers }));

    // Terminate and await the old process, then bind a new API to the same DB.
    await stopAPI();
    await startAPI();
    expect(await body(await request.get(root, { headers }))).toEqual(persistedState);
    expect((await body(await request.get(`${root}/executions/${cancelledRun}`, { headers }))).executionRun.status).toBe('cancelled');
    expect((await body(await request.get(`${root}/executions/${evidenceRun}`, { headers }))).executionRun.status).toBe('completed');
    await page.goto(projectURL);
    await page.reload();
    await expect(page.getByTestId('figma-shell')).toBeVisible();
    await expect(page).toHaveURL(projectURL);
    await expect(fixture).toBeVisible();
    await expect(page.getByRole('button', { name: 'LIVE', exact: true })).toHaveCount(0);
    await keyboardActivate(page.getByRole('button', { name: 'Execution Plan', exact: true }));
    await expect(page.getByRole('region', { name: 'Execution plan review' })).toBeVisible();
    await keyboardActivate(page.getByRole('button', { name: 'Evidence Explorer', exact: true }));
    const evidence = page.getByTestId('evidence-explorer');
    await expect(evidence).toContainText('deterministic-code');
    await keyboardActivate(evidence.getByRole('button', { name: 'Inspect Run Logs', exact: true }).first());
    const logs = page.getByRole('dialog', { name: 'Run logs', exact: true });
    await expect(logs).toContainText('Status: completed');
    await expect(logs).toContainText('NEXUS_ANALYSIS_R7 assessment=PASS');
    await expect(logs.getByRole('alert')).toHaveCount(0);
    await logs.press('Escape');
    await expect(logs).toHaveCount(0);
  } finally {
    await stopAPI();
  }
});
