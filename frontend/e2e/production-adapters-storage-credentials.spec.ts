import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 3600 })).toString('base64url');
  return `dev.${payload}.sig`;
}

// The legacy production-adapters page was folded into the unified model center;
// object storage credentials are now managed under 模型中心 → 供应商账号.
test('legacy production adapters entry opens model center connections for storage credentials', async ({ page }) => {
  await page.addInitScript(({ token, userId }) => {
    localStorage.setItem('auth_token', token);
    localStorage.setItem('user', JSON.stringify({ id: userId, username: userId, email: `${userId}@example.test` }));
  }, { token: devToken('storage-ui-user'), userId: 'storage-ui-user' });

  await page.goto('/production-adapters?capability=object_storage');
  await page.waitForURL((url) => !url.pathname.startsWith('/production-adapters'));
  expect(page.url()).toContain('connections');
  expect(page.url()).toContain('object_storage');
  await expect(page.getByRole('button', { name: /新增账号/ })).toBeVisible({ timeout: 15_000 });
});
