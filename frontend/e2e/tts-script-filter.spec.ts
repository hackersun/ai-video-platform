import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `tts-script-filter-user-${Date.now()}`;
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

test('tts script selector is scoped to the selected chapter', async ({ page }) => {
  const scriptQueries: string[] = [];

  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;

    if (path === '/api/v1/novels') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 'novel-001', title: '逆天至尊' }]),
      });
      return;
    }

    if (path === '/api/v1/tts/jobs') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }

    if (path === '/api/v1/llm/configs') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }

    if (path === '/api/v1/tts/voices') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ voices: [] }) });
      return;
    }

    if (path === '/api/v1/chapters/novel/novel-001') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 'chapter-001', novel_id: 'novel-001', title: '第一章 少年出山' },
          { id: 'chapter-002', novel_id: 'novel-001', title: '第二章 宗门试炼' },
        ]),
      });
      return;
    }

    if (path === '/api/v1/story-bibles') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }

    if (path === '/api/v1/scripts') {
      scriptQueries.push(url.search);
      const chapterId = url.searchParams.get('chapter_id');
      const allScripts = [
        { id: 'script-001', title: '第一章剧本', novel_id: 'novel-001', chapter_id: 'chapter-001' },
        { id: 'script-002', title: '第二章剧本', novel_id: 'novel-001', chapter_id: 'chapter-002' },
      ];
      const scripts = chapterId ? allScripts.filter((item) => item.chapter_id === chapterId) : allScripts;
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(scripts) });
      return;
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });

  await page.goto('/tts');
  await expect(page.getByRole('heading', { name: /语音合成/ })).toBeVisible();

  await page.locator('select').filter({ has: page.locator('option[value="novel-001"]') }).selectOption('novel-001');
  await page.locator('select').filter({ has: page.locator('option[value="chapter-002"]') }).selectOption('chapter-002');

  await expect.poll(() => scriptQueries.some((query) => query.includes('chapter_id=chapter-002'))).toBeTruthy();
  await expect(page.getByRole('option', { name: '第二章剧本' })).toBeAttached();
  await expect(page.getByRole('option', { name: '第一章剧本' })).toHaveCount(0);
});
