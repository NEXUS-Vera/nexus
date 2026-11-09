import { USER_ACTOR } from '../src/api/actor';
import { spawn, type ChildProcess } from 'node:child_process';
import { once } from 'node:events';
import { readFile } from 'node:fs/promises';
import { expect as baseExpect, test, type Locator, type APIResponse, type Response } from '@playwright/test';

const expect = baseExpect.configure({ timeout: 300_000 });

const GOLDEN_PROMPT =
  'Build an ESP32-based vibration monitor using an MPU6050. ' +
  'It should stream acceleration telemetry and analyze stationary sensor noise ' +
  'to verify that accel_x RMS noise stays below 0.10 g.';

/**
 * Opt-in paid live gate: one project, real API/SQLite/model/PlatformIO/Wokwi.
 * API inputs only: USER compile-fault edit and user-authored analysis files.
 * Reads/polling observe real state; no interception, seeded approval, or fixture fallback.
 * Process restart has no UI control and is owned here. Diagnostics expose LIVE,
 * not vendor/name; assert the actual model in the generated patch metadata instead.
 * Analysis inputs use the file API for reproducible noise data/cancellation timing.
 * Failed compile logs have no direct UI entry; try Evidence Explorer and fail
 * with the missing navigation limit if no row exposes that run.
 * Run with scripts/run-w8-live-e2e.sh; no live result has been recorded.
 */
test.skip(process.env.NEXUS_W8_LIVE_E2E !== '1', 'Run scripts/run-w8-live-e2e.sh for the opt-in paid live stack.');
test('W8 live journey through the real API, SQLite, model and tools', async ({ page, request }) => {
  test.setTimeout(30 * 60_000);
  page.setDefaultTimeout(300_000);
  page.setDefaultNavigationTimeout(300_000);
  await page.setViewportSize({ width: 1366, height: 768 });
  const apiURL = process.env.VITE_API_BASE_URL!;
  let api: ChildProcess | undefined;
  const headers = {
    Authorization: `Bearer ${process.env.NEXUS_API_SESSION_TOKEN ?? 'nexus-dev-session-token'}`,
  };
  async function startAPI() {
    api = spawn(process.env.PYTHON!, [
      '-m', 'uvicorn', 'nexus_api.main:app', '--host', '127.0.0.1', '--port', '18000',
    ], { env: process.env, stdio: 'ignore' });
    await expect.poll(async () => {
      if (api!.exitCode !== null) throw new Error(`API exited: ${api!.exitCode}`);
      try {
        const response = await request.get(`${apiURL}/healthz`, { headers });
        return response.ok() ? response.json() : null;
      } catch { return null; }
    }, { timeout: 30_000 }).toMatchObject({ storageBackend: 'sqlite', initializationProvider: 'llm' });
  }
  async function stopAPI() {
    if (api && api.exitCode === null && api.signalCode === null) {
      const exited = once(api, 'exit');
      const killTimer = setTimeout(() => api?.kill('SIGKILL'), 10_000);
      try {
        api.kill('SIGTERM');
        await exited;
      } finally { clearTimeout(killTimer); }
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
    await expect(page).toHaveURL(/\/projects\/proj_/, { timeout: 360_000 });
    const projectURL = page.url();
    const live = page.getByRole('button', { name: 'LIVE', exact: true });
    await keyboardActivate(live);
    await expect(page.getByRole('region', { name: 'Toolchain diagnostics' })).toContainText('Storage: sqlite');
    await expect(page.getByRole('region', { name: 'Toolchain diagnostics' })).toContainText('Initialization provider: LIVE.');
    await expect(page.getByRole('button', { name: 'FIXTURE', exact: true })).toHaveCount(0);
    await keyboardActivate(page.getByRole('button', { name: 'Close diagnostics' }));

    await keyboardActivate(page.getByRole('button', { name: 'Execution Plan', exact: true }));
    await keyboardActivate(page.getByRole('button', { name: 'Create Execution Plan', exact: true }));
    await expect(page.getByRole('region', { name: 'Execution plan review' })).toBeVisible();

    await page.getByRole('textbox', { name: 'Rejection reason (optional)' }).fill('Review the wiring before execution');
    await keyboardActivate(page.getByRole('button', { name: 'Reject plan', exact: true }));
    await expect(page.getByRole('status').filter({ hasText: 'Plan rejected.' })).toBeVisible();
    await keyboardActivate(page.getByRole('button', { name: 'Create Execution Plan', exact: true }));
    await keyboardActivate(page.getByRole('button', { name: 'Accept plan', exact: true }));

    const pid = new URL(projectURL).hash.match(/projects\/([^?]+)/)![1];
    const root = `${apiURL}/v1/projects/${pid}`;
    const actor = USER_ACTOR;
    async function body(response: APIResponse | Response) {
      expect(response.ok(), `API HTTP failure: ${response.status()}`).toBeTruthy();
      return response.json();
    }
    await expect.poll(async () => {
      const state = await body(await request.get(root, { headers }));
      return state.artifacts.find((a: { artifactType: string }) => a.artifactType === 'execution-plan')?.approvalStatus;
    }).toBe('user-approved');

    // Controlled user-authored input through real file APIs; no model or tool success is fabricated.
    async function writeFile(artifact: string, path: string, content: Buffer) {
      const runtime = await body(await request.get(`${root}/artifacts/${artifact}/workspace/runtime`, { headers }));
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
    async function writeAnalysis(path: string, content: Buffer) {
      await writeFile('analysis', path, content);
    }
    function diagnostics(value: unknown) {
      let text = JSON.stringify(value);
      for (const secret of [process.env.NEXUS_MODEL_API_KEY, process.env.ANTHROPIC_API_KEY, process.env.WOKWI_CLI_TOKEN]) {
        if (secret) text = text.replaceAll(secret, '[REDACTED]');
      }
      return text;
    }
    // Capture only responses caused by the UI action, never synthesize results.
    async function uiResponse(control: Locator, suffix: string, repairAction?: string) {
      const response = page.waitForResponse(r => r.url().endsWith(suffix) && r.request().method() === 'POST' &&
        (suffix !== '/artifact-commands' || r.request().postDataJSON()?.commandType === 'artifact.execute') &&
        (!repairAction || r.request().postDataJSON()?.action === repairAction), { timeout: 300_000 });
      await keyboardActivate(control);
      return body(await response);
    }
    async function getRun(id: string) {
      return (await body(await request.get(`${root}/executions/${id}`, { headers }))).executionRun;
    }
    const savedRuns = new Map<string, string>();
    async function finishRun(id: string, expected = 'completed') {
      let latest;
      await expect.poll(async () => {
        latest = await getRun(id);
        return ['queued', 'running', 'pending', 'cancelling'].includes(latest.status) ? 'active' : latest.status;
      }, { timeout: 300_000, intervals: [1000, 3000, 5000] }).not.toBe('active');
      const logs = await body(await request.get(`${root}/executions/${id}/logs`, { headers }));
      latest = await getRun(id);
      expect(latest.status, diagnostics({ run: latest, logs })).toBe(expected);
      savedRuns.set(id, expected);
    }
    async function compile(expected = 'completed') {
      const result = await uiResponse(page.getByTestId('firmware-compile'), '/workspace/compile');
      expect(result.toolchainProfile.executionMode).toBe('platformio');
      const id = result.executionRun.executionRunId;
      await finishRun(id, expected);
      await expect(page.getByText('Fixture execution — no real build evidence')).toHaveCount(0);
      return id as string;
    }
    await keyboardActivate(page.getByRole('button', { name: 'Firmware', exact: true }));
    await expect(page.getByTestId('firmware-refresh')).toBeVisible();
    const scaffold = page.getByTestId('firmware-generate-scaffold');
    await expect.poll(async () => await scaffold.isVisible() || await page.getByTestId('firmware-patch-toggle').isVisible()).toBe(true);
    if (await scaffold.isVisible()) await keyboardActivate(scaffold);
    await keyboardActivate(page.getByTestId('firmware-patch-toggle'));
    await page.getByLabel('Describe the firmware change').fill(
      'Implement the approved ESP32 MPU6050 vibration monitor using Wire.begin and the approved pinout. ' +
      'Stream acceleration telemetry and NEXUS_MPU_READY on Serial for the real Wokwi simulation.',
    );
    const proposal = await uiResponse(page.getByTestId('firmware-patch-propose'), '/workspace/patch/propose');
    expect(proposal.proposal.generatorMetadata.mode).toBe('llm');
    await expect(page.getByTestId('firmware-patch-model')).toContainText(process.env.NEXUS_MODEL_NAME!);
    await expect(page.getByText('MODE: LLM', { exact: true })).toBeVisible();
    await uiResponse(page.getByTestId('firmware-patch-apply'), '/workspace/patch/apply');
    await compile();

    await keyboardActivate(page.getByRole('button', { name: 'Electrical Architecture', exact: true }));
    await keyboardActivate(page.getByTestId('electrical-mode-simulation'));
    const simulation = await uiResponse(page.getByTestId('run-circuit-simulation'), '/artifact-commands');
    expect(simulation.status).not.toBe('failed');
    // Execution command returns the actual run ID.
    const simId = simulation.executionRunId ?? simulation.resultPayload?.executionRunId ?? simulation.resultPayload?.runId;
    expect(simId).toBeTruthy();
    await finishRun(simId);
    await expect(page.getByTestId('latest-simulation-run')).toContainText('wokwi');

    await writeAnalysis('analysis.py', Buffer.from(
      "from threading import Event\nprint('W8 cancellation probe running', flush=True)\nEvent().wait(300)\n",
    ));
    await keyboardActivate(page.getByRole('button', { name: 'Analysis', exact: true }));
    const runButton = page.getByRole('button', { name: 'Run Current', exact: true }).first();
    const cancelledStart = page.waitForResponse(r => r.url().endsWith('/workspace/run') && r.request().method() === 'POST');
    await keyboardActivate(runButton);
    const cancelledRun = (await body(await cancelledStart)).executionRun.executionRunId;
    await expect.poll(async () => (await getRun(cancelledRun)).status, { timeout: 30_000 }).toBe('running');
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
      { timeout: 300_000 }).toBe('completed');
    await keyboardActivate(page.getByRole('button', { name: 'Firmware', exact: true }));
    const source = await body(await request.get(`${root}/artifacts/firmware/workspace/file?path=src%2Fmain.cpp`, { headers }));
    expect(source.content).toMatch(/\bWire\.begin\s*\(/);
    await writeFile('firmware', 'src/main.cpp', Buffer.from(source.content.replace(/\bWire\.begin(?=\s*\()/, 'Wire.begn')));
    await page.reload();
    const failedBuild = await compile('failed');
    // No build-output Inspect control currently exists. Only real evidence rows
    // can open RunLogModal; fail explicitly if the failed build is unreachable.
    async function openFailedBuild(id: string) {
      await keyboardActivate(page.getByRole('button', { name: 'Evidence Explorer', exact: true }));
      await expect(page.getByTestId('evidence-explorer')).toBeVisible();
      await expect(page.getByTestId('evidence-explorer').getByText('Loading…', { exact: true })).toHaveCount(0);
      const controls = page.getByTestId('evidence-explorer').getByRole('button', { name: 'Inspect Run Logs', exact: true });
      for (let n = 0; n < await controls.count(); n++) {
        const response = page.waitForResponse(r => r.url().includes('/executions/') && !r.url().includes('/logs') && r.request().method() === 'GET');
        await keyboardActivate(controls.nth(n));
        const inspected = (await body(await response)).executionRun;
        if (inspected.executionRunId === id) return;
        const dialog = page.getByRole('dialog', { name: 'Run logs', exact: true });
        await dialog.press('Escape');
        await expect(dialog).toHaveCount(0);
      }
      expect(false, `W8 UI navigation limit: failed compile ${id} is absent from Evidence Explorer Inspect Run Logs controls; cannot reach Diagnose & Repair. No API repair input was substituted; W8 remains open.`).toBe(true);
    }
    await openFailedBuild(failedBuild);
    async function diagnose(start = true) {
      // RunLogModal starts once, then automatically advances with the returned revision.
      // Register both listeners before clicking so the automatic advance cannot race us.
      const advanced = page.waitForResponse(r => r.url() === `${root}/repair` &&
        r.request().method() === 'POST' && r.request().postDataJSON()?.action === 'advance',
      { timeout: 300_000 });
      const control = page.getByRole('button', { name: /Diagnose & Repair/ });
      const [response] = await Promise.all([advanced, (async () => {
        if (start) {
          const started = await uiResponse(control, '/repair', 'start');
          expect(started.status, diagnostics(started)).toBe('inspect');
        } else {
          // An inspect retry already has a repair: advance it without starting again.
          await keyboardActivate(control);
        }
      })()]);
      const state = await body(response);
      expect(state.status, `Repair diagnosis did not reach review: ${diagnostics(state)}`).toBe('review');
      await expect(page.getByRole('button', { name: 'Review repair patch in Workspace' })).toBeVisible();
      return state;
    }
    const rejected = await diagnose();
    await keyboardActivate(page.getByRole('button', { name: 'Review repair patch in Workspace' }));
    await keyboardActivate(page.getByRole('button', { name: 'Reject proposal', exact: true }));
    await page.getByLabel('Feedback (optional)').fill('Please provide a minimal correction preserving telemetry and approved wiring.');
    const rejection = await uiResponse(page.getByRole('button', { name: 'Confirm rejection' }), '/repair');
    expect(rejection.status).toBe('rejected');
    expect(rejection.repairId).toBe(rejected.repairId);
    // A fresh failed build provides a new run from which to start the revised repair.
    await keyboardActivate(page.getByRole('button', { name: 'Firmware', exact: true }));
    // Repair state belongs to the mounted project page; clear the rejected session
    // before starting a new repair from the new failed run.
    await page.reload();
    await openFailedBuild(await compile('failed'));
    let repair = await diagnose();
    for (let n = 0; n < 3 && repair.status === 'review'; n++) {
      await keyboardActivate(page.getByRole('button', { name: 'Review repair patch in Workspace' }));
      await uiResponse(page.getByTestId('firmware-patch-apply'), '/workspace/patch/apply');
      repair = await uiResponse(page.getByRole('button', { name: 'Continue repair (rebuild & verify)' }), '/repair');
      await expect.poll(async () => {
        repair = await body(await request.post(`${root}/repair`, { headers, data: { action: 'get', repairId: repair.repairId } }));
        return repair.status;
      }, { timeout: 600_000, intervals: [2000, 5000] }).not.toBe('running');
      if (repair.status === 'inspect' || repair.status === 'review') {
        await keyboardActivate(page.getByRole('button', { name: 'Inspect repair run' }));
        if (repair.status === 'inspect') repair = await diagnose(false);
      }
    }
    expect(repair.status, `Terminal repair state and last diagnostics: ${diagnostics(repair)}`).toBe('completed');
    await compile();
    await keyboardActivate(page.getByRole('button', { name: 'Test Plan', exact: true }));
    const verify = page.getByRole('button', { name: 'Re-verify Stale Criteria', exact: true });
    if (await verify.isVisible() && await verify.isEnabled({ timeout: 2000 })) await keyboardActivate(verify);
    await keyboardActivate(page.getByTestId('test-plan-tab-tests'));
    const testPlan = await body(await request.get(`${root}/artifacts/test-plan`, { headers }));
    const inspections = testPlan.content.testCases.filter((c: { verificationMethod: string }) => c.verificationMethod === 'inspection');
    expect(inspections.length).toBeGreaterThan(0);
    for (const inspection of inspections) {
      await expect(page.getByTestId(`test-plan-case-${inspection.displayId}`)).toContainText('Manual Review (Option B)');
    }
    await expect.poll(async () => {
      const plan = await body(await request.get(`${root}/artifacts/test-plan`, { headers }));
      const text = await page.locator('body').innerText();
      const banner = text.match(/Dynamic Verification PASS \(Option B, (\d+)\/(\d+) cases\)/);
      if (!banner || Number(banner[1]) === 0 || banner[1] !== banner[2]) {
        return { assessments: plan.content, banner: banner?.[0] ?? 'missing' };
      }
      return 'pass';
    }, { timeout: 300_000, intervals: [2000, 5000] }).toBe('pass');
    savedRuns.set(cancelledRun, 'cancelled');
    savedRuns.set(evidenceRun, 'completed');
    const persistedState = await body(await request.get(root, { headers }));

    // Terminate and await the old process, then bind a new API to the same DB.
    await stopAPI();
    await startAPI();
    expect(await body(await request.get(root, { headers }))).toEqual(persistedState);
    for (const [id, status] of savedRuns) expect((await getRun(id)).status).toBe(status);
    expect((await body(await request.get(`${root}/executions/${cancelledRun}`, { headers }))).executionRun.status).toBe('cancelled');
    expect((await body(await request.get(`${root}/executions/${evidenceRun}`, { headers }))).executionRun.status).toBe('completed');
    await page.goto(projectURL);
    await page.reload();
    await expect(page.getByTestId('figma-shell')).toBeVisible();
    await expect(page).toHaveURL(projectURL);
    await expect(live).toBeVisible();
    await expect(page.getByRole('button', { name: 'FIXTURE', exact: true })).toHaveCount(0);
    await keyboardActivate(page.getByRole('button', { name: 'Execution Plan', exact: true }));
    await expect(page.getByRole('region', { name: 'Execution plan review' })).toBeVisible();
    await keyboardActivate(page.getByRole('button', { name: 'Evidence Explorer', exact: true }));
    const evidence = page.getByTestId('evidence-explorer');
    await expect(evidence).toBeVisible();
    await expect(evidence.getByText('Loading…', { exact: true })).toHaveCount(0);
    const seen = new Set<string>();
    const inspect = evidence.getByRole('button', { name: 'Inspect Run Logs', exact: true });
    expect(await inspect.count()).toBeGreaterThanOrEqual(3);
    for (let n = 0; n < await inspect.count(); n++) {
      const detail = page.waitForResponse(r => r.url().includes('/executions/') && !r.url().includes('/logs') && r.request().method() === 'GET');
      await keyboardActivate(inspect.nth(n));
      const inspected = (await body(await detail)).executionRun;
      const logs = page.getByRole('dialog', { name: 'Run logs', exact: true });
      await expect(logs).toContainText(`Status: ${inspected.status}`);
      await expect(logs).not.toContainText(/fixture|stub/i);
      if (inspected.status === 'completed') await expect.poll(async () => {
        const text = await logs.innerText();
        for (const marker of ['platformio', 'wokwi', 'NEXUS_ANALYSIS_R7']) {
          if (text.toLowerCase().includes(marker.toLowerCase())) seen.add(marker);
        }
        return /platformio|wokwi|NEXUS_ANALYSIS_R7/i.test(text);
      }).toBe(true);
      await logs.press('Escape');
      await expect(logs).toHaveCount(0);
    }
    expect([...seen]).toEqual(expect.arrayContaining(['platformio', 'wokwi', 'NEXUS_ANALYSIS_R7']));
    for (const [id, status] of savedRuns) expect((await getRun(id)).status).toBe(status);
  } finally {
    await stopAPI();
  }
});
