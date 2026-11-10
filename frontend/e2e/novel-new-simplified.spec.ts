import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test('新建小说默认只展示标题、简介、题材，其余收进“更多设置”', async ({ page }) => {
  const userId = `novel-new-simple-${Date.now()}`;
  await page.addInitScript(({ authToken, authUserId }) => {
    localStorage.setItem('auth_token', authToken);
    localStorage.setItem('user', JSON.stringify({ id: authUserId, username: authUserId, email: `${authUserId}@example.test` }));
  }, { authToken: devToken(userId), authUserId: userId });
  let created: Record<string, unknown> | null = null;
  await page.route('**/api/v1/novels', async (route) => {
    if (route.request().method() !== 'POST') return route.fallback();
    created = route.request().postDataJSON();
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ id: 'novel-simple-1' }) });
  });
  await page.route('**/novels/novel-simple-1**', (route) => route.fulfill({ status: 200, contentType: 'text/html', body: '<html><body>ok</body></html>' }));

  await page.goto('/novels/new');
  await expect(page.getByPlaceholder('输入小说标题')).toBeVisible();
  await expect(page.getByPlaceholder('简要介绍小说内容')).toBeVisible();
  const more = page.getByTestId('novel-more-settings');
  await expect(more).not.toHaveAttribute('open', '');
  await expect(page.getByPlaceholder(/用逗号分隔标签/)).toBeHidden();
  await expect(page.getByText('封面设置')).toBeHidden();

  await more.locator('summary').click();
  await expect(page.getByPlaceholder(/用逗号分隔标签/)).toBeVisible();
  await expect(page.getByText('封面设置')).toBeVisible();

  await page.getByPlaceholder('输入小说标题').fill('极简新建');
  await page.locator('select').first().selectOption('xianxia');
  await page.getByRole('button', { name: '保存草稿' }).click();
  await expect.poll(() => created?.title).toBe('极简新建');
  expect(created?.genre).toBe('仙侠');
});
