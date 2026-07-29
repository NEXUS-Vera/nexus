import { expect, test } from '@playwright/test';

const GREENHOUSE =
  'I want to build a greenhouse monitoring node that measures temperature, humidity, soil moisture, and light, and reports the readings remotely.';

test.describe('fixture-mode persistence and modification', () => {
  test('create, refresh, modify runtime, inspect history', async ({ page }) => {
    test.skip(
      !process.env.NEXUS_E2E,
      'Set NEXUS_E2E=1 with API/web running (make test-e2e starts them).',
    );

    await page.goto('/');
    await page.getByLabel(/Project idea/i).fill(GREENHOUSE);
    await page.getByRole('button', { name: /Create project/i }).click();
    await expect(page).toHaveURL(/\/projects\/proj_/, { timeout: 60_000 });
    await expect(page.getByRole('heading', { name: 'Vera' })).toBeVisible();
    const url = page.url();

    await page.reload();
    await expect(page.getByRole('heading', { name: 'Vera' })).toBeVisible({ timeout: 30_000 });

    await page
      .getByLabel(/Continue the conversation/i)
      .fill('It should run for at least six months on battery power.');
    await page.getByRole('button', { name: /Send to Vera/i }).click();
    await expect(page.getByText(/Requirements · v2/i)).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText(/Architecture · v2/i)).toBeVisible();
    await expect(page.getByText(/Project Brief · v1/i)).toBeVisible();

    await page.getByRole('button', { name: /Show history/i }).click();
    await expect(page.getByText(/Artifact revisions/i)).toBeVisible();
    await expect(page.getByText(/requirement-set v2/i)).toBeVisible();

    expect(url).toMatch(/\/projects\/proj_/);
  });
});
