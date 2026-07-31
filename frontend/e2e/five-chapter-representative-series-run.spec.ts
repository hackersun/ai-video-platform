import { expect, test } from '@playwright/test';

import { fiveChapter3dNovel } from './helpers/five-chapter-3d-fixture';

test.setTimeout(180_000);

async function register(page: any) {
  const username = `fivechapter_${Date.now()}`;
  const password = 'DeterministicOnly123!';
  await page.goto('/register');
  await page.getByPlaceholder('请输入用户名').fill(username);
  await page.getByPlaceholder('请输入邮箱').fill(`${username}@example.invalid`);
  await page.getByPlaceholder('请输入密码（至少6位）').fill(password);
  await page.getByPlaceholder('请再次输入密码').fill(password);
  await page.getByRole('button', { name: '注册' }).click();
  await page.waitForURL(/\/dashboard/);
}

test('five chapters can start whole-book production and expose representative mode', async ({ page }) => {
  await register(page);
  const title = `${fiveChapter3dNovel.title}-${Date.now()}`;
  await page.goto('/novels/new');
  await page.getByPlaceholder('输入小说标题').fill(title);
  await page.getByPlaceholder('简要介绍小说内容').fill(fiveChapter3dNovel.description);
  await page.locator('select').first().selectOption('fantasy');
  await page.getByRole('button', { name: '保存草稿' }).click();
  await page.waitForURL(/\/novels$/);
  const href = await page.getByRole('link', { name: new RegExp(title) }).first().getAttribute('href');
  expect(href).toMatch(/^\/novels\//);
  await page.goto(`${href}?tab=chapters`);

  for (const chapter of fiveChapter3dNovel.chapters) {
    await page.getByRole('button', { name: '新建章节' }).click();
    await page.getByPlaceholder(/章节标题，可留空/).fill(chapter.title);
    await page.getByPlaceholder(/章节内容或创作方向/).fill(chapter.content);
    await page.getByRole('button', { name: '手动创建' }).click();
    await expect(page.getByText(chapter.title, { exact: true })).toBeVisible({ timeout: 30_000 });
  }

  await page.getByRole('tab', { name: /整书计划/ }).click();
  await page.getByLabel('更多风格').selectOption('xianxia-3d');
  await page.getByRole('button', { name: '生成多集计划', exact: true }).click();
  const panel = page.getByTestId('series-run-panel');
  await expect(panel).toBeVisible();
  await expect(panel.getByRole('button', { name: '整书自动制作', exact: true })).toBeEnabled();
  await expect(panel).toContainText('本次共 5 章');
  await panel.getByRole('button', { name: '整书自动制作', exact: true }).click();
  await expect(panel.getByRole('button', { name: '3 镜头前中后代表验证' })).toBeEnabled({ timeout: 120_000 });
  await panel.getByRole('button', { name: '3 镜头前中后代表验证' }).click();
  await expect(panel.getByRole('button', { name: '生成 3 个镜头首帧' })).toBeVisible();
  await expect(panel.getByRole('button', { name: '单独重做本镜头参考' })).toHaveCount(3);
  await expect(panel.getByText('角色三视图默认跨章节复用')).toBeVisible();
  await expect(page.getByText(/xianxia-3d/).first()).toBeVisible();
});
