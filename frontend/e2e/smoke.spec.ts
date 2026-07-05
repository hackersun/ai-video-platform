import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test('unauthenticated homepage CTA opens login', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.clear();
  });

  await page.goto('/');
  const startLink = page.getByRole('link', { name: /开始连续动漫向导/ });

  await expect(startLink).toHaveAttribute('href', '/login');
  await startLink.click();
  await expect(page).toHaveURL(/\/login$/);
});

test('authenticated studio shell renders without backend', async ({ page }) => {
  const userId = `smoke-user-${Date.now()}`;
  const token = devToken(userId);

  await page.addInitScript(({ authToken, authUserId }) => {
    localStorage.setItem('auth_token', authToken);
    localStorage.setItem('user', JSON.stringify({
      id: authUserId,
      username: authUserId,
      email: `${authUserId}@example.test`,
    }));
  }, { authToken: token, authUserId: userId });

  await page.route('**/api/v1/**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });

  await page.goto('/studio');

  const navigation = page.getByRole('navigation').first();
  await expect(navigation.getByText('工作室')).toBeVisible();
  await expect(navigation.getByText('快速开始')).toBeVisible();
  await expect(page.getByRole('heading', { name: '系列动漫工作室' })).toBeVisible();
});
