import { expect, test } from '@playwright/test';

const GREENHOUSE =
  'I want to build a greenhouse monitoring node that measures temperature, humidity, soil moisture, and light, and reports the readings remotely.';

test.describe('service-restart notice layout', () => {
  test('shares the viewport with the workspace instead of pushing it off screen', async ({
    page,
  }) => {
    test.skip(
      !process.env.NEXUS_E2E,
      'Set NEXUS_E2E=1 with API/web running (make test-e2e starts them).',
    );

    // Stand in for the desktop shell reporting that it replaced a crashed
    // sidecar. `api` is left empty on purpose, so the client falls back to the
    // browser configuration and the page behaves exactly as it does here
    // normally - only the notice changes.
    await page.addInitScript(() => {
      (window as unknown as { nexus: unknown }).nexus = {
        api: {},
        shell: { serviceRestarted: true },
      };
    });

    await page.goto('/');
    await page.getByLabel(/Project idea/i).fill(GREENHOUSE);
    await page.getByRole('button', { name: /Create project/i }).click();
    await expect(page).toHaveURL(/\/projects\/proj_/, { timeout: 60_000 });
    await expect(page.getByRole('status')).toBeVisible();

    // Vera lives in the inspector sidecar; open the conversation as a user would.
    await page.getByRole('tab', { name: 'Vera', exact: true }).click();

    // The notice apologises for losing what the student had typed, so the box
    // they would retype it into has to still be on screen. A notice rendered as
    // a sibling of a `100vh` workspace makes the document taller than the
    // viewport and pushes the composer below the fold, where the workspace's
    // own `overflow: hidden` puts it out of reach.
    const composer = page.getByLabel(/Continue the conversation/i);
    await expect(composer).toBeInViewport({ ratio: 1 });
    const send = page.getByRole('button', { name: /Send to Vera/i });
    await expect(send).toBeInViewport({ ratio: 1 });

    // A short workspace and a scrolled conversation must keep the input usable.
    await page.setViewportSize({ width: 1280, height: 600 });
    await page.getByTestId('vera-thread').evaluate((thread) => {
      thread.style.minHeight = '2000px';
      thread.parentElement!.scrollTop = 2000;
    });
    await expect(composer).toBeInViewport({ ratio: 1 });
    await expect(send).toBeInViewport({ ratio: 1 });

    const overflow = await page.evaluate(
      () => document.documentElement.scrollHeight - window.innerHeight,
    );
    expect(overflow).toBeLessThanOrEqual(0);
  });
});

test.describe('fixture-mode persistence and modification', () => {
  test('create, refresh, board shell, modify, inspect history', async ({ page }) => {
    test.skip(
      !process.env.NEXUS_E2E,
      'Set NEXUS_E2E=1 with API/web running (make test-e2e starts them).',
    );

    await page.goto('/');
    await page.getByLabel(/Project idea/i).fill(GREENHOUSE);
    await page.getByRole('button', { name: /Create project/i }).click();
    await expect(page).toHaveURL(/\/projects\/proj_/, { timeout: 60_000 });
    await expect(page.getByTestId('figma-shell')).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Vera' })).toBeVisible();
    const url = page.url();

    await page.reload();
    await expect(page.getByTestId('figma-shell')).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole('tab', { name: 'Vera' })).toBeVisible({ timeout: 30_000 });

    await page.getByRole('button', { name: /^Project Brief$/i }).click();
    await expect(page.getByTestId('workspace-project-brief')).toBeVisible();

    await page.getByRole('button', { name: /^Requirements$/i }).click();
    await expect(page.getByTestId('workspace-requirements')).toBeVisible();

    await page.getByRole('button', { name: /^Architecture$/i }).click();
    await expect(page.getByTestId('workspace-architecture')).toBeVisible();

    await page.getByRole('navigation', { name: /Workflow artifacts/i }).getByRole('button', { name: /Next Action/i }).click();
    await expect(page.getByTestId('workspace-next-action')).toBeVisible();

    await page.getByRole('button', { name: /^Firmware$/i }).click();
    await expect(page.getByTestId('firmware-workspace')).toBeVisible();
    await expect(page.getByTestId('firmware-toolbar')).toBeVisible();
    await expect(page.getByTestId('firmware-workspace-error')).toHaveCount(0);

    for (const label of ['Analysis', 'Test Plan', 'Risk Register']) {
      await page.getByRole('button', { name: new RegExp(`^${label}$`, 'i') }).click();
      await expect(page.getByTestId('artifact-placeholder')).toBeVisible();
    }

    await page.getByRole('button', { name: /^Components$/i }).click();
    await expect(page.getByTestId('workspace-component-plan')).toBeVisible();
    await expect(page.getByTestId('workspace-component-plan-shell')).toBeVisible();
    await expect(page.getByTestId('component-plan-summary')).toBeVisible();
    await expect(page.getByTestId('component-plan-role-list')).toBeVisible();
    const componentsUrl = page.url();
    await page.reload();
    await expect(page.getByTestId('workspace-component-plan')).toBeVisible({ timeout: 30_000 });
    expect(componentsUrl).toMatch(/artifact=component-plan/);

    await page.getByRole('tab', { name: 'Vera' }).click();
    await page
      .getByLabel(/Continue the conversation/i)
      .fill('It should run for at least six months on battery power.');
    await page.getByRole('button', { name: /Send to Vera/i }).click();

    await page.getByRole('button', { name: /^Requirements$/i }).click();
    await expect(page.getByText(/Requirements · v2/i)).toBeVisible({ timeout: 60_000 });
    await page.getByRole('button', { name: /^Architecture$/i }).click();
    await expect(page.getByText(/Architecture · v2/i)).toBeVisible();
    await page.getByRole('button', { name: /^Project Brief$/i }).click();
    await expect(page.getByText(/Project Brief · v1/i)).toBeVisible();

    await page.getByRole('button', { name: /Show project history|History/i }).click();
    await expect(page.getByText(/Artifact revisions/i)).toBeVisible();
    await expect(page.getByText(/requirement-set v2 \(ready\)/i)).toBeVisible();

    await expect(page.getByText(/BMI270/i)).toHaveCount(0);
    await expect(page.getByText(/T-008/i)).toHaveCount(0);

    expect(url).toMatch(/\/projects\/proj_/);
  });
});
