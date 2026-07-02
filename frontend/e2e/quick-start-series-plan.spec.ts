import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `quick-start-series-${Date.now()}`;
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

test('quick start result links users into the whole-book production plan', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('ai-video-platform:quick-start-draft', JSON.stringify({
      savedAt: new Date().toISOString(),
      form: {
        title: '整书计划入口测试',
        premise: '少年在旧城中追查星光密信，并逐步揭开隐藏世界。',
        genre: 'fantasy',
        style: 'anime',
        chapterTitle: '第一章',
        chapterContent: '林澈在雨夜旧城捡起会发光的密信，远处钟声回应他的心跳。',
        shotCount: 3,
        createStoryBible: true,
        autoProducePreview: false,
      },
    }));
  });
  await page.route('**/api/v1/llm/configs', (route) => route.fulfill({ json: [] }));
  await page.route('**/api/v1/novels', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        json: {
          id: 'novel-series-e2e',
          title: '整书计划入口测试',
          description: '少年在旧城中追查星光密信。',
          genre: 'fantasy',
          style: 'anime',
          status: 'writing',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      });
      return;
    }
    await route.continue();
  });
  await page.route('**/api/v1/chapters', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        json: {
          id: 'chapter-series-e2e',
          novel_id: 'novel-series-e2e',
          title: '第一章',
          chapter_number: 1,
          content: '林澈在雨夜旧城捡起会发光的密信。',
          status: 'draft',
          created_at: new Date().toISOString(),
        },
      });
      return;
    }
    await route.continue();
  });
  await page.route('**/api/v1/story-bibles/generate-from-novel', (route) => route.fulfill({ json: { id: 'story-bible-series-e2e' } }));
  await page.route('**/api/v1/storyboards/generate-smart', (route) => route.fulfill({
    json: {
      id: 'storyboard-series-e2e',
      script_id: 'script-series-e2e',
      shot_count: 3,
      shots: [{ id: 'shot-1' }, { id: 'shot-2' }, { id: 'shot-3' }],
    },
  }));
  await page.route('**/api/v1/workflow/start', (route) => route.fulfill({ json: { workflow_id: 'workflow-series-e2e' } }));

  await page.goto('/quick-start');
  await expect(page.getByPlaceholder('作品名')).toHaveValue('整书计划入口测试', { timeout: 10_000 });
  await expect(page.getByText('作品名就绪')).toBeVisible();
  await page.getByRole('button', { name: '生成首集工程' }).click();

  const seriesPlanLink = page.getByRole('link', { name: '进入整书计划' });
  await expect(seriesPlanLink).toBeVisible({ timeout: 10_000 });
  await expect(seriesPlanLink).toHaveAttribute('href', '/novels/novel-series-e2e?tab=series-plan');
});

test('quick start auto preview uses canonical episode production pipeline with audio model and render preflight', async ({ page }) => {
  const mediaRequests: Array<Record<string, unknown>> = [];
  const preflightRequests: string[] = [];

  await page.addInitScript(() => {
    localStorage.setItem('ai-video-platform:quick-start-draft', JSON.stringify({
      savedAt: new Date().toISOString(),
      form: {
        title: '自动草片统一管线',
        premise: '少女在旧车站追踪蓝色电弧，发现列车时刻表正在倒流。',
        genre: 'suspense',
        style: 'anime',
        chapterTitle: '第一章',
        chapterContent: '许南在旧车站看见蓝色电弧沿着站台爬行，倒流的时刻表指向午夜。',
        shotCount: 2,
        createStoryBible: false,
        autoProducePreview: true,
      },
    }));
  });
  await page.route('**/api/v1/llm/configs', (route) => route.fulfill({
    json: [
      {
        id: 'text-model-e2e',
        name: '文本模型',
        provider_id: 'dev',
        provider_name: 'DEV',
        model_name: 'text-dev',
        capabilities: ['text'],
        test_status: 'success',
        key_available: true,
        is_default: true,
      },
      {
        id: 'video-model-e2e',
        name: '视频模型',
        provider_id: 'dev',
        provider_name: 'DEV',
        model_name: 'video-dev',
        capabilities: ['video'],
        test_status: 'success',
        key_available: true,
        is_default: true,
      },
      {
        id: 'audio-model-e2e',
        name: '声音模型',
        provider_id: 'dev',
        provider_name: 'DEV',
        model_name: 'audio-dev',
        capabilities: ['audio'],
        test_status: 'success',
        key_available: true,
        is_default: true,
      },
    ],
  }));
  await page.route('**/api/v1/novels', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        json: {
          id: 'novel-auto-e2e',
          title: '自动草片统一管线',
          description: '少女在旧车站追踪蓝色电弧。',
          genre: 'suspense',
          style: 'anime',
          status: 'writing',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      });
      return;
    }
    await route.fulfill({ json: [] });
  });
  await page.route('**/api/v1/chapters', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        json: {
          id: 'chapter-auto-e2e',
          novel_id: 'novel-auto-e2e',
          title: '第一章',
          chapter_number: 1,
          content: '许南在旧车站看见蓝色电弧。',
          status: 'draft',
          created_at: new Date().toISOString(),
        },
      });
      return;
    }
    await route.fulfill({ json: [] });
  });
  await page.route('**/api/v1/storyboards/generate-smart', (route) => route.fulfill({
    json: {
      id: 'storyboard-auto-e2e',
      script_id: 'script-auto-e2e',
      shot_count: 2,
      shots: [{ id: 'shot-auto-1' }, { id: 'shot-auto-2' }],
    },
  }));
  await page.route('**/api/v1/workflow/start', (route) => route.fulfill({ json: { workflow_id: 'workflow-auto-e2e' } }));
  await page.route('**/api/v1/workflow/status/workflow-auto-e2e', (route) => route.fulfill({
    json: {
      workflow_id: 'workflow-auto-e2e',
      novel_id: 'novel-auto-e2e',
      chapter_id: 'chapter-auto-e2e',
      script_id: 'script-auto-e2e',
      storyboard_id: 'storyboard-auto-e2e',
      video_jobs: [],
      tts_jobs: [],
      synthesis_jobs: [],
    },
  }));
  await page.route('**/api/v1/scripts?**', (route) => route.fulfill({ json: [] }));
  await page.route('**/api/v1/storyboards?**', (route) => route.fulfill({
    json: [{ id: 'storyboard-auto-e2e', script_id: 'script-auto-e2e', content: { chapter_id: 'chapter-auto-e2e' }, updated_at: new Date().toISOString() }],
  }));
  await page.route('**/api/v1/workflow/workflow-auto-e2e/step', (route) => route.fulfill({ json: { ok: true } }));
  await page.route('**/api/v1/production-control/workflow/workflow-auto-e2e/producer-assistant', (route) => route.fulfill({
    json: { workflow_id: 'workflow-auto-e2e', summary: { executed_count: 1 }, executed: [{ code: 'apply_asset_locks' }] },
  }));
  await page.route('**/api/v1/production-control/workflow/workflow-auto-e2e/asset-locks', (route) => route.fulfill({
    json: { workflow_id: 'workflow-auto-e2e', applied_shots: [{ shot_id: 'shot-auto-1' }, { shot_id: 'shot-auto-2' }] },
  }));
  await page.route('**/api/v1/short-video/workflow/workflow-auto-e2e/refresh-contracts', (route) => route.fulfill({
    json: { workflow_id: 'workflow-auto-e2e', refreshed_count: 2 },
  }));
  await page.route('**/api/v1/workflow/workflow-auto-e2e/generate-media-batch', async (route) => {
    mediaRequests.push(route.request().postDataJSON());
    await route.fulfill({
      json: {
        ready_for_concatenate: true,
        video_job_ids: ['video-auto-1', 'video-auto-2'],
        tts_job_ids: ['tts-auto-1', 'tts-auto-2'],
        media_job_ids: [],
        subtitle_track_ids: ['subtitle-auto-1', 'subtitle-auto-2'],
      },
    });
  });
  await page.route('**/api/v1/workflow/concatenate/workflow-auto-e2e', (route) => route.fulfill({
    json: {
      job_id: 'synthesis-auto-e2e',
      output_url: '/static/dev/synthesis-auto-e2e.mp4',
      manifest_url: '/static/exports/synthesis-auto-e2e.json',
      segment_count: 2,
    },
  }));
  await page.route('**/api/v1/workflow/workflow-auto-e2e/render/preflight**', async (route) => {
    preflightRequests.push(route.request().url());
    await route.fulfill({ json: { ready: true, issues: [], timeline_id: 'timeline-auto-e2e' } });
  });
  await page.route('**/api/v1/workflow/workflow-auto-e2e/render', (route) => route.fulfill({
    json: {
      status: 'succeeded',
      message: '本集草片渲染包已生成',
      preview_url: '/static/exports/auto-preview.html',
      srt_url: '/static/exports/auto.srt',
      timeline_url: '/static/exports/auto-timeline.json',
      render_manifest_url: '/static/exports/auto-render.json',
    },
  }));

  await page.goto('/quick-start');
  await expect(page.getByPlaceholder('作品名')).toHaveValue('自动草片统一管线', { timeout: 10_000 });
  await expect(page.getByText('首集草片声音模型')).toBeVisible();
  await page.getByRole('button', { name: '生成首集工程' }).click();

  await expect(page.getByText('首集预览草片、字幕和渲染包已生成')).toBeVisible({ timeout: 10_000 });
  expect(mediaRequests).toHaveLength(1);
  expect(mediaRequests[0]).toMatchObject({
    strategy: 'separate_video_tts',
    model_config_id: 'video-model-e2e',
    audio_model_config_id: 'audio-model-e2e',
  });
  expect(preflightRequests.length).toBe(1);
  await expect(page.getByRole('link', { name: '播放预览包' })).toBeVisible();
});

test('novel detail opens the whole-book plan tab from query params', async ({ page }) => {
  await page.route('**/api/v1/llm/configs', (route) => route.fulfill({ json: [] }));
  await page.route('**/api/v1/novels/novel-series-e2e', (route) => route.fulfill({
    json: {
      id: 'novel-series-e2e',
      title: '整书计划入口测试',
      description: '少年在旧城中追查星光密信。',
      genre: 'fantasy',
      status: 'writing',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
  }));
  await page.route('**/api/v1/chapters/novel/novel-series-e2e', (route) => route.fulfill({
    json: [
      {
        id: 'chapter-series-e2e',
        title: '第一章',
        chapter_number: 1,
        word_count: 1200,
        status: 'draft',
        created_at: new Date().toISOString(),
      },
    ],
  }));
  await page.route('**/api/v1/characters?novel_id=novel-series-e2e', (route) => route.fulfill({ json: [] }));
  await page.route('**/api/v1/scripts?novel_id=novel-series-e2e', (route) => route.fulfill({ json: [] }));
  await page.route('**/api/v1/story-bibles?novel_id=novel-series-e2e', (route) => route.fulfill({ json: [] }));
  await page.route('**/api/v1/novels/novel-series-e2e/series-plan', (route) => route.fulfill({
    json: {
      novel_id: 'novel-series-e2e',
      episodes: [
        {
          episode_number: 1,
          title: '第一集 星光密信',
          status: 'planned',
          chapters: [{ id: 'chapter-series-e2e', chapter_number: 1, title: '第一章' }],
          narrative: { hook: '密信亮起星光。' },
        },
      ],
    },
  }));

  await page.goto('/novels/novel-series-e2e?tab=series-plan');
  await expect(page.getByRole('tab', { name: /整书计划/ })).toHaveAttribute('data-state', 'active', { timeout: 10_000 });
  await expect(page.getByText('第一集 星光密信')).toBeVisible();
});
