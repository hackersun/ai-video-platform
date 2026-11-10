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
    if (sessionStorage.getItem('top_nav_auth_seeded')) return;
    localStorage.setItem('auth_token', authToken);
    localStorage.setItem('user', JSON.stringify({
      id: authUserId,
      username: authUserId,
      email: `${authUserId}@example.test`,
    }));
    sessionStorage.setItem('top_nav_auth_seeded', '1');
  }, { authToken: token, authUserId: userId });
});

test('顶部导航只保留主线入口，并把专业工具收进高级工具菜单', async ({ page }) => {
  await page.route('**/api/v1/**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });

  await page.goto('/studio');
  await page.waitForLoadState('networkidle');

  const navigation = page.getByRole('navigation').first();
  for (const label of ['小说', '成片', '模型设置']) {
    await expect(navigation.getByRole('link', { name: label })).toBeVisible();
  }
  // one-entry rule: jobs/assets/expert pages are not primary entries
  await expect(navigation.getByRole('link', { name: '任务中心' })).toHaveCount(0);
  await expect(navigation.getByRole('link', { name: '资产' })).toHaveCount(0);
  await expect(navigation.getByRole('link', { name: '快速开始' })).toHaveCount(0);
  await expect(navigation.getByRole('link', { name: '专家向导' })).toHaveCount(0);

  await page.getByRole('button', { name: '高级工具' }).click();
  for (const label of ['工作室', '专家向导', '任务中心', '角色与场景图', '故事设定', 'AI 制片', '工作流', '视频生成', '配音', '时间线', '数据概览']) {
    await expect(page.getByRole('menuitem', { name: label })).toBeVisible();
  }
  await page.getByRole('menuitem', { name: '工作流' }).click();
  await expect(page).toHaveURL(/\/workflow$/);
});

test('登录后顶部导航提供账户设置和退出入口', async ({ page }) => {
  await page.route('**/api/v1/**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });

  await page.goto('/studio');
  await page.waitForLoadState('networkidle');

  await page.getByRole('button', { name: '账户菜单' }).click();
  await expect(page.getByRole('menuitem', { name: '系统设置' })).toBeVisible();
  await expect(page.getByRole('menuitem', { name: '个人资料' })).toBeVisible();
  await expect(page.getByRole('menuitem', { name: '团队管理' })).toBeVisible();
  await expect(page.getByRole('menuitem', { name: '退出登录' })).toBeVisible();

  await page.getByRole('menuitem', { name: '个人资料' }).click();
  await expect(page).toHaveURL(/\/settings\/profile$/);

  await page.goto('/studio');
  await page.getByRole('button', { name: '账户菜单' }).click();
  await page.getByRole('menuitem', { name: '退出登录' }).click();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.evaluate(() => localStorage.getItem('auth_token'))).resolves.toBeNull();
});

test('专家工具页面提示回到工作室统一管控', async ({ page }) => {
  await page.route('**/api/v1/**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });

  await page.goto('/workflow');
  await expect(page.getByText('这是高级工具。连续动漫制作建议从工作室统一管控。')).toBeVisible();
  await expect(page.getByRole('button', { name: '回到工作室' })).toBeVisible();
});

test('手机栏可进入模型设置', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route('**/api/v1/**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });
  await page.goto('/novels');
  await page.waitForLoadState('networkidle');
  await page.getByRole('navigation').getByRole('link', { name: '模型设置' }).click();
  await expect(page).toHaveURL(/\/llm-config/);
});
