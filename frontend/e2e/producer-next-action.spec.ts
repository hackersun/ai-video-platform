import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `producer-next-action-user-${Date.now()}`;
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

test('producer next action posts only the selected assistant action code', async ({ page }) => {
  const assistantRequests: Array<Record<string, unknown>> = [];

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
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }

    if (path === '/api/v1/workflow') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{
          workflow_id: 'wf-001',
          title: '逆天至尊 第一章',
          status: 'active',
          current_step: 6,
          novel_id: 'novel-001',
          chapter_id: 'chapter-001',
          script_id: 'script-001',
          storyboard_id: 'storyboard-001',
          video_job_ids: [],
          tts_job_ids: [],
          synthesis_job_ids: [],
        }]),
      });
      return;
    }

    if (path === '/api/v1/workflow/status/wf-001') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          workflow_id: 'wf-001',
          title: '逆天至尊 第一章',
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

    if (path === '/api/v1/short-video/workflow/wf-001/readiness') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          summary: { ready: false, score: 72, blocker_count: 0, warning_count: 1 },
          recommendations: ['先生成资产定稿包。'],
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
        body: JSON.stringify({ script_id: 'script-001', storyboard_id: 'storyboard-001', shot_count: 2 }),
      });
      return;
    }

    if (path === '/api/v1/story-bibles') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }

    if (path === '/api/v1/production-control/workflow/wf-001/producer-assistant') {
      const body = request.postData() ? JSON.parse(request.postData() || '{}') : {};
      assistantRequests.push(body);
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          workflow_id: 'wf-001',
          summary: {
            ready: false,
            next_action: {
              code: 'build_production_pack',
              label: '生成资产定稿包',
              detail: '锁定角色、场景、道具参考资产，避免多集生成漂移。',
              status: 'ready',
              priority: 'P0',
            },
            action_count: 1,
            executed_count: body.auto_fix ? 1 : 0,
          },
          actions: [{
            code: 'build_production_pack',
            label: '生成资产定稿包',
            detail: '锁定角色、场景、道具参考资产，避免多集生成漂移。',
            status: 'ready',
            priority: 'P0',
          }],
          executed: body.auto_fix ? [{ code: 'build_production_pack', result: { lock_count: 3 } }] : [],
          media_audit: { missing_count: 0 },
          quality: { average_score: 72 },
        }),
      });
      return;
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });

  await page.goto('/producer?workflow_id=wf-001');

  await page.getByRole('button', { name: /制片检查/ }).click();
  await expect(page.getByText('下一步：生成资产定稿包')).toBeVisible();

  await page.getByRole('button', { name: /执行下一步/ }).click();

  await expect.poll(() => assistantRequests.length).toBe(2);
  expect(assistantRequests[0]).toEqual({ auto_fix: false });
  expect(assistantRequests[1]).toEqual({ auto_fix: true, action_code: 'build_production_pack' });
});

test('producer reuses an existing novel chapter workflow instead of creating a duplicate', async ({ page }) => {
  let startWorkflowCalls = 0;

  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
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
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }

    if (path === '/api/v1/workflow' && route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{
          workflow_id: 'wf-existing',
          title: '逆天至尊 第一章 已有工程',
          status: 'active',
          current_step: 4,
          novel_id: 'novel-001',
          chapter_id: 'chapter-001',
          script_id: 'script-001',
          storyboard_id: 'storyboard-001',
          video_job_ids: [],
          tts_job_ids: [],
          synthesis_job_ids: [],
        }]),
      });
      return;
    }

    if (path === '/api/v1/workflow/start') {
      startWorkflowCalls += 1;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ workflow_id: 'wf-duplicate' }),
      });
      return;
    }

    if (path === '/api/v1/workflow/status/wf-existing') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          workflow_id: 'wf-existing',
          title: '逆天至尊 第一章 已有工程',
          status: 'active',
          current_step: 4,
          completed_steps: [1, 2, 3, 4],
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

    if (path === '/api/v1/short-video/workflow/wf-existing/readiness') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          summary: { ready: false, score: 68, blocker_count: 0, warning_count: 1 },
          recommendations: ['复用已有工程继续补齐。'],
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
        body: JSON.stringify({ script_id: 'script-001', storyboard_id: 'storyboard-001', shot_count: 2 }),
      });
      return;
    }

    if (path === '/api/v1/story-bibles') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });

  await page.goto('/producer');
  await page.getByRole('combobox').first().selectOption('novel-001');
  await page.getByRole('combobox').nth(1).selectOption('chapter-001');
  await expect(page.getByRole('combobox').nth(2)).toHaveValue('wf-existing');

  await page.getByRole('button', { name: /创建\/复用本集工程/ }).click();

  await page.waitForTimeout(500);
  expect(startWorkflowCalls).toBe(0);
  await expect(page.getByRole('combobox').nth(2)).toHaveValue('wf-existing');
});
