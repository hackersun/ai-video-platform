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
  await expect(page.getByRole('heading', { name: /模板(库|市场)/ })).toBeVisible({ timeout: 10_000 });
  await expect(page.getByRole('heading', { name: '玄幻修仙 预置' })).toBeVisible({ timeout: 10_000 });

  await page.getByTitle('复制并编辑玄幻修仙').click();
  await page.getByPlaceholder('输入模板名称').last().fill(customName);
  await page.getByPlaceholder(/用逗号分隔/).last().fill('E2E,开场,悬念');
  await page.getByPlaceholder(/适用场景/).last().fill('E2E 定制系统模板，用于验证刷新后仍生效。');
  await page.getByRole('button', { name: /^保存模板$/ }).click();

  await expect(page.getByText('模板已创建')).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText(customName)).toBeVisible();

  await page.reload();
  await expect(page.getByText(customName)).toBeVisible({ timeout: 10_000 });

  await page.getByLabel(`选择${customName}`).check();
  await expect(page.getByRole('button', { name: '批量分类' })).toBeVisible();
  await expect(page.getByRole('button', { name: '批量标签' })).toBeVisible();
  await expect(page.getByRole('button', { name: '批量公开状态' })).toBeVisible();
});
