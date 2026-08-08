import { expect, test } from '@playwright/test';

test.describe('登录页 redesign', () => {
  test('renders the production login surface and preserves auth actions', async ({ page }) => {
    await page.goto('/login');
    await page.waitForLoadState('networkidle');

    await expect(page.getByRole('link', { name: 'AI视频平台' })).toBeVisible();
    await expect(page.getByText('AI 动漫制作工作台').filter({ visible: true })).toBeVisible();
    await expect(page.getByText('角色资产', { exact: true })).toBeVisible();
    await expect(page.getByText('剧本分镜', { exact: true })).toBeVisible();
    await expect(page.getByText('视频生成', { exact: true })).toBeVisible();

    await expect(page.getByRole('heading', { name: '用户登录' })).toBeVisible();
    await expect(page.getByLabel('用户名')).toBeVisible();
    await expect(page.getByLabel('密码')).toBeVisible();
    await expect(page.getByPlaceholder('请输入用户名')).toBeVisible();
    await expect(page.getByPlaceholder('请输入密码')).toBeVisible();
    await expect(page.getByRole('button', { name: /登录/ })).toBeVisible();

    await expect(page.getByRole('link', { name: '忘记密码？' })).toHaveAttribute('href', '/forgot-password');
    await expect(page.getByRole('link', { name: '立即注册' })).toHaveAttribute('href', '/register');
    await expect(page.getByRole('link', { name: /返回首页/ })).toHaveAttribute('href', '/');

    await page.getByRole('button', { name: /登录/ }).click();
    await expect(page.getByText('请填写用户名和密码')).toBeVisible();
  });

  test('keeps the login form readable on mobile', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/login');
    await page.waitForLoadState('networkidle');

    await expect(page.getByText('AI 动漫制作工作台').filter({ visible: true })).toBeVisible();
    await expect(page.getByTestId('login-form-panel')).toBeInViewport();
    await expect(page.getByRole('heading', { name: '用户登录' })).toBeInViewport();
    await expect(page.getByRole('button', { name: /登录/ })).toBeInViewport();
  });

  test('toggles password visibility without changing the password', async ({ page }) => {
    await page.goto('/login');
    const password = page.getByLabel('密码');
    await password.fill('CommercialPass123!');

    await expect(password).toHaveAttribute('type', 'password');
    await page.getByRole('button', { name: '显示输入内容' }).click();
    await expect(password).toHaveAttribute('type', 'text');
    await expect(password).toHaveValue('CommercialPass123!');
    await page.getByRole('button', { name: '隐藏输入内容' }).click();
    await expect(password).toHaveAttribute('type', 'password');
  });

  test('returns to a safe requested task after login', async ({ page }) => {
    await page.route('**/api/v1/auth/me', route => route.fulfill({
      status: 401,
      contentType: 'application/json',
      body: JSON.stringify({ detail: '请先登录后再继续操作' }),
    }));
    await page.route('**/api/v1/auth/login', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        message: '登录成功',
        user: { id: 'return-user', username: 'return-user', email: 'return@example.test' },
      }),
    }));
    await page.goto('/login?next=%2Fquick-start');
    await page.getByLabel('用户名').fill('return-user');
    await page.getByLabel('密码').fill('CommercialPass123!');
    await page.getByRole('button', { name: '登录' }).click();

    await expect(page).toHaveURL(/\/quick-start$/);
  });

  test('rejects an external return address after login', async ({ page }) => {
    await page.route('**/api/v1/auth/me', route => route.fulfill({
      status: 401,
      contentType: 'application/json',
      body: JSON.stringify({ detail: '请先登录后再继续操作' }),
    }));
    await page.route('**/api/v1/auth/login', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        message: '登录成功',
        user: { id: 'safe-user', username: 'safe-user', email: 'safe@example.test' },
      }),
    }));
    await page.goto('/login?next=%2F%5Cevil.example');
    await page.getByLabel('用户名').fill('safe-user');
    await page.getByLabel('密码').fill('CommercialPass123!');
    await page.getByRole('button', { name: '登录' }).click();

    await expect(page).toHaveURL(/\/dashboard$/);
  });
});
