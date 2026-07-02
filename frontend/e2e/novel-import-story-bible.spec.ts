import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `novel-import-user-${Date.now()}`;
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

test('imports txt chapters and drives entity and Story Bible actions', async ({ page }) => {
  const novel = {
    id: 'novel-imported',
    user_id: 'test-user',
    title: '星海试炼',
    description: '从文本导入，共 2 章',
    genre: '科幻',
    status: 'draft',
    word_count: 120,
    tags: [],
    cover_url: null,
    source: 'manual',
    created_at: '2026-05-10T00:00:00',
    updated_at: '2026-05-10T00:00:00',
  };
  const previewChapters = [
    {
      title: '第一章 启航',
      chapter_number: 1,
      word_count: 7,
      preview: '林澈进入星舰。',
    },
    {
      title: '第二章 星门',
      chapter_number: 2,
      word_count: 9,
      preview: '星门在远方开启。',
    },
  ];
  let chapters: any[] = [];
  const characters = [{
    id: 'char-lin',
    user_id: 'test-user',
    name: '林澈',
    description: '飞船领航员',
    appearance: '',
    personality: '',
    voice: '',
    avatar: '',
    tags: ['主角'],
    created_at: '2026-05-10T00:00:00',
    updated_at: '2026-05-10T00:00:00',
  }];
  let storyBibles: any[] = [];

  await page.route('**/*', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (!url.pathname.includes('/api/v1')) {
      await route.continue();
      return;
    }
    const path = url.pathname.slice(url.pathname.indexOf('/api/v1') + '/api/v1'.length);
    const method = request.method();

    if (method === 'GET' && path === '/novels') {
      await route.fulfill({ json: [] });
      return;
    }

    if (method === 'GET' && path === '/novels/novel-imported') {
      await route.fulfill({ json: novel });
      return;
    }

    if (method === 'POST' && path === '/novels/import/preview') {
      await route.fulfill({
        status: 201,
        json: {
          id: 'import-job-1',
          user_id: 'test-user',
          filename: '星海试炼.txt',
          content_type: 'text/plain',
          status: 'previewed',
          title: '星海试炼',
          description: null,
          chapter_count: previewChapters.length,
          word_count: 16,
          metadata: { parser: 'heading' },
          chapters: previewChapters,
          novel_id: null,
          error_message: null,
          created_at: '2026-05-10T00:00:00',
          updated_at: '2026-05-10T00:00:00',
        },
      });
      return;
    }

    if (method === 'POST' && path === '/novels/import/confirm') {
      chapters = previewChapters.map((chapter) => ({
        id: `chapter-${chapter.chapter_number}`,
        novel_id: novel.id,
        user_id: 'test-user',
        title: chapter.title,
        content: chapter.preview,
        chapter_number: chapter.chapter_number,
        word_count: chapter.word_count,
        status: 'completed',
        created_at: '2026-05-10T00:00:00',
        updated_at: '2026-05-10T00:00:00',
      }));
      await route.fulfill({
        status: 201,
        json: { ...novel, source: 'imported', chapters },
      });
      return;
    }

    if (method === 'GET' && path === '/chapters/novel/novel-imported') {
      await route.fulfill({ json: chapters });
      return;
    }

    if (method === 'GET' && path === '/characters') {
      await route.fulfill({ json: characters });
      return;
    }

    if (method === 'POST' && path === '/story-bibles/entities/extract') {
      await route.fulfill({
        json: {
          novel_id: novel.id,
          chapter_id: null,
          entities: [
            { id: 'entity-char', entity_type: 'character', name: '林澈', source: 'deterministic' },
            { id: 'entity-scene', entity_type: 'scene', name: '星舰', source: 'deterministic' },
            { id: 'entity-prop', entity_type: 'prop', name: '星门', source: 'deterministic' },
            { id: 'entity-event', entity_type: 'event', name: '星门开启', source: 'deterministic' },
          ],
        },
      });
      return;
    }

    if (method === 'GET' && path === '/scripts') {
      await route.fulfill({ json: [] });
      return;
    }

    if (method === 'GET' && path === '/story-bibles') {
      await route.fulfill({ json: storyBibles });
      return;
    }

    if (method === 'POST' && path === '/story-bibles/generate-from-novel') {
      const body = JSON.parse(request.postData() || '{}');
      const bible = {
        id: 'bible-1',
        user_id: 'test-user',
        ...body,
        title: body.title || '星海试炼 Story Bible',
        character_rules: [{ name: '林澈', description: '领航员' }],
        scene_rules: [{ name: '星舰', description: '核心场景' }],
        prop_rules: [{ name: '星门', description: '关键装置' }],
        event_timeline: [],
        created_at: '2026-05-10T00:00:00',
        updated_at: '2026-05-10T00:00:00',
      };
      storyBibles = [bible];
      await route.fulfill({ status: 201, json: bible });
      return;
    }

    if (method === 'POST' && path === '/story-bibles/check-consistency') {
      await route.fulfill({
        json: {
          story_bible_id: 'bible-1',
          checked_entity_count: 4,
          issue_count: 0,
          issues: [],
        },
      });
      return;
    }

    await route.fulfill({ status: 404, json: { detail: `${method} ${path} not mocked` } });
  });

  await page.goto('/novels');
  await expect(page.getByText('没有找到小说')).toBeVisible();
  await page.locator('input[type="file"]').setInputFiles({
    name: '星海试炼.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('第一章 启航\n林澈进入星舰。\n\n第二章 星门\n星门在远方开启。'),
  });

  await expect(page.getByText('已解析 2 章')).toBeVisible();
  await page.getByRole('button', { name: /确认导入/ }).click();
  await page.waitForURL(/\/novels\/novel-imported/);

  await page.getByRole('tab', { name: /角色 \(/ }).click();
  await page.getByRole('button', { name: /提取实体/ }).click();
  await expect(page.locator('[role="tabpanel"]').filter({ hasText: '已提取 4 个实体' })).toBeVisible();

  await page.getByRole('tab', { name: /Story Bible \(/ }).click();
  await page.getByRole('button', { name: /^生成$/ }).click();
  await expect(page.locator('[role="tabpanel"]').filter({ hasText: 'Story Bible 已生成' })).toBeVisible();

  await page.getByRole('button', { name: /^检查$/ }).click();
  await expect(page.getByText('检查完成：0 个提示')).toBeVisible();
});
