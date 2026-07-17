import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

const novel = {
  id: 'novel-001',
  title: '雨夜铜铃',
  description: '旧城雨夜里，少年林澈追查铜铃异响，发现家族旧案与灵界裂缝有关。',
  genre: '悬疑',
  status: 'writing',
  chapter_count: 2,
  character_count: 3,
  created_at: '2026-07-08T10:00:00.000Z',
  updated_at: '2026-07-08T12:00:00.000Z',
};

const chapters = [
  {
    id: 'chapter-001',
    novel_id: 'novel-001',
    title: '第一章 雨巷铜铃',
    content: '雨落在青石巷里，铜铃声从废弃戏楼深处传来。林澈握紧伞柄，第一次看见墙上的影子比自己先回头。',
    chapter_number: 1,
    word_count: 1280,
    status: 'completed',
    created_at: '2026-07-08T10:00:00.000Z',
    updated_at: '2026-07-08T11:00:00.000Z',
  },
  {
    id: 'chapter-002',
    novel_id: 'novel-001',
    title: '第二章 戏楼回声',
    content: '戏台上的红幕无风自动，铜铃碎片映出十年前的火光。林澈意识到父亲留下的信并不是遗书。',
    chapter_number: 2,
    word_count: 1420,
    status: 'draft',
    created_at: '2026-07-08T12:00:00.000Z',
    updated_at: '2026-07-08T13:00:00.000Z',
  },
];

const scripts = [
  {
    id: 'script-001',
    title: '雨巷铜铃 动漫短剧脚本',
    description: '林澈在雨巷追踪铜铃声，进入废弃戏楼。',
    content: '【场景】雨夜旧巷。林澈听见铜铃声，镜头贴近伞面雨滴。林澈：这声音，和父亲失踪那晚一样。',
    genre: 'suspense',
    style: 'cinematic_anime',
    status: 'completed',
    novel_id: 'novel-001',
    chapter_id: 'chapter-001',
    duration: 1.5,
    created_at: '2026-07-08T13:00:00.000Z',
    updated_at: '2026-07-08T14:00:00.000Z',
  },
];

test.beforeEach(async ({ page }) => {
  const userId = `novel-workbench-${Date.now()}`;
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

async function mockNovelApis(page: any) {
  await page.route('**/api/v1/asset-style-templates**', async (route: any) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ templates: [] }) });
  });
  await page.route('**/api/v1/characters**', async (route: any) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });
  await page.route('**/api/v1/story-bibles/entities**', async (route: any) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });
  await page.route('**/api/v1/story-bibles**', async (route: any) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });
  await page.route('**/api/v1/novels/novel-001/series-plan**', async (route: any) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({}) });
  });
  await page.route('**/api/v1/entity-review/summary**', async (route: any) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ approved_count: 0, candidate_count: 0 }) });
  });
  await page.route('**/api/v1/novels/production-entries**', async (route: any) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ entries: {}, count: 0 }) });
  });
  await page.route('**/api/v1/novels/novel-001', async (route: any) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(novel) });
  });
  await page.route('**/api/v1/chapters/chapter-001', async (route: any) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(chapters[0]) });
  });
  await page.route('**/api/v1/novels', async (route: any) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([novel]) });
  });
  await page.route('**/api/v1/chapters/novel/novel-001', async (route: any) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(chapters) });
  });
  await page.route('**/api/v1/storyboards/script/script-001', async (route: any) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });
  await page.route('**/api/v1/storyboards/script/**', async (route: any) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });
  await page.route('**/api/v1/storyboards**', async (route: any) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });
  await page.route('**/api/v1/video/jobs**', async (route: any) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });
  await page.route('**/api/v1/scripts/script-001/versions', async (route: any) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });
  await page.route('**/api/v1/scripts/script-001/check-consistency', async (route: any) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ issue_count: 0, issues: [], summary: {} }) });
  });
  await page.route('**/api/v1/scripts/script-001', async (route: any) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(scripts[0]) });
  });
  await page.route('**/api/v1/scripts**', async (route: any) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/scripts/script-001/versions') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
      return;
    }
    if (path === '/api/v1/scripts/script-001/check-consistency') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ issue_count: 0, issues: [], summary: {} }) });
      return;
    }
    if (path === '/api/v1/scripts/script-001') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(scripts[0]) });
      return;
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(scripts) });
  });
  await page.route('**/api/v1/llm/configs', async (route: any) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });
}

test('novel list exposes an operations preview with AI next actions', async ({ page }) => {
  await mockNovelApis(page);

  await page.goto('/novels');

  await expect(page.getByRole('heading', { name: '小说管理' })).toBeVisible();
  await expect(page.getByRole('heading', { name: '作品预览' })).toBeVisible();
  await expect(page.getByRole('complementary').getByText('旧城雨夜里，少年林澈追查铜铃异响')).toBeVisible();
  await expect(page.getByText('AI 下一步')).toBeVisible();
  await expect(page.getByRole('link', { name: /分析制作资产/ })).toHaveAttribute('href', '/novels/novel-001/asset-analysis');
});

test('chapter list shows readable chapter previews and AI-assisted next steps', async ({ page }) => {
  await mockNovelApis(page);

  await page.goto('/novels/novel-001/chapters');

  await expect(page.getByRole('heading', { name: /章节管理/ })).toBeVisible();
  await expect(page.getByText('正文预览').first()).toBeVisible();
  await expect(page.getByText('雨落在青石巷里')).toBeVisible();
  await expect(page.getByRole('link', { name: /生成剧本/ }).first()).toHaveAttribute('href', '/scripts?novel_id=novel-001&chapter_id=chapter-001');
});

test('script list provides a script preview and production actions', async ({ page }) => {
  await mockNovelApis(page);

  await page.goto('/scripts');

  await expect(page.getByRole('heading', { name: '剧本管理' })).toBeVisible();
  await expect(page.getByRole('heading', { name: '剧本预览' })).toBeVisible();
  await expect(page.getByRole('complementary').getByText('镜头贴近伞面雨滴')).toBeVisible();
  await expect(page.getByText('AI 下一步')).toBeVisible();
  await expect(page.getByRole('button', { name: /生成分镜/ }).first()).toBeVisible();
});

test('novel detail exposes a reading preview and AI production shortcuts', async ({ page }) => {
  await mockNovelApis(page);

  await page.goto('/novels/novel-001');

  await expect(page.getByRole('heading', { name: '作品阅读预览' })).toBeVisible();
  await expect(page.getByTestId('novel-summary-panel').getByText('雨落在青石巷里')).toBeVisible();
  await expect(page.getByText('AI 下一步')).toBeVisible();
  await expect(page.getByTestId('novel-summary-panel').getByRole('link', { name: /分析制作资产/ })).toHaveAttribute('href', '/novels/novel-001/asset-analysis');
});

test('chapter detail and editor keep preview beside AI writing actions', async ({ page }) => {
  await mockNovelApis(page);

  await page.goto('/novels/novel-001/chapters/chapter-001');

  await expect(page.getByRole('heading', { name: '章节阅读预览' })).toBeVisible();
  await expect(page.getByText('正文预览')).toBeVisible();
  await expect(page.getByRole('complementary').getByText('雨落在青石巷里')).toBeVisible();
  await expect(page.getByRole('button', { name: /智能编写本章/ })).toBeVisible();
  await expect(page.getByRole('link', { name: /生成剧本/ })).toHaveAttribute('href', '/scripts?novel_id=novel-001&chapter_id=chapter-001');

  await page.goto('/novels/novel-001/chapters/chapter-001/edit');

  await expect(page.getByRole('heading', { name: '章节写作助手' })).toBeVisible();
  await expect(page.getByText('当前正文预览')).toBeVisible();
  await expect(page.getByRole('complementary').getByText('雨落在青石巷里')).toBeVisible();
  await expect(page.getByRole('button', { name: /续写内容/ })).toBeVisible();
});

test('script detail provides a production assistant beside the editor', async ({ page }) => {
  await mockNovelApis(page);

  await page.goto('/scripts/script-001');

  await expect(page.getByRole('heading', { name: '剧本生产助手' })).toBeVisible();
  await expect(page.getByText('剧本预览')).toBeVisible();
  await expect(page.getByRole('complementary').getByText('镜头贴近伞面雨滴')).toBeVisible();
  await expect(page.getByRole('button', { name: /AI 润色正文/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /生成分镜/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /一致性检查/ })).toBeVisible();
});
