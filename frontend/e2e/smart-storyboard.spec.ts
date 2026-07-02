import { expect, test } from '@playwright/test';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `smart-storyboard-user-${Date.now()}`;
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

test('smart storyboard page matches a template and generates reviewable shots from a chapter', async ({ page }) => {
  const stamp = Date.now();
  const storyboardTitle = `E2E智能分镜-${stamp}`;

  await page.goto('/dashboard');
  await expect(page.locator('body')).toBeVisible();

  const novel = await apiPost(page, '/novels', {
    title: `E2E智能分镜小说-${stamp}`,
    description: '赛博都市里的少年被敌人追击，在雨夜中爆发隐藏能力。',
    genre: 'action',
    style: 'anime',
    status: 'writing',
  });
  const chapter = await apiPost(page, '/chapters', {
    novel_id: novel.id,
    title: '雨夜追击',
    chapter_number: 1,
    content: '敌人从巷口冲出，机车轰鸣，主角翻越护栏躲避爆炸，在雨幕中反击。',
  });

  await page.goto('/storyboards');
  await expect(page.getByRole('heading', { name: '分镜设计' })).toBeVisible();

  await page.getByRole('button', { name: '新建分镜' }).first().click();
  const modal = page.locator('.fixed').filter({ hasText: '智能生成' });
  await expect(modal).toBeVisible();

  await modal.locator('select').nth(0).selectOption(novel.id);
  await expect(modal.getByText('选择章节')).toBeVisible();
  await modal.locator('select').nth(1).selectOption(chapter.id);
  await modal.locator('input[type="number"]').fill('4');
  await page.getByPlaceholder('例如：第一章 分镜A').fill(storyboardTitle);

  await expect(modal.getByText(/匹配模板：/)).toBeVisible({ timeout: 10000 });

  await modal.getByRole('button', { name: /智能生成分镜与镜头/ }).click();
  await expect(page.getByText('智能分镜已生成')).toBeVisible({ timeout: 15_000 });

  await expect(page.getByText(storyboardTitle).first()).toBeVisible({ timeout: 15000 });

  const scripts = await apiGet(page, '/scripts');
  const generatedScript = scripts.find((script: any) =>
    script.title.includes('雨夜追击') && script.title.includes('自动改编脚本')
  );
  expect(generatedScript).toBeTruthy();

  const storyboards = await apiGet(page, `/storyboards/script/${generatedScript.id}`);
  const storyboard = storyboards.find((item: any) => item.title === storyboardTitle);
  expect(storyboard).toBeTruthy();

  const shots = await apiGet(page, `/shots/storyboard/${storyboard.id}`);
  expect(shots).toHaveLength(4);
  expect(shots[0].visual_description).toBeTruthy();
  expect(shots[0].prompt).toBeTruthy();
  expect(shots[0].camera_angle).toBeTruthy();
  expect(shots[0].camera_movement).toBeTruthy();
  expect(shots[0].emotion).toBeTruthy();
  expect(shots[0].lighting).toBeTruthy();
  expect(shots[0].color_grading).toBeTruthy();
  expect(shots[0].extra_data?.review_status).toBe('pending_review');
});
