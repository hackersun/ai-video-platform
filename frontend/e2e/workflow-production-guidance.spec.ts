import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `workflow-guidance-user-${Date.now()}`;
  const token = devToken(userId);
  await page.addInitScript(({ authToken, authUserId }) => {
    localStorage.setItem('auth_token', authToken);
    localStorage.setItem('user', JSON.stringify({
      id: authUserId,
      username: authUserId,
      email: `${authUserId}@example.test`,
    }));
  }, { authToken: token, authUserId: userId });
});

test('workflow page does not silently create a workflow without workflow_id', async ({ page }) => {
  let startWorkflowCalls = 0;
  await page.route('**/api/v1/workflow/start', async (route) => {
    startWorkflowCalls += 1;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ workflow_id: 'unexpected-auto-workflow' }),
    });
  });

  await page.goto('/workflow');
  await expect(page.getByText('选择或创建本集工程')).toBeVisible({ timeout: 10_000 });
  await page.waitForTimeout(1000);

  expect(startWorkflowCalls).toBe(0);
});
