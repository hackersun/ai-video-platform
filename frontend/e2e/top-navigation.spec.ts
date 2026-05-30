import { test, expect } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `top-nav-user-${Date.now()}`;
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

test('顶部工具和更多菜单可展开并显示功能入口', async ({ page }) => {
  await page.goto('/dashboard');
  await page.waitForLoadState('networkidle');

  await page.getByRole('button', { name: /工具/ }).click();
  await expect(page.getByRole('menuitem', { name: '语音合成' })).toBeVisible();
  await expect(page.getByRole('menuitem', { name: '资产库' })).toBeVisible();
  await expect(page.getByRole('menuitem', { name: '任务队列' })).toBeVisible();

  await page.getByRole('button', { name: /更多/ }).click();
  await expect(page.getByRole('menuitem', { name: '团队' })).toBeVisible();
  await expect(page.getByRole('menuitem', { name: '设置' })).toBeVisible();
});
