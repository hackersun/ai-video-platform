import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `novel-overview-user-${Date.now()}`;
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

test('作品详情首屏用左侧封面和右侧简介展示作品概览', async ({ page }) => {
  const novel = {
    id: 'novel-overview',
    user_id: 'test-user',
    title: '逆天至尊',
    description: '少年重生归来，凭借前世记忆踏上修仙复仇之路，逐步揭开宗门、秘境和上古神器之间的因果。',
    genre: '修仙',
    status: 'draft',
    word_count: 1126,
    tags: [],
    cover_url: '/static/generated/images/novel-cover-test.jpg',
    source: 'manual',
    created_at: '2026-06-01T00:00:00',
    updated_at: '2026-06-01T00:00:00',
  };
  const chapters = [{
    id: 'chapter-1',
    novel_id: novel.id,
    title: '第一章 重生之路',
    chapter_number: 1,
    content: '少年在宗门废墟中醒来。',
    word_count: 1126,
    status: 'completed',
    created_at: '2026-06-01T00:00:00',
    updated_at: '2026-06-01T00:00:00',
  }];

  await page.route('**/*', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (!url.pathname.includes('/api/v1')) {
      await route.continue();
      return;
    }

    const path = url.pathname.slice(url.pathname.indexOf('/api/v1') + '/api/v1'.length);
    const method = request.method();

    if (method === 'GET' && path === '/novels/novel-overview') {
      await route.fulfill({ json: novel });
      return;
    }
    if (method === 'GET' && path === '/chapters/novel/novel-overview') {
      await route.fulfill({ json: chapters });
      return;
    }
    if (method === 'GET' && path === '/characters') {
      await route.fulfill({ json: [{ id: 'char-1', name: '谭云', description: '重生少年，隐忍果决。' }] });
      return;
    }
    if (method === 'GET' && path === '/scripts') {
      await route.fulfill({ json: [] });
      return;
    }
    if (method === 'GET' && path === '/story-bibles') {
      await route.fulfill({ json: [] });
      return;
    }
    if (method === 'GET' && path === '/novels/novel-overview/series-plan') {
      await route.fulfill({ status: 404, json: { detail: 'not found' } });
      return;
    }
    if (method === 'GET' && path === '/video/jobs') {
      await route.fulfill({ json: [] });
      return;
    }
    if (method === 'GET' && path === '/llm/configs') {
      await route.fulfill({ json: [] });
      return;
    }

    await route.fulfill({ json: [] });
  });

  await page.goto('/novels/novel-overview');

  const overview = page.getByTestId('novel-overview-card');
  await expect(overview).toBeVisible();
  await expect(overview.getByTestId('novel-cover-panel')).toBeVisible();
  await expect(overview.getByTestId('novel-summary-panel')).toContainText('少年重生归来');
  await expect(overview.getByText('章节 1')).toBeVisible();
  await expect(overview.getByText('角色 1')).toBeVisible();
  await expect(page.getByText('选择封面画面风格', { exact: true })).toHaveCount(0);

  await page.getByRole('button', { name: '生成封面' }).click();

  await expect(page.getByRole('dialog', { name: '生成封面图片' })).toBeVisible();
  await expect(page.getByText('先选择封面画面风格')).toBeVisible();
  await expect(page.getByText('选择封面画面风格', { exact: true })).toBeVisible();
  await expect(page.getByTestId('image-style-template').first()).toBeVisible();
});
