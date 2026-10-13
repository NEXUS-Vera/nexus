import { expect, test } from '@playwright/test';

const GREENHOUSE =
  'I want to build a greenhouse monitoring node that measures temperature, humidity, soil moisture, and light, and reports the readings remotely.';

test.describe('phase 11 artifact workspace shell', () => {
  test('overview, requirements, and component-plan load through registry', async ({ page }) => {
    test.skip(
      !process.env.NEXUS_E2E,
      'Set NEXUS_E2E=1 with API/web running (make test-e2e starts them).',
    );

    await page.goto('/');
    await page.getByLabel(/Project idea/i).fill(GREENHOUSE);
    await page.getByRole('button', { name: /Create project/i }).click();
    await expect(page).toHaveURL(/\/projects\/proj_/, { timeout: 60_000 });
    await expect(page.getByTestId('figma-shell')).toBeVisible();

    await page.getByRole('tab', { name: /^Overview$/i }).click();
    await expect(page.getByTestId('project-overview')).toBeVisible();

    await page.getByRole('button', { name: /^Requirements$/i }).click();
    await expect(page.getByTestId('workspace-requirements')).toBeVisible();
    await expect(page.getByTestId('workspace-requirements-shell')).toBeVisible();

    await page.getByRole('button', { name: /^Components$/i }).click();
    await expect(page.getByTestId('workspace-component-plan')).toBeVisible();
    await expect(page.getByTestId('workspace-component-plan-shell')).toBeVisible();
    await expect(page).toHaveURL(/artifact=component-plan/);

    await page.reload();
    await expect(page.getByTestId('workspace-component-plan')).toBeVisible({ timeout: 30_000 });
    await expect(page).toHaveURL(/artifact=component-plan/);
  });
});
