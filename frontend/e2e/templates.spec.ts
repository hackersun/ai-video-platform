import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `templates-e2e-user-${Date.now()}`;
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

test('模板库可编辑系统预制模板并持久化定制状态', async ({ page }) => {
  const stamp = Date.now();
  const customName = `E2E定制开场模板-${stamp}`;

  await page.goto('/templates');
  await expect(page.getByRole('heading', { name: '模板库' })).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText('强钩子开场')).toBeVisible({ timeout: 10_000 });

  await page.getByTitle('编辑系统模板强钩子开场').click();
  await page.getByPlaceholder('模板名称').last().fill(customName);
  await page.getByPlaceholder('标签，用逗号分隔').last().fill('E2E,开场,悬念');
  await page.getByPlaceholder('模板用途和适用场景').last().fill('E2E 定制系统模板，用于验证刷新后仍生效。');
  await page.getByRole('button', { name: /^保存$/ }).click();

  await expect(page.getByText('系统模板已定制')).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText(customName)).toBeVisible();
  await expect(page.getByText('已定制', { exact: true })).toBeVisible();

  await page.reload();
  await expect(page.getByText(customName)).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText('已定制', { exact: true })).toBeVisible();
});
