import { expect, test } from '@playwright/test';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `chapter-ai-user-${Date.now()}`;
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

async function apiPost(page: any, endpoint: string, body: any) {
  return page.evaluate(async ({ url, payload }) => {
    const token = localStorage.getItem('auth_token');
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(`${url} failed: HTTP ${response.status} ${JSON.stringify(data)}`);
    }
    return data;
  }, { url: `${API_BASE}${endpoint}`, payload: body });
}

async function apiGet(page: any, endpoint: string) {
  return page.evaluate(async (url) => {
    const token = localStorage.getItem('auth_token');
    const response = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(`${url} failed: HTTP ${response.status} ${JSON.stringify(data)}`);
    }
    return data;
  }, `${API_BASE}${endpoint}`);
}

test('chapter edit page auto-saves and AI extends content into the database', async ({ page }) => {
  test.setTimeout(60_000);
  const stamp = Date.now();
  await page.goto('/dashboard');
  await expect(page.locator('body')).toBeVisible();

  const novel = await apiPost(page, '/novels', {
    title: `E2E章节AI小说-${stamp}`,
    description: '角色：林澈\n场景：星港\n道具：星门钥匙\n事件：星门开启',
    genre: '科幻',
    status: 'writing',
  });
  const chapter = await apiPost(page, '/chapters', {
    novel_id: novel.id,
    title: '第一章 星港',
    chapter_number: 1,
    content: '林澈握着星门钥匙进入星港。',
  });

  await page.goto(`/novels/${novel.id}/chapters/${chapter.id}/edit`);
  await expect(page.getByRole('heading', { name: '编辑章节' })).toBeVisible();

  const contentBox = page.getByPlaceholder(/开始编写章节内容/);
  await contentBox.fill('林澈握着星门钥匙进入星港，远处的星门忽然亮起。');
  await expect(page.getByText('已自动保存')).toBeVisible({ timeout: 6000 });

  let persisted = await apiGet(page, `/chapters/${chapter.id}`);
  expect(persisted.content).toContain('远处的星门忽然亮起');

  await page.getByPlaceholder(/补充要求/).fill('续写时保留星港和星门钥匙，并制造追击悬念');
  await page.getByRole('button', { name: /续写内容/ }).click();
  await expect(page.getByText('章节已续写并保存')).toBeVisible({ timeout: 30_000 });

  persisted = await apiGet(page, `/chapters/${chapter.id}`);
  expect(persisted.content).toContain('林澈握着星门钥匙进入星港');
  expect(persisted.content.length).toBeGreaterThan('林澈握着星门钥匙进入星港，远处的星门忽然亮起。'.length);
  expect(persisted.status).toBe('completed');

  const entities = await apiPost(page, '/story-bibles/entities/extract', {
    chapter_id: chapter.id,
    persist: false,
  });
  expect(entities.entities.length).toBeGreaterThan(0);
});

test('chapter edit page can continue an empty next chapter from previous context', async ({ page }) => {
  test.setTimeout(60_000);
  const stamp = Date.now();
  await page.goto('/dashboard');
  await expect(page.locator('body')).toBeVisible();

  const novel = await apiPost(page, '/novels', {
    title: `E2E空章续写小说-${stamp}`,
    description: '角色：谭云\n场景：山门废墟\n道具：祖传玉简\n事件：重生后发现仇敌追踪而来',
    genre: '修仙',
    status: 'writing',
  });
  const firstChapter = await apiPost(page, '/chapters', {
    novel_id: novel.id,
    title: '第一章 重生之路',
    chapter_number: 1,
    content: '谭云在山门废墟中醒来，掌心的祖传玉简微微发烫，远处传来仇敌的脚步声。',
  });
  const nextChapter = await apiPost(page, '/chapters', {
    novel_id: novel.id,
    title: '第2章',
    chapter_number: 2,
    content: '',
  });

  await page.goto(`/novels/${novel.id}/chapters/${nextChapter.id}/edit`);
  await expect(page.getByRole('heading', { name: '编辑章节' })).toBeVisible();
  await expect(page.getByText('0 字')).toBeVisible();

  await page.getByPlaceholder(/补充要求/).fill('承接上一章脚步声，写出谭云发现追兵并保护祖传玉简');
  await page.getByRole('button', { name: /续写内容|生成本章内容/ }).click();
  await expect(page.getByText('章节已续写并保存')).toBeVisible({ timeout: 30_000 });

  const persisted = await apiGet(page, `/chapters/${nextChapter.id}`);
  expect(persisted.content.length).toBeGreaterThan(firstChapter.content.length);
  expect(persisted.content).toContain('谭云');
  expect(persisted.content).toContain('祖传玉简');
  expect(persisted.status).toBe('completed');
});

test('chapter list edit action opens the dedicated editor and saves long content', async ({ page }) => {
  test.setTimeout(45_000);
  const stamp = Date.now();
  await page.goto('/dashboard');
  await expect(page.locator('body')).toBeVisible();

  const novel = await apiPost(page, '/novels', {
    title: `E2E章节入口小说-${stamp}`,
    description: '角色：陆青；场景：山门；事件：试炼开启。',
    genre: '玄幻',
    status: 'writing',
  });
  const chapter = await apiPost(page, '/chapters', {
    novel_id: novel.id,
    title: '第一章 山门试炼',
    chapter_number: 1,
    content: '陆青站在山门前，等待试炼钟声响起。',
  });

  await page.goto(`/novels/${novel.id}/chapters`);
  await expect(page.getByRole('heading', { name: /章节管理/ })).toBeVisible();
  await page.getByLabel(`编辑章节 ${chapter.title}`).click();
  await expect(page).toHaveURL(new RegExp(`/novels/${novel.id}/chapters/${chapter.id}/edit$`));
  await expect(page.getByRole('heading', { name: '编辑章节' })).toBeVisible();

  const longContent = Array.from(
    { length: 30 },
    (_, index) => `第${index + 1}段：陆青沿着山门石阶向上，试炼钟声一次比一次清晰。`
  ).join('\n');
  await page.getByPlaceholder(/开始编写章节内容/).fill(longContent);
  await expect(page.getByText('已自动保存')).toBeVisible({ timeout: 6000 });

  const persisted = await apiGet(page, `/chapters/${chapter.id}`);
  expect(persisted.content).toContain('第30段');
  expect(persisted.content.length).toBeGreaterThan(chapter.content.length);
});

test('novel detail supports AI-assisted chapter creation and Chinese settings controls', async ({ page }) => {
  test.setTimeout(60_000);
  const stamp = Date.now();
  await page.goto('/dashboard');
  await expect(page.locator('body')).toBeVisible();

  const novel = await apiPost(page, '/novels', {
    title: `E2E章节新建辅助小说-${stamp}`,
    description: '角色：陆青；场景：山门；道具：试炼令；事件：山门试炼开启。',
    genre: 'xianxia',
    status: 'draft',
  });
  const firstChapter = await apiPost(page, '/chapters', {
    novel_id: novel.id,
    title: '第一章 山门钟声',
    chapter_number: 1,
    content: '陆青握着试炼令站在山门前，钟声响起，众弟子开始入山。',
  });

  await page.goto(`/novels/${novel.id}`);
  await expect(page.getByText(/仙侠 · 草稿/)).toBeVisible();
  await page.getByRole('button', { name: /新建章节/ }).click();

  const chapterPanel = page.locator('[role="tabpanel"]').filter({ hasText: 'AI 续写下一章' });
  await chapterPanel.getByPlaceholder(/章节内容或创作方向/).fill('陆青进入山门后发现试炼令发烫，石阶尽头出现新的敌人。');
  await chapterPanel.getByRole('button', { name: /提炼标题/ }).click();
  await expect(chapterPanel.getByPlaceholder(/章节标题/)).toHaveValue(/第2章/);

  await chapterPanel.getByRole('button', { name: /AI 续写下一章/ }).click();
  await expect(page.getByText('AI 已续写下一章')).toBeVisible({ timeout: 30_000 });

  const chapters = await apiGet(page, `/chapters/novel/${novel.id}`);
  expect(chapters.length).toBeGreaterThanOrEqual(2);
  const generatedChapter = chapters.find((item: any) => item.id !== firstChapter.id);
  expect(generatedChapter?.content || '').toContain('陆青');
  expect(generatedChapter?.title || '').toMatch(/^第2章/);
  expect(generatedChapter?.title).not.toBe('第2章');

  await page.getByRole('tab', { name: /设置/ }).click();
  const settingsPanel = page.locator('[role="tabpanel"]').filter({ hasText: '小说设置' });
  await settingsPanel.locator('select').first().selectOption('玄幻');
  await settingsPanel.locator('select').nth(1).selectOption('writing');
  await settingsPanel.getByRole('button', { name: /保存修改/ }).click();
  await expect(page.getByText('小说设置已保存')).toBeVisible({ timeout: 10_000 });

  const persistedNovel = await apiGet(page, `/novels/${novel.id}`);
  expect(persistedNovel.genre).toBe('玄幻');
  expect(persistedNovel.status).toBe('writing');
});

test('chapter content page exposes AI writing controls and persists generated content', async ({ page }) => {
  test.setTimeout(60_000);
  const stamp = Date.now();
  await page.goto('/dashboard');
  await expect(page.locator('body')).toBeVisible();

  const novel = await apiPost(page, '/novels', {
    title: `E2E章节正文AI小说-${stamp}`,
    description: '角色：沈砚\n场景：旧城雨巷\n道具：铜铃\n事件：密信被夺',
    genre: '悬疑',
    status: 'writing',
  });
  const chapter = await apiPost(page, '/chapters', {
    novel_id: novel.id,
    title: '第一章 雨巷铜铃',
    chapter_number: 1,
    content: '沈砚听见铜铃在旧城雨巷深处响起。',
  });

  await page.goto(`/novels/${novel.id}/chapters/${chapter.id}`);
  await expect(page.getByText('AI智能编写')).toBeVisible();
  await expect(page.getByRole('button', { name: /智能编写/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /续写内容/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /润色内容/ })).toBeVisible();

  await page.getByPlaceholder(/补充要求/).fill('续写时保留旧城雨巷、铜铃和密信线索');
  await page.getByRole('button', { name: /续写内容/ }).click();
  await expect(page.getByText('章节已续写并保存')).toBeVisible({ timeout: 30_000 });

  const persisted = await apiGet(page, `/chapters/${chapter.id}`);
  expect(persisted.content).toContain('沈砚听见铜铃');
  expect(persisted.content.length).toBeGreaterThan(chapter.content.length);
  expect(persisted.status).toBe('completed');
});
