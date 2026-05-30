import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `asset-e2e-user-${Date.now()}`;
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

test('资产库页面可创建、编辑和归档资产', async ({ page }) => {
  const stamp = Date.now();
  const name = `资产库验证角色-${stamp}`;
  const editedName = `${name}-更新`;

  await page.goto('/assets');
  await expect(page.getByRole('heading', { name: '资产库' })).toBeVisible();

  await page.getByRole('textbox', { name: '搜索资产名称、描述、标签' }).fill(name);
  await page.getByRole('button', { name: '搜索' }).click();
  await page.getByRole('button', { name: '新建资产' }).click();
  await page.getByRole('textbox', { name: '资产名称', exact: true }).fill(name);
  await page.getByPlaceholder('资源 URL 或 /static/... 路径').fill('/static/dev/reference.png');
  await page.getByPlaceholder('业务标签，例如：主角，夜景，法器').fill('主角,多视图');
  await page.getByPlaceholder('资产用途、视觉 DNA、适用镜头或一致性说明').fill('黑发蓝衣，正面角色参考图。');
  await page.getByRole('button', { name: '保存资产' }).click();

  await expect(page.getByText('资产已保存')).toBeVisible();
  await expect(page.getByText(name)).toBeVisible();

  await page.getByTitle('编辑资产').filter({ hasText: '编辑' }).first().click();
  await page.getByRole('textbox', { name: '资产名称', exact: true }).fill(editedName);
  await page.getByRole('button', { name: '保存资产' }).click();

  await expect(page.getByText('资产已更新')).toBeVisible();
  await expect(page.getByText(editedName)).toBeVisible();

  await page.getByTitle('归档资产').filter({ hasText: '归档' }).first().click();
  await expect(page.getByText('资产已归档')).toBeVisible();
});
