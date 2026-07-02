import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `workflow-guidance-user-${Date.now()}`;
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

test('workflow page does not silently create a workflow without workflow_id', async ({ page }) => {
  let startWorkflowCalls = 0;
  await page.route('**/api/v1/workflow/start', async (route) => {
    startWorkflowCalls += 1;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ workflow_id: 'unexpected-auto-workflow' }),
    });
  });

  await page.goto('/workflow');
  await expect(page.getByText('选择或创建本集工程')).toBeVisible({ timeout: 10_000 });
  await page.waitForTimeout(1000);

  expect(startWorkflowCalls).toBe(0);
});

test('workflow next action posts the selected assistant action code', async ({ page }) => {
  const assistantRequests: Array<Record<string, unknown>> = [];

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path === '/api/v1/llm/configs') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
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
          metadata: { production_pack: { lock_count: 0 } },
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

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: request.method() === 'GET' ? '[]' : '{}',
    });
  });

  await page.goto('/workflow?workflow_id=wf-001');
  await expect(page.getByText('下一步：生成资产定稿包')).toBeVisible();

  await page.getByRole('button', { name: /执行下一步/ }).click();

  await expect.poll(() => assistantRequests.some((body) => (
    body.auto_fix === true && body.action_code === 'build_production_pack'
  ))).toBeTruthy();
  expect(assistantRequests[0]).toEqual({ auto_fix: false });
});
