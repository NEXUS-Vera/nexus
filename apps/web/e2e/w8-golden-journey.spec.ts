import { spawn, type ChildProcess } from 'node:child_process';
import { once } from 'node:events';
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
    ], { env: process.env, stdio: 'ignore' });
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
    await expect(control).toBeEnabled();
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
    // The current fixture's FX-* candidates are rejected by the real propose
    // endpoint. Keep this assertion red until the product configuration gap is
    // resolved; accepting that error would falsely close the W8 gate.
    await expect(page.getByRole('region', { name: 'Execution plan review' }),
      'W8 blocked: fixture FX-MCU-32 / FX-IMU-200 are unsupported by plan materialization.',
    ).toBeVisible();

    for (const reason of ['', 'Review the wiring before execution']) {
      await page.getByRole('textbox', { name: 'Rejection reason (optional)' }).fill(reason);
      await keyboardActivate(page.getByRole('button', { name: 'Reject plan', exact: true }));
      await expect(page.getByRole('status').filter({ hasText: 'Plan rejected.' })).toBeVisible();
      await keyboardActivate(page.getByRole('button', { name: 'Create Execution Plan', exact: true }));
    }
    await keyboardActivate(page.getByRole('button', { name: 'Accept plan', exact: true }));

    // Terminate and await the old process, then bind a new API to the same DB.
    await stopAPI();
    await startAPI();
    await page.reload();
    await expect(page.getByTestId('figma-shell')).toBeVisible();
    await expect(page).toHaveURL(projectURL);
    await expect(fixture).toBeVisible();
    await expect(page.getByRole('region', { name: 'Execution plan review' })).toBeVisible();
    // Cancellation and evidence navigation cannot be authored truthfully until
    // fixture plan creation supports the real P1 -> P2 handoff. This partial
    // probe must not be treated as a complete W8 acceptance journey.
    throw new Error('W8 gate remains open: cancellation and evidence/run-log navigation are not implemented in this probe.');
  } finally {
    await stopAPI();
  }
});
