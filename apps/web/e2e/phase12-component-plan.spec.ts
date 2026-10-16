import { expect, test } from '@playwright/test';

const GREENHOUSE =
  'I want to build a greenhouse monitoring node that measures temperature, humidity, soil moisture, and light, and reports the readings remotely.';

test.describe('phase 12 component plan workspace', () => {
  test('greenhouse components: table, candidates, request alternatives opens Vera', async ({
    page,
  }) => {
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
    await expect(page.getByTestId('overview-phase-DESIGN')).toBeVisible();
    await expect(page.getByTestId('overview-artifact-component-plan')).toBeVisible();

    await page.getByRole('button', { name: /^Components$/i }).click();
    await expect(page.getByTestId('workspace-component-plan')).toBeVisible();
    await expect(page.getByTestId('workspace-component-plan-shell')).toBeVisible();
    await expect(page).toHaveURL(/artifact=component-plan/);

    await expect(page.getByTestId('component-plan-role-list')).toBeVisible();
    await expect(page.getByTestId('component-plan-role-table')).toBeVisible();
    const sensorRole = page.locator('[data-role-category="sensor"]').first();
    await expect(sensorRole).toBeVisible();
    await sensorRole.click();
    await expect(page).toHaveURL(/role=/);

    await page.getByTestId('component-plan-inspector-tab-alternatives').click();
    await expect(page.getByTestId('component-plan-candidate-compare')).toBeVisible();
    const candidatesEmpty = page.getByTestId('component-plan-candidates-empty');
    const candidateCards = page.locator('[data-testid^="component-candidate-"]');
    const hasCandidates = (await candidateCards.count()) > 0;
    if (!hasCandidates) {
      await expect(candidatesEmpty).toBeVisible();
    } else {
      await expect(candidateCards.first()).toBeVisible();
    }

    await page.getByTestId('component-plan-inspector-tab-decision').click();
    const approve = page.getByTestId('component-plan-approve');
    if (await approve.isVisible()) {
      const enabled = await approve.isEnabled();
      if (enabled) {
        await approve.click();
        await expect(page.getByRole('status')).toBeVisible({ timeout: 30_000 });
      }
    }

    await page.getByTestId('component-plan-request-alternatives').click();
    await expect(page).toHaveURL(/panel=vera/);
    await expect(page.getByTestId('vera-panel')).toBeVisible();
    await expect(page.getByLabel(/Continue the conversation/i)).toHaveValue(
      /Show me alternatives for the .+ role\./,
    );
    await expect(page.getByTestId('vera-context-chips')).toBeVisible();
    await expect(page.getByTestId('workspace-component-plan')).toBeVisible();

    await page.reload();
    await expect(page.getByTestId('workspace-component-plan')).toBeVisible({ timeout: 30_000 });
    await expect(page).toHaveURL(/artifact=component-plan/);
    await expect(page.getByTestId('component-plan-role-list')).toBeVisible();
  });
});
