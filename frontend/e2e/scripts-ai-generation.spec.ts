import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `scripts-ai-generation-user-${Date.now()}`;
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

test('custom AI script generation uses script assist and preserves novel chapter context', async ({ page }) => {
  const codingPlanCalls: string[] = [];
  const aiAssistRequests: Array<Record<string, unknown>> = [];
  const createScriptRequests: Array<Record<string, unknown>> = [];

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path === '/api/v1/novels') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 'novel-001', title: '逆天至尊', genre: 'xuanhuan' }]),
      });
      return;
    }

    if (path === '/api/v1/llm/configs') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{
          id: 'model-text-001',
          name: '已验证文本模型',
          provider_id: 'provider-001',
          model_name: 'doubao-test',
          model_id: 'model-text-001',
          model_type: 'text',
          capabilities: ['text'],
          is_default: true,
          test_status: 'success',
          key_available: true,
        }]),
      });
      return;
    }

    if (path === '/api/v1/chapters/novel/novel-001') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 'chapter-002', novel_id: 'novel-001', title: '第二章 宗门试炼', chapter_number: 2 }]),
      });
      return;
    }

    if (path === '/api/v1/scripts' && request.method() === 'GET') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }

    if (path === '/api/v1/scripts/ai-assist') {
      const body = request.postData() ? JSON.parse(request.postData() || '{}') : {};
      aiAssistRequests.push(body);
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          title: '第二章 宗门试炼 剧本',
          description: '围绕宗门试炼改编的动漫短剧剧本。',
          content: '【第1场】宗门试炼场\n镜头：少年踏入试炼台。\n少年：我不会退。',
          warnings: ['请人工确认角色名和章节设定。'],
        }),
      });
      return;
    }

    if (path === '/api/v1/scripts' && request.method() === 'POST') {
      const body = request.postData() ? JSON.parse(request.postData() || '{}') : {};
      createScriptRequests.push(body);
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'script-002',
          user_id: 'user-001',
          novel_id: body.novel_id,
          chapter_id: body.chapter_id,
          title: body.title,
          description: body.description,
          content: body.content,
          genre: body.genre,
          style: body.style,
          duration: null,
          status: 'completed',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }),
      });
      return;
    }

    if (path === '/api/v1/coding-plan/storyboard') {
      codingPlanCalls.push(path);
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ storyboard: '错误接口返回的技术分镜' }),
      });
      return;
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });

  await page.goto('/scripts?novel_id=novel-001&chapter_id=chapter-002');
  await expect(page.getByRole('heading', { name: '剧本管理' })).toBeVisible();

  await page.getByRole('button', { name: /AI生成剧本/ }).click();
  await page.getByRole('button', { name: '自定义描述' }).click();
  await page.getByPlaceholder(/描述你想要生成的剧本内容/).fill('宗门试炼，少年被长老质疑，主角用行动证明自己。');
  await page.getByRole('button', { name: '开始生成' }).click();

  await expect.poll(() => aiAssistRequests.length, { timeout: 3_000 }).toBe(1);
  expect(codingPlanCalls).toHaveLength(0);
  expect(aiAssistRequests[0]).toMatchObject({
    title: '第二章 宗门试炼 剧本',
    mode: 'short_drama',
    model_config_id: 'model-text-001',
  });
  expect(String(aiAssistRequests[0].content)).toContain('宗门试炼');

  await expect(page.getByText('生成结果')).toBeVisible();
  await page.getByRole('button', { name: '创建剧本' }).click();

  await expect.poll(() => createScriptRequests.length, { timeout: 3_000 }).toBe(1);
  expect(createScriptRequests[0]).toMatchObject({
    novel_id: 'novel-001',
    chapter_id: 'chapter-002',
    title: '第二章 宗门试炼 剧本',
    genre: 'xuanhuan',
    style: 'anime',
  });
});
