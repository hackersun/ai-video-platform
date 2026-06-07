import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `workflow-step-evidence-user-${Date.now()}`;
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

async function mockCommonWorkflowRoutes(page: any, overrides: {
  currentStep?: number;
  scriptId?: string;
  storyboardId?: string;
  videoJobs?: any[];
  ttsJobs?: any[];
  mediaJobs?: any[];
  synthesisJobs?: any[];
  extraRoute?: (route: any, path: string, request: any) => Promise<boolean>;
} = {}) {
  await page.route('**/api/v1/**', async (route: any) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (await overrides.extraRoute?.(route, path, request)) {
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

    if (path === '/api/v1/workflow/status/wf-269') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          workflow_id: 'wf-269',
          title: '逆天至尊 第一章',
          status: 'active',
          current_step: overrides.currentStep || 4,
          completed_steps: [1, 2, 3],
          novel_id: 'novel-001',
          chapter_id: 'chapter-001',
          script_id: overrides.scriptId || null,
          storyboard_id: overrides.storyboardId || null,
          video_jobs: overrides.videoJobs || [],
          tts_jobs: overrides.ttsJobs || [],
          media_jobs: overrides.mediaJobs || [],
          subtitle_tracks: [],
          synthesis_jobs: overrides.synthesisJobs || [],
          metadata: {},
        }),
      });
      return;
    }

    if (path === '/api/v1/workflow/wf-269/step') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
      return;
    }

    if (path === '/api/v1/production-control/workflow/wf-269/producer-assistant') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ summary: { action_count: 0 }, actions: [], executed: [] }),
      });
      return;
    }

    if (path === '/api/v1/short-video/workflow/wf-269/readiness') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ summary: { ready: false }, recommendations: [] }),
      });
      return;
    }

    if (path === '/api/v1/story-bibles') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }

    if (path === '/api/v1/external-configs') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }

    if (path === '/api/v1/scripts' && request.method() === 'GET') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }

    if (path === '/api/v1/storyboards/script/script-001') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
      return;
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });
}

test('workflow shows persistent script generation evidence with model status and produced script id', async ({ page }) => {
  const scriptRequests: Array<Record<string, unknown>> = [];
  await mockCommonWorkflowRoutes(page, {
    currentStep: 4,
    extraRoute: async (route, path, request) => {
      if (path === '/api/v1/scripts/generate') {
        const body = request.postData() ? JSON.parse(request.postData() || '{}') : {};
        scriptRequests.push(body);
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 'script-001',
            title: '第一章 少年出山 动漫剧本',
            content: '镜头一：少年踏入风雪。',
          }),
        });
        return true;
      }
      return false;
    },
  });

  await page.goto('/workflow?workflow_id=wf-269');
  await page.getByRole('button', { name: 'AI 生成剧本' }).click();

  await expect.poll(() => scriptRequests.length).toBe(1);
  expect(scriptRequests[0]).toMatchObject({ chapter_id: 'chapter-001', model_config_id: 'text-config-001' });

  const evidence = page.getByTestId('workflow-step-evidence-script');
  await expect(evidence).toBeVisible();
  await expect(evidence).toContainText('剧本生成证据');
  await expect(evidence).toContainText('默认文本模型');
  await expect(evidence).toContainText('已验证');
  await expect(evidence).toContainText('script-001');
  await expect(evidence).toContainText('第一章 少年出山 动漫剧本');
});

test('workflow keeps storyboard failure evidence with selected model and backend reason', async ({ page }) => {
  await mockCommonWorkflowRoutes(page, {
    currentStep: 5,
    scriptId: 'script-001',
    extraRoute: async (route, path) => {
      if (path === '/api/v1/storyboards/generate-smart') {
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: '分镜提示词缺少章节事件上下文' }),
        });
        return true;
      }
      return false;
    },
  });

  await page.goto('/workflow?workflow_id=wf-269');
  await page.getByRole('button', { name: 'AI 生成分镜' }).click();

  const evidence = page.getByTestId('workflow-step-evidence-storyboard');
  await expect(evidence).toBeVisible();
  await expect(evidence).toContainText('分镜生成证据');
  await expect(evidence).toContainText('默认文本模型');
  await expect(evidence).toContainText('已验证');
  await expect(evidence).toContainText('生成失败');
  await expect(evidence).toContainText('分镜提示词缺少章节事件上下文');
});

test('workflow shows continuous video evidence after synthesis manifest generation', async ({ page }) => {
  const concatenateRequests: Array<Record<string, unknown>> = [];
  await mockCommonWorkflowRoutes(page, {
    currentStep: 9,
    scriptId: 'script-001',
    storyboardId: 'storyboard-001',
    videoJobs: [{ id: 'video-job-001', script_id: 'script-001', novel_id: 'novel-001', chapter_id: 'chapter-001', storyboard_id: 'storyboard-001' }],
    ttsJobs: [{ id: 'tts-job-001', script_id: 'script-001', chapter_id: 'chapter-001', storyboard_id: 'storyboard-001' }],
    extraRoute: async (route, path, request) => {
      if (path === '/api/v1/workflow/concatenate/wf-269') {
        const body = request.postData() ? JSON.parse(request.postData() || '{}') : {};
        concatenateRequests.push(body);
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            job_id: 'synthesis-001',
            manifest_url: '/static/exports/synthesis-001.json',
            output_url: '/static/exports/synthesis-001.mp4',
            segment_count: 2,
            duration_seconds: 8,
          }),
        });
        return true;
      }
      return false;
    },
  });

  await page.goto('/workflow?workflow_id=wf-269');
  await page.getByRole('button', { name: '生成连续成片' }).click();

  await expect.poll(() => concatenateRequests.length).toBe(1);
  expect(concatenateRequests[0]).toMatchObject({
    video_job_ids: ['video-job-001'],
    tts_job_ids: ['tts-job-001'],
    include_subtitles: true,
  });

  const evidence = page.getByTestId('workflow-synthesis-evidence');
  await expect(evidence).toBeVisible();
  await expect(evidence).toContainText('连续成片证据');
  await expect(evidence).toContainText('synthesis-001');
  await expect(evidence).toContainText('片段 2');
  await expect(evidence).toContainText('8 秒');
});
