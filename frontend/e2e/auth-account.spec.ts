import { expect, test } from '@playwright/test';

test('unauthenticated protected pages redirect to login and expose password recovery', async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on('console', message => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });
  await page.route('**/api/v1/auth/refresh', route => route.fulfill({
    status: 401,
    contentType: 'application/json',
    body: JSON.stringify({ detail: '登录会话已过期，请重新登录' }),
  }));
  await page.route('**/api/v1/auth/me', route => route.fulfill({
    status: 401,
    contentType: 'application/json',
    body: JSON.stringify({ detail: '请先登录后再继续操作' }),
  }));
  await page.goto('/settings/profile');
  await expect(page).toHaveURL(/\/login\?next=%2Fsettings%2Fprofile$/);

  await expect(page.getByRole('link', { name: '忘记密码？' })).toBeVisible();
  await page.getByRole('link', { name: '忘记密码？' }).click();
  await expect(page).toHaveURL(/\/forgot-password$/);
  await expect(page.getByRole('heading', { name: '找回密码' })).toBeVisible();

  await page.goto('/reset-password');
  await expect(page.getByRole('heading', { name: '重置密码' })).toBeVisible();
  expect(consoleErrors.filter(message => message.includes('加载用户信息失败'))).toEqual([]);
});

test('cookie login succeeds without storing a new access token in localStorage', async ({ page }) => {
  await page.addInitScript(() => localStorage.clear());
  await page.route('**/api/v1/**', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify([]),
  }));
  await page.route('**/api/v1/auth/me', route => route.fulfill({
    status: 401,
    contentType: 'application/json',
    body: JSON.stringify({ detail: '请先登录后再继续操作' }),
  }));
  await page.route('**/api/v1/auth/login', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    headers: { 'Set-Cookie': 'csrf_token=e2e-csrf; Path=/; SameSite=Lax' },
    body: JSON.stringify({
      success: true,
      message: '登录成功',
      user: { id: 'cookie-user', username: 'cookie-user', email: 'cookie@example.test' },
    }),
  }));
  await page.goto('/login');
  await page.getByLabel('用户名').fill('cookie-user');
  await page.getByLabel('密码').fill('CommercialPass123!');
  await page.getByRole('button', { name: '登录' }).click();

  await expect(page).toHaveURL(/\/dashboard$/);
  expect(await page.evaluate(() => localStorage.getItem('auth_token'))).toBeNull();
  expect(await page.evaluate(() => localStorage.getItem('user'))).toBeNull();
});
