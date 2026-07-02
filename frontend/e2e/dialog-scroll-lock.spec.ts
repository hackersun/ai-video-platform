import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `dialog-scroll-user-${Date.now()}`;
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

test('closed dialogs do not lock page scrolling and open dialogs restore scroll after close', async ({ page }) => {
  const novels = Array.from({ length: 20 }, (_, index) => ({
    id: `scroll-novel-${index + 1}`,
    title: `测试小说 ${index + 1}`,
    description: '用于验证确认弹窗不会在关闭状态锁住页面滚动。',
    genre: '玄幻',
    status: index % 2 === 0 ? 'writing' : 'draft',
    word_count: 1200 + index,
    tags: [],
    cover_url: null,
    source: 'manual',
    created_at: '2026-06-02T00:00:00',
    updated_at: '2026-06-02T00:00:00',
  }));

  await page.route('**/api/v1/novels', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({ json: novels });
      return;
    }
    await route.fulfill({ status: 201, json: novels[0] });
  });

  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto('/novels');
  await expect(page.getByRole('heading', { name: '小说管理' })).toBeVisible();

  await expect.poll(() => page.evaluate(() => document.body.style.overflow)).not.toBe('hidden');
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollHeight > window.innerHeight)).toBe(true);
  await page.evaluate(() => {
    window.scrollTo(0, 600);
  });
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(0);
  const beforeDialogScroll = await page.evaluate(() => window.scrollY);
  expect(beforeDialogScroll).toBeGreaterThan(0);

  await page.getByLabel('删除《测试小说 1》').click();
  await expect(page.getByRole('dialog', { name: '删除小说' })).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.body.style.overflow)).toBe('hidden');

  await page.getByRole('button', { name: '取消' }).click();
  await expect(page.getByRole('dialog', { name: '删除小说' })).toBeHidden();
  await expect.poll(() => page.evaluate(() => document.body.style.overflow)).not.toBe('hidden');

  await page.evaluate(() => {
    window.scrollTo(0, 900);
  });
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(beforeDialogScroll);
  const afterDialogScroll = await page.evaluate(() => window.scrollY);
  expect(afterDialogScroll).toBeGreaterThan(beforeDialogScroll);
});
