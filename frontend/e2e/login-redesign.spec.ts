import { expect, test } from '@playwright/test';

test.describe('登录页 redesign', () => {
  test('同源 API 地址可代理到后端登录服务', async ({ page }) => {
    test.skip(process.env.AUTH_PROXY_E2E !== '1', '仅在登录代理集成验收时运行');

    await page.goto('/login');
    await page.getByLabel('用户名').fill('invalid-proxy-probe');
    await page.getByLabel('密码').fill('invalid-proxy-probe');
    await page.getByRole('button', { name: /^登录/ }).click();

    await expect(page.getByTestId('login-form-panel').getByRole('alert'))
      .toContainText('用户名或密码错误');
  });

  test('新用户默认看到完整的浅色登录页', async ({ page }) => {
    await page.goto('/login');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');

    const colors = await page.evaluate(() => {
      const main = document.querySelector('main') as HTMLElement;
      const panel = document.querySelector('[data-testid="login-form-panel"]') as HTMLElement;
      const backdrop = main.children[1] as HTMLElement;
      return {
        main: getComputedStyle(main).backgroundColor,
        panel: getComputedStyle(panel).backgroundColor,
        backdrop: getComputedStyle(backdrop).backgroundImage,
      };
    });

    expect(colors.main).toBe('rgb(248, 250, 252)');
    expect(colors.panel).toBe('rgba(255, 255, 255, 0.96)');
    expect(colors.backdrop).not.toContain('rgb(2, 6, 23)');
  });

  test('登录页尊重用户显式选择的深色模式', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('settings.appearance', JSON.stringify({
        theme: 'dark',
        compactMode: false,
        reduceMotion: false,
        accentColor: 'violet',
        denseCards: false,
      }));
    });

    await page.goto('/login');
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
    await expect(page.getByTestId('login-form-panel')).toBeVisible();
  });

  test('登录服务返回非 JSON 内容时显示中文提示', async ({ page }) => {
    await page.route('**/auth/login', (route) => route.fulfill({
      status: 502,
      contentType: 'text/html',
      body: '<html><body>Bad Gateway</body></html>',
    }));

    await page.goto('/login');
    await page.getByLabel('用户名').fill('login-probe');
    await page.getByLabel('密码').fill('login-probe');
    await page.getByRole('button', { name: /^登录/ }).click();

    const alert = page.getByTestId('login-form-panel').getByRole('alert');
    await expect(alert).toContainText('登录服务暂时不可用，请稍后重试');
    await expect(alert).not.toContainText('string did not match');
  });

  test('登录网络连接失败时不暴露浏览器英文异常', async ({ page }) => {
    await page.route('**/auth/login', (route) => route.abort('failed'));

    await page.goto('/login');
    await page.getByLabel('用户名').fill('login-probe');
    await page.getByLabel('密码').fill('login-probe');
    await page.getByRole('button', { name: /^登录/ }).click();

    const alert = page.getByTestId('login-form-panel').getByRole('alert');
    await expect(alert).toContainText('无法连接登录服务，请检查网络后重试');
    await expect(alert).not.toContainText('Failed to fetch');
  });

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
});
