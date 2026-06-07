import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `producer-one-click-evidence-user-${Date.now()}`;
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

test('producer keeps one-click generation evidence with model status and produced ids', async ({ page }) => {
  const generateRequests: Array<Record<string, unknown>> = [];

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path === '/api/v1/novels') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 'novel-001', title: '逆天至尊', genre: '玄幻', description: '少年逆境崛起。' }]),
      });
      return;
    }

    if (path === '/api/v1/llm/configs') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{
          id: 'text-config-001',
          config_model_id: 'doubao-text-001',
          api_model_id: 'doubao-seed-1-8-test',
          model_id: 'doubao-seed-1-8-test',
          model_type: 'chat',
          model_capabilities: ['text-generation'],
          provider_id: 'volcano',
          provider_name: '火山方舟',
          model_name: 'Doubao Seed 1.8',
          name: '默认文本模型',
          is_default: true,
          test_status: 'success',
          key_available: true,
        }]),
      });
      return;
    }

    if (path === '/api/v1/workflow' && request.method() === 'GET') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }

    if (path === '/api/v1/workflow/start') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ workflow_id: 'wf-created' }),
      });
      return;
    }

    if (path === '/api/v1/workflow/status/wf-created') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          workflow_id: 'wf-created',
          title: '逆天至尊 第一章 制片工程',
          status: 'active',
          current_step: 6,
          completed_steps: [1, 2, 3, 4, 5, 6],
          novel_id: 'novel-001',
          chapter_id: 'chapter-001',
          script_id: 'script-001',
          storyboard_id: 'storyboard-001',
          video_jobs: [],
          tts_jobs: [],
          synthesis_jobs: [],
        }),
      });
      return;
    }

    if (path === '/api/v1/workflow/wf-created/step') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
      return;
    }

    if (path === '/api/v1/short-video/workflow/wf-created/readiness') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          summary: { ready: false, score: 78, blocker_count: 0, warning_count: 1, shot_count: 5 },
          recommendations: ['继续生成参考图和配音。'],
        }),
      });
      return;
    }

    if (path === '/api/v1/chapters/novel/novel-001') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 'chapter-001', title: '第一章 少年出山', chapter_number: 1, content: '少年踏入风雪。' }]),
      });
      return;
    }

    if (path === '/api/v1/chapters/chapter-001/production-status') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ script_id: 'script-001', storyboard_id: 'storyboard-001', shot_count: 5, has_script: true, has_storyboard: true }),
      });
      return;
    }

    if (path === '/api/v1/chapters/chapter-001/generate-all') {
      const body = request.postData() ? JSON.parse(request.postData() || '{}') : {};
      generateRequests.push(body);
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          message: '已生成剧本、分镜和镜头',
          script_id: 'script-001',
          script_title: '第一章 少年出山 动漫剧本',
          storyboard_id: 'storyboard-001',
          storyboard_title: '第一章 少年出山 分镜',
          shot_count: 5,
        }),
      });
      return;
    }

    if (path === '/api/v1/story-bibles') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }

    if (path === '/api/v1/batch/list') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ total: 0, jobs: [] }) });
      return;
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });

  await page.goto('/producer');
  await page.getByRole('combobox').first().selectOption('novel-001');
  await page.getByRole('combobox').nth(1).selectOption('chapter-001');

  await page.getByRole('button', { name: /^全部$/ }).click();

  await expect.poll(() => generateRequests.length).toBe(1);
  expect(generateRequests[0]).toMatchObject({ model_config_id: 'text-config-001', shot_count: 5 });

  const evidence = page.getByTestId('producer-one-click-evidence');
  await expect(evidence).toBeVisible();
  await expect(evidence).toContainText('一键生成证据');
  await expect(evidence).toContainText('模式：全部');
  await expect(evidence).toContainText('默认文本模型');
  await expect(evidence).toContainText('已验证');
  await expect(evidence).toContainText('script-001');
  await expect(evidence).toContainText('storyboard-001');
  await expect(evidence).toContainText('镜头 5');
  await expect(evidence).toContainText('已自动创建本集工程');
});

test('producer keeps one-click generation failure evidence instead of only showing a toast', async ({ page }) => {
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path === '/api/v1/novels') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 'novel-001', title: '逆天至尊', genre: '玄幻' }]),
      });
      return;
    }

    if (path === '/api/v1/llm/configs') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{
          id: 'text-config-001',
          model_id: 'doubao-seed-1-8-test',
          model_type: 'chat',
          model_capabilities: ['text-generation'],
          provider_id: 'volcano',
          provider_name: '火山方舟',
          model_name: 'Doubao Seed 1.8',
          name: '默认文本模型',
          is_default: true,
          test_status: 'success',
          key_available: true,
        }]),
      });
      return;
    }

    if (path === '/api/v1/workflow' && request.method() === 'GET') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }

    if (path === '/api/v1/chapters/novel/novel-001') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 'chapter-001', title: '第一章 少年出山', chapter_number: 1 }]),
      });
      return;
    }

    if (path === '/api/v1/chapters/chapter-001/production-status') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ has_script: false, has_storyboard: false, shot_count: 0 }),
      });
      return;
    }

    if (path === '/api/v1/chapters/chapter-001/generate-storyboard') {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: '文本模型额度不足，无法生成分镜' }),
      });
      return;
    }

    if (path === '/api/v1/story-bibles') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }

    if (path === '/api/v1/batch/list') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ total: 0, jobs: [] }) });
      return;
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });

  await page.goto('/producer');
  await page.getByRole('combobox').first().selectOption('novel-001');
  await page.getByRole('combobox').nth(1).selectOption('chapter-001');

  await page.getByRole('button', { name: /^分镜$/ }).click();

  const evidence = page.getByTestId('producer-one-click-evidence');
  await expect(evidence).toBeVisible();
  await expect(evidence).toContainText('模式：分镜');
  await expect(evidence).toContainText('默认文本模型');
  await expect(evidence).toContainText('已验证');
  await expect(evidence).toContainText('生成失败');
  await expect(evidence).toContainText('文本模型额度不足，无法生成分镜');
});
