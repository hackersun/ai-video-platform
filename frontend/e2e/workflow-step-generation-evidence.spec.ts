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

test('workflow marks local artifact render package as review-only and keeps artifact links', async ({ page }) => {
  const renderRequests: Array<Record<string, unknown>> = [];
  await mockCommonWorkflowRoutes(page, {
    currentStep: 9,
    scriptId: 'script-001',
    storyboardId: 'storyboard-001',
    videoJobs: [{ id: 'video-job-001', script_id: 'script-001', novel_id: 'novel-001', chapter_id: 'chapter-001', storyboard_id: 'storyboard-001' }],
    ttsJobs: [{ id: 'tts-job-001', script_id: 'script-001', chapter_id: 'chapter-001', storyboard_id: 'storyboard-001' }],
    synthesisJobs: [{
      id: 'synthesis-001',
      job_id: 'synthesis-001',
      title: '第一章连续成片清单',
      status: 'succeeded',
      manifest_url: '/static/exports/synthesis-001.json',
      output_url: '/static/exports/synthesis-001-preview.html',
      segment_count: 2,
      duration_seconds: 8,
      extra_data: {
        render_backend: 'local_artifact_package',
        output_kind: 'preview_package',
        is_publishable: false,
        publish_block_reason: '当前只有本地预览包',
        render_artifacts: {
          preview_url: '/static/exports/synthesis-001-preview.html',
          srt_url: '/static/exports/synthesis-001.srt',
          timeline_url: '/static/exports/synthesis-001-timeline.json',
          render_manifest_url: '/static/exports/synthesis-001-render.json',
        },
      },
    }],
    extraRoute: async (route, path, request) => {
      if (path === '/api/v1/workflow/wf-269/render') {
        const body = request.postData() ? JSON.parse(request.postData() || '{}') : {};
        renderRequests.push(body);
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            job_id: 'synthesis-001',
            status: 'succeeded',
            render_backend: 'local_artifact_package',
            output_kind: 'preview_package',
            is_publishable: false,
            publish_block_reason: '当前只有本地预览包',
            output_url: '/static/exports/synthesis-001-preview.html',
            preview_url: '/static/exports/synthesis-001-preview.html',
            srt_url: '/static/exports/synthesis-001.srt',
            timeline_url: '/static/exports/synthesis-001-timeline.json',
            render_manifest_url: '/static/exports/synthesis-001-render.json',
          }),
        });
        return true;
      }
      return false;
    },
  });

  await page.goto('/workflow?workflow_id=wf-269');
  await page.getByRole('button', { name: /生成审阅包|重新生成审阅包/ }).click();

  await expect.poll(() => renderRequests.length).toBe(1);
  expect(renderRequests[0]).toMatchObject({ render_backend: 'local_artifact_package' });

  const reviewOnlyNotice = page.getByText('审阅包 · 不可直接发布');
  await expect(reviewOnlyNotice).toBeVisible();
  await expect(reviewOnlyNotice.locator('..')).toContainText('当前只有本地预览包');
  await expect(page.getByRole('link', { name: 'HTML 预览' })).toHaveAttribute('href', /synthesis-001-preview\.html$/);
  await expect(page.getByRole('link', { name: 'SRT 字幕' })).toHaveAttribute('href', /synthesis-001\.srt$/);
  await expect(page.getByRole('link', { name: '时间线 EDL' })).toHaveAttribute('href', /synthesis-001-timeline\.json$/);
  await expect(page.getByRole('link', { name: '渲染清单' })).toHaveAttribute('href', /synthesis-001-render\.json$/);
});

test('workflow can run local FFmpeg render and exposes real mp4 artifacts', async ({ page }) => {
  const renderRequests: Array<Record<string, unknown>> = [];
  await mockCommonWorkflowRoutes(page, {
    currentStep: 9,
    scriptId: 'script-001',
    storyboardId: 'storyboard-001',
    videoJobs: [{ id: 'video-job-001', script_id: 'script-001', novel_id: 'novel-001', chapter_id: 'chapter-001', storyboard_id: 'storyboard-001' }],
    ttsJobs: [{ id: 'tts-job-001', script_id: 'script-001', chapter_id: 'chapter-001', storyboard_id: 'storyboard-001' }],
    synthesisJobs: [{
      id: 'synthesis-001',
      job_id: 'synthesis-001',
      title: '第一章连续成片清单',
      status: 'succeeded',
      manifest_url: '/static/exports/synthesis-001.json',
      output_url: '/static/exports/synthesis-001-preview.html',
      segment_count: 2,
      duration_seconds: 8,
    }],
    extraRoute: async (route, path, request) => {
      if (path === '/api/v1/workflow/wf-269/render') {
        const body = request.postData() ? JSON.parse(request.postData() || '{}') : {};
        renderRequests.push(body);
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            job_id: 'synthesis-001',
            status: 'succeeded',
            render_status: 'completed',
            render_backend: 'ffmpeg_local',
            output_kind: 'final_video',
            is_publishable: true,
            output_url: '/static/exports/synthesis-001-final.mp4',
            srt_url: '/static/exports/synthesis-001.srt',
            render_manifest_url: '/static/exports/synthesis-001-render.json',
          }),
        });
        return true;
      }
      return false;
    },
  });

  await page.goto('/workflow?workflow_id=wf-269');
  await page.locator('select[title="渲染执行器"]').selectOption('ffmpeg_local');
  await page.getByRole('button', { name: '生成真实成片' }).click();

  await expect.poll(() => renderRequests.length).toBe(1);
  expect(renderRequests[0]).toMatchObject({ render_backend: 'ffmpeg_local' });

  await expect(page.getByText('本地 FFmpeg 真实成片已生成')).toBeVisible();
  await expect(page.getByRole('link', { name: '打开真实 MP4' })).toHaveAttribute('href', /synthesis-001-final\.mp4$/);
  await expect(page.getByRole('link', { name: '打开真实 MP4' })).toHaveAttribute('target', '_blank');
  await expect(page.getByRole('link', { name: '下载 MP4' })).toHaveAttribute('download', '');
  await expect(page.getByRole('link', { name: '下载 MP4' })).toHaveAttribute('href', /synthesis-001-final\.mp4$/);
  await expect(page.getByRole('link', { name: '下载 SRT' })).toHaveAttribute('download', '');
  await expect(page.getByRole('link', { name: '下载 SRT' })).toHaveAttribute('href', /synthesis-001\.srt$/);
});

test('workflow shows install guidance when local FFmpeg is missing', async ({ page }) => {
  await mockCommonWorkflowRoutes(page, {
    currentStep: 9,
    scriptId: 'script-001',
    storyboardId: 'storyboard-001',
    videoJobs: [{ id: 'video-job-001', script_id: 'script-001', novel_id: 'novel-001', chapter_id: 'chapter-001', storyboard_id: 'storyboard-001' }],
    ttsJobs: [{ id: 'tts-job-001', script_id: 'script-001', chapter_id: 'chapter-001', storyboard_id: 'storyboard-001' }],
    synthesisJobs: [{
      id: 'synthesis-001',
      job_id: 'synthesis-001',
      title: '第一章连续成片清单',
      status: 'succeeded',
      manifest_url: '/static/exports/synthesis-001.json',
      output_url: '/static/exports/synthesis-001-preview.html',
      segment_count: 2,
      duration_seconds: 8,
    }],
    extraRoute: async (route, path) => {
      if (path === '/api/v1/workflow/wf-269/render') {
        await route.fulfill({
          status: 422,
          contentType: 'application/json',
          body: JSON.stringify({
            detail: {
              code: 'ffmpeg_not_installed',
              message: 'FFmpeg 未安装',
            },
          }),
        });
        return true;
      }
      return false;
    },
  });

  await page.goto('/workflow?workflow_id=wf-269');
  await page.locator('select[title="渲染执行器"]').selectOption('ffmpeg_local');
  await page.getByRole('button', { name: '生成真实成片' }).click();

  await expect(page.getByText('未检测到本地 FFmpeg')).toBeVisible();
  await expect(page.getByText('brew install ffmpeg')).toBeVisible();
});

test('workflow hydrates persisted local FFmpeg output instead of stale review preview', async ({ page }) => {
  await mockCommonWorkflowRoutes(page, {
    currentStep: 9,
    scriptId: 'script-001',
    storyboardId: 'storyboard-001',
    videoJobs: [{ id: 'video-job-001', script_id: 'script-001', novel_id: 'novel-001', chapter_id: 'chapter-001', storyboard_id: 'storyboard-001' }],
    ttsJobs: [{ id: 'tts-job-001', script_id: 'script-001', chapter_id: 'chapter-001', storyboard_id: 'storyboard-001' }],
    synthesisJobs: [{
      id: 'synthesis-001',
      job_id: 'synthesis-001',
      title: '第一章连续成片清单',
      status: 'succeeded',
      manifest_url: '/static/exports/synthesis-001.json',
      output_url: '/static/exports/synthesis-001-final.mp4',
      segment_count: 2,
      duration_seconds: 8,
      extra_data: {
        render_status: 'rendered',
        render_backend: 'ffmpeg_local',
        output_kind: 'final_video',
        is_publishable: true,
        render_artifacts: {
          output_url: '/static/exports/synthesis-001-final.mp4',
          preview_url: '/static/exports/synthesis-001-preview.html',
          srt_url: '/static/exports/synthesis-001.srt',
          timeline_url: '/static/exports/synthesis-001-timeline.json',
          render_manifest_url: '/static/exports/synthesis-001-render.json',
        },
      },
    }],
  });

  await page.goto('/workflow?workflow_id=wf-269');

  await expect(page.getByText('本地 FFmpeg 真实成片已生成')).toBeVisible();
  await expect(page.getByRole('link', { name: '打开真实 MP4' })).toHaveAttribute('href', /synthesis-001-final\.mp4$/);

  await page.getByRole('button', { name: '下一步' }).click();
  await expect(page.getByRole('button', { name: '真实 MP4' })).toBeVisible();
  await expect(page.getByRole('button', { name: '真实 MP4' })).not.toHaveText(/HTML 预览/);
});
