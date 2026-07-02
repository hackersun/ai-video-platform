import { test, expect } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test('未登录用户点击首页开始创作进入登录页', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.clear();
  });

  await page.goto('/');
  const startLink = page.getByRole('link', { name: /开始创作/ });

  await expect(startLink).toHaveAttribute('href', '/login');
  await startLink.click();
  await expect(page).toHaveURL(/\/login$/);
});

test('已登录用户点击首页开始创作进入极速向导', async ({ page }) => {
  const userId = `home-cta-user-${Date.now()}`;
  const token = devToken(userId);
  await page.addInitScript(({ authToken, authUserId }) => {
    localStorage.setItem('auth_token', authToken);
    localStorage.setItem('user', JSON.stringify({
      id: authUserId,
      username: authUserId,
      email: `${authUserId}@example.test`,
    }));
  }, { authToken: token, authUserId: userId });

  await page.goto('/');
  const startLink = page.getByRole('link', { name: /开始创作/ });

  await expect(startLink).toHaveAttribute('href', '/quick-start');
  await startLink.click();
  await expect(page).toHaveURL(/\/quick-start$/);
});
