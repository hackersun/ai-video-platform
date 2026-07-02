import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `producer-preview-production-user-${Date.now()}`;
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

test('producer preview production uses audio model, contract refresh, render preflight and review links', async ({ page }) => {
  const mediaRequests: Array<Record<string, unknown>> = [];
  const calls: string[] = [];

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path === '/api/v1/novels') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 'novel-preview', title: '裂纹月光', genre: '都市异能', description: '雨夜天桥上的异能事件。' }]),
      });
      return;
    }

    if (path === '/api/v1/llm/configs') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'text-model-preview',
            model_id: 'text-dev',
            model_type: 'chat',
            model_capabilities: ['text-generation'],
            provider_id: 'dev',
            provider_name: 'DEV',
            model_name: 'text-dev',
            name: '默认文本模型',
            is_default: true,
            test_status: 'success',
            key_available: true,
          },
          {
            id: 'video-model-preview',
            model_id: 'video-dev',
            model_type: 'video',
            model_capabilities: ['text-to-video'],
            provider_id: 'dev',
            provider_name: 'DEV',
            model_name: 'video-dev',
            name: '默认视频模型',
            is_default: true,
            test_status: 'success',
            key_available: true,
          },
          {
            id: 'audio-model-preview',
            model_id: 'audio-dev',
            model_type: 'audio',
            model_capabilities: ['audio'],
            provider_id: 'dev',
            provider_name: 'DEV',
            model_name: 'audio-dev',
            name: '默认声音模型',
            is_default: true,
            test_status: 'success',
            key_available: true,
          },
        ]),
      });
      return;
    }

    if (path === '/api/v1/workflow' && request.method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{
          workflow_id: 'wf-preview',
          title: '裂纹月光 第一集',
          status: 'active',
          current_step: 6,
          novel_id: 'novel-preview',
          chapter_id: 'chapter-preview',
          script_id: 'script-preview',
          storyboard_id: 'storyboard-preview',
          video_job_ids: [],
          tts_job_ids: [],
          synthesis_job_ids: [],
        }]),
      });
      return;
    }

    if (path === '/api/v1/workflow/status/wf-preview') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          workflow_id: 'wf-preview',
          title: '裂纹月光 第一集',
          status: 'active',
          current_step: 6,
          completed_steps: [1, 2, 3, 4, 5, 6],
          novel_id: 'novel-preview',
          chapter_id: 'chapter-preview',
          script_id: 'script-preview',
          storyboard_id: 'storyboard-preview',
          video_jobs: [],
          tts_jobs: [],
          synthesis_jobs: [],
        }),
      });
      return;
    }

    if (path === '/api/v1/chapters/novel/novel-preview') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 'chapter-preview', title: '第一章 裂纹月光', chapter_number: 1, content: '沈砚在雨夜天桥发现吊坠裂纹。' }]),
      });
      return;
    }

    if (path === '/api/v1/chapters/chapter-preview/production-status') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ script_id: 'script-preview', storyboard_id: 'storyboard-preview', shot_count: 2, has_script: true, has_storyboard: true }),
      });
      return;
    }

    if (path === '/api/v1/short-video/workflow/wf-preview/readiness') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          summary: { ready: true, score: 88, blocker_count: 0, warning_count: 0, shot_count: 2 },
          recommendations: ['可以生成本集草片。'],
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

    if (path === '/api/v1/workflow/wf-preview/step') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
      return;
    }

    if (path === '/api/v1/production-control/workflow/wf-preview/producer-assistant') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ workflow_id: 'wf-preview', summary: { executed_count: 1 }, executed: [{ code: 'apply_asset_locks' }] }),
      });
      return;
    }

    if (path === '/api/v1/production-control/workflow/wf-preview/asset-locks') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ workflow_id: 'wf-preview', applied_shots: [{ shot_id: 'shot-1' }, { shot_id: 'shot-2' }] }),
      });
      return;
    }

    if (path === '/api/v1/short-video/workflow/wf-preview/refresh-contracts') {
      calls.push('refresh-contracts');
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ workflow_id: 'wf-preview', refreshed_count: 2 }),
      });
      return;
    }

    if (path === '/api/v1/workflow/wf-preview/generate-media-batch') {
      mediaRequests.push(request.postDataJSON());
      calls.push('media');
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ready_for_concatenate: true,
          video_job_ids: ['video-1', 'video-2'],
          tts_job_ids: ['tts-1', 'tts-2'],
          media_job_ids: [],
          subtitle_track_ids: ['subtitle-1', 'subtitle-2'],
        }),
      });
      return;
    }

    if (path === '/api/v1/workflow/concatenate/wf-preview') {
      calls.push('concatenate');
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          job_id: 'synthesis-preview',
          output_url: '/static/dev/synthesis-preview.mp4',
          manifest_url: '/static/exports/synthesis-preview.json',
          segment_count: 2,
        }),
      });
      return;
    }

    if (path === '/api/v1/workflow/wf-preview/render/preflight') {
      calls.push('preflight');
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ready: true, issues: [], timeline_id: 'timeline-preview' }) });
      return;
    }

    if (path === '/api/v1/workflow/wf-preview/render') {
      calls.push('render');
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'succeeded',
          message: '本集草片渲染包已生成',
          preview_url: '/static/exports/preview.html',
          srt_url: '/static/exports/preview.srt',
          timeline_url: '/static/exports/preview-timeline.json',
          render_manifest_url: '/static/exports/preview-render.json',
        }),
      });
      return;
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });

  await page.goto('/producer?workflow_id=wf-preview');
  await expect(page.getByText('本集草片声音模型')).toBeVisible({ timeout: 10_000 });
  await page.getByRole('button', { name: '一键生成本集草片' }).click();

  await expect(page.getByRole('link', { name: /打开草片预览/ })).toBeVisible({ timeout: 10_000 });
  await expect(page.getByRole('link', { name: '查看字幕' })).toBeVisible();
  await expect.poll(() => mediaRequests.length).toBe(1);
  expect(mediaRequests[0]).toMatchObject({
    strategy: 'separate_video_tts',
    model_config_id: 'video-model-preview',
    audio_model_config_id: 'audio-model-preview',
  });
  expect(calls).toEqual(['refresh-contracts', 'media', 'concatenate', 'preflight', 'render']);
});
