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

  const contentBox = page.getByPlaceholder('开始编写章节内容...');
  await contentBox.fill('林澈握着星门钥匙进入星港，远处的星门忽然亮起。');
  await expect(page.getByText('已自动保存')).toBeVisible({ timeout: 6000 });

  let persisted = await apiGet(page, `/chapters/${chapter.id}`);
  expect(persisted.content).toContain('远处的星门忽然亮起');

  await page.getByPlaceholder(/补充要求/).fill('续写时保留星港和星门钥匙，并制造追击悬念');
  const dialogPromise = page.waitForEvent('dialog', { timeout: 30_000 });
  await page.getByRole('button', { name: /续写内容/ }).click();
  const dialog = await dialogPromise;
  const dialogMessage = dialog.message();
  await dialog.accept();
  expect(dialogMessage).toContain('章节已续写并保存');

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
  const dialogPromise = page.waitForEvent('dialog', { timeout: 30_000 });
  await page.getByRole('button', { name: /续写内容/ }).click();
  const dialog = await dialogPromise;
  const dialogMessage = dialog.message();
  await dialog.accept();
  expect(dialogMessage).toContain('章节已续写并保存');

  const persisted = await apiGet(page, `/chapters/${chapter.id}`);
  expect(persisted.content).toContain('沈砚听见铜铃');
  expect(persisted.content.length).toBeGreaterThan(chapter.content.length);
  expect(persisted.status).toBe('completed');
});
