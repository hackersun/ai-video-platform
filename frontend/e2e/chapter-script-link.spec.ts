import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `chapter-script-link-user-${Date.now()}`;
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

test('chapter list script action preserves novel and chapter context', async ({ page }) => {
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path === '/api/v1/novels/novel-001') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ id: 'novel-001', title: '逆天至尊' }),
      });
      return;
    }

    if (path === '/api/v1/chapters/novel/novel-001') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'chapter-001',
            novel_id: 'novel-001',
            title: '第一章 少年出山',
            status: 'completed',
            updated_at: '2026-06-01T00:00:00',
          },
          {
            id: 'chapter-002',
            novel_id: 'novel-001',
            title: '第二章 宗门试炼',
            status: 'completed',
            updated_at: '2026-06-02T00:00:00',
          },
        ]),
      });
      return;
    }

    if (path === '/api/v1/novels') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 'novel-001', title: '逆天至尊' }]),
      });
      return;
    }

    if (path === '/api/v1/scripts' && request.method() === 'GET') {
      const chapterId = url.searchParams.get('chapter_id');
      const scripts = [
        { id: 'script-001', title: '第一章剧本', novel_id: 'novel-001', chapter_id: 'chapter-001', status: 'draft' },
        { id: 'script-002', title: '第二章剧本', novel_id: 'novel-001', chapter_id: 'chapter-002', status: 'draft' },
      ].filter((script) => !chapterId || script.chapter_id === chapterId);
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(scripts) });
      return;
    }

    if (path === '/api/v1/llm/configs') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });

  await page.goto('/novels/novel-001/chapters');
  await expect(page.getByRole('heading', { name: /章节管理/ })).toBeVisible();

  await page.getByRole('link', { name: /剧本/ }).nth(1).click();

  await expect(page).toHaveURL(/\/scripts\?novel_id=novel-001&chapter_id=chapter-002$/);
  await expect(page.getByText('第二章剧本')).toBeVisible();
  await expect(page.getByText('第一章剧本')).toHaveCount(0);
});
