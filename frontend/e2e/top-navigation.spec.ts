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

test('顶部导航突出工作室主线，并把专业工具收进专家菜单', async ({ page }) => {
  await page.route('**/api/v1/**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });

  await page.goto('/studio');
  await page.waitForLoadState('networkidle');

  const navigation = page.getByRole('navigation').first();
  await expect(navigation.getByText('工作室')).toBeVisible();
  await expect(navigation.getByText('快速开始')).toBeVisible();
  await expect(navigation.getByText('小说')).toBeVisible();
  await expect(navigation.getByText('资产')).toBeVisible();

  await page.getByRole('button', { name: /专家工具|更多/ }).click();
  await expect(page.getByRole('menuitem', { name: '工作流' })).toBeVisible();
  await expect(page.getByRole('menuitem', { name: '视频生成' })).toBeVisible();
});

test('专家工具页面提示回到工作室统一管控', async ({ page }) => {
  await page.route('**/api/v1/**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });

  await page.goto('/workflow');
  await expect(page.getByText('这是专家工具。连续动漫制作建议从工作室统一管控。')).toBeVisible();
  await expect(page.getByRole('button', { name: '回到工作室' })).toBeVisible();
});
