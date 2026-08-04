import { expect, test } from '@playwright/test';

const GREENHOUSE =
  'I want to build a greenhouse monitoring node that measures temperature, humidity, soil moisture, and light, and reports the readings remotely.';

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
    await expect(page.getByRole('heading', { name: 'Vera' })).toBeVisible();
    const url = page.url();

    await page.reload();
    await expect(page.getByTestId('figma-shell')).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole('heading', { name: 'Vera' })).toBeVisible({ timeout: 30_000 });

    await page.getByRole('button', { name: /^Project Brief$/i }).click();
    await expect(page.getByTestId('workspace-project-brief')).toBeVisible();

    await page.getByRole('button', { name: /^Requirements$/i }).click();
    await expect(page.getByTestId('workspace-requirements')).toBeVisible();

    await page.getByRole('button', { name: /^Architecture$/i }).click();
    await expect(page.getByTestId('workspace-architecture')).toBeVisible();

    await page.getByRole('navigation', { name: /Workflow artifacts/i }).getByRole('button', { name: /Next Action/i }).click();
    await expect(page.getByTestId('workspace-next-action')).toBeVisible();

    for (const label of ['Components', 'Firmware', 'Analysis', 'Test Plan', 'Risk Register']) {
      await page.getByRole('button', { name: new RegExp(`^${label}$`, 'i') }).click();
      await expect(page.getByTestId('artifact-placeholder')).toBeVisible();
    }

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
    await expect(page.getByText(/requirement-set v2/i)).toBeVisible();

    await expect(page.getByText(/BMI270/i)).toHaveCount(0);
    await expect(page.getByText(/T-008/i)).toHaveCount(0);

    expect(url).toMatch(/\/projects\/proj_/);
  });
});
