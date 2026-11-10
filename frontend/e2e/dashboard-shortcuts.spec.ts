import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 86400 })).toString('base64url');
  return `dev.${payload}.sig`;
}

test('数据概览快捷入口不超过 3 个且指向小说/成片/模型设置', async ({ page }) => {
  const userId = `dash-${Date.now()}`;
  await page.addInitScript(({ authToken, authUserId }) => {
    localStorage.setItem('auth_token', authToken);
    localStorage.setItem('user', JSON.stringify({ id: authUserId, username: authUserId, email: `${authUserId}@example.test` }));
  }, { authToken: devToken(userId), authUserId: userId });
  await page.route('**/api/v1/**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });
  await page.goto('/dashboard');
  const shortcuts = page.getByTestId('dashboard-shortcuts').getByRole('link');
  await expect(shortcuts).toHaveCount(3);
  await expect(shortcuts.nth(0)).toHaveAttribute('href', '/novels');
  await expect(shortcuts.nth(1)).toHaveAttribute('href', '/synthesis');
  await expect(shortcuts.nth(2)).toHaveAttribute('href', '/llm-config');
  await expect(page.getByText('推荐制作路径')).toHaveCount(0);
});
