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
  await page.route('**/api/v1/workflow', (route) => route.fulfill({
    json: [{ workflow_id: 'workflow-series-e2e', title: '整书计划入口测试 第一集', status: 'active' }],
  }));
  await page.route('**/api/v1/studio/workflows/workflow-series-e2e/snapshot**', (route) => route.fulfill({
    json: {
      series_studio: { enabled: true, primary_console: 'series_studio', expert_drilldowns: [] },
      workflow: {
        id: 'workflow-series-e2e',
        title: '整书计划入口测试 第一集',
        status: 'active',
        novel_id: 'novel-series-e2e',
        chapter_id: 'chapter-series-e2e',
        script_id: 'script-series-e2e',
        storyboard_id: 'storyboard-series-e2e',
      },
      story_context: {
        novel: { id: 'novel-series-e2e', title: '整书计划入口测试', genre: 'fantasy' },
        chapter: { id: 'chapter-series-e2e', title: '第一章', chapter_number: 1 },
      },
      production_bible_summary: {
        readiness_score: 82,
        style: { visual_style: '动画电影' },
        counts: { characters: 1, scenes: 1, props: 1, events: 1, voices: 0 },
        characters: [{ entity_id: 'char-series-e2e', name: '林澈', approved: true }],
        scenes: [],
        props: [],
        events: [],
        voices: [],
        missing_requirements: [],
        asset_readiness: { asset_count: 1, missing_asset_count: 0, ready: true },
      },
      series_plan: { novel_id: 'novel-series-e2e', current_episode: { episode_index: 1, title: '第一集' }, episodes: [] },
      episode_contract: null,
      consistency_ledger: { overall_score: 100, dimensions: {}, findings: [] },
      production: { shot_count: 3, asset_lock_coverage: 1, entity_ref_coverage: 1, ready: true },
      shots: [],
      assets: { total_count: 1, locked_count: 1, final_count: 1, by_category: { character: 1 } },
      jobs: { summary: { video_count: 0, tts_count: 0, synthesis_count: 0, media_count: 0 } },
      issues: [],
      actions: [],
      mode_policy: { mode: 'production', ready: true, blocking_issue_count: 0 },
    },
  }));
  await page.route('**/api/v1/production-cards/novel/novel-series-e2e', (route) => route.fulfill({
    json: { novel_id: 'novel-series-e2e', cards: [], summary: { ready: 0, incomplete: 0 } },
  }));
  await page.route('**/api/v1/prompt-skills', (route) => route.fulfill({ json: { items: [], count: 0 } }));

  await page.goto('/quick-start');
  await expect(page.getByPlaceholder('例如：星灯邮差')).toHaveValue('整书计划入口测试', { timeout: 10_000 });
  await expect(page.getByText('检查')).toBeVisible();
  await page.getByRole('button', { name: /生成第一集|开始生成/ }).click();
  await expect(page.getByText(/生成完成|已生成/).first()).toBeVisible({ timeout: 120_000 });
  await page.getByRole('link', { name: /进入工作室|打开工作室/ }).first().click();
  await expect(page).toHaveURL(/\/studio\?.*workflow_id=workflow-series-e2e/);
  await expect(page).toHaveURL(/source=quick_start/);
  await expect(page.getByRole('heading', { name: '系列动漫工作室' })).toBeVisible();
  await expect(page.getByText('Failed to fetch')).toHaveCount(0);

  const seriesPlanLink = page.getByRole('link', { name: '进入整书计划' });
  await page.goto('/quick-start');
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
  await expect(page.getByPlaceholder('例如：星灯邮差')).toHaveValue('自动草片统一管线', { timeout: 10_000 });
  await page.getByRole('button', { name: /高级设置/ }).click();
  await expect(page.getByText('效果模式', { exact: true })).toBeVisible();
  await expect(page.getByText('角色配音配置（高级）')).toBeVisible();
  await page.getByRole('button', { name: /生成第一集|开始生成/ }).click();

  await expect(page.getByText('首集预览草片、字幕和渲染包已生成')).toBeVisible({ timeout: 10_000 });
  expect(mediaRequests).toHaveLength(1);
  expect(mediaRequests[0]).toMatchObject({
    production_strategy: 'draft_fast',
    strategy: 'separate_video_tts',
    model_config_id: 'video-model-e2e',
    audio_model_config_id: 'audio-model-e2e',
  });
  expect(preflightRequests.length).toBe(1);
  await expect(page.getByRole('link', { name: '播放预览包' })).toBeVisible();
});

test('quick start progress cards expose recovery guidance and actions for failed stages', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('ai-video-platform:quick-start-last-run', JSON.stringify({
      savedAt: new Date().toISOString(),
      progressSteps: [
        { id: 'novel', label: '创建作品', status: 'done', detail: '作品已保存', updatedAt: new Date().toISOString() },
        { id: 'chapter', label: '创建首章', status: 'done', detail: '首章已保存', updatedAt: new Date().toISOString() },
        { id: 'storyboard', label: '智能生成剧本与分镜', status: 'done', detail: '已生成 2 个镜头', updatedAt: new Date().toISOString() },
        { id: 'workflow', label: '创建首集工作流', status: 'done', detail: '工作流已创建', updatedAt: new Date().toISOString() },
        { id: 'media', label: '批量生成音视频草稿', status: 'failed', detail: 'MiniMax voice id not exist', updatedAt: new Date().toISOString() },
        { id: 'render', label: '生成本地预览包与字幕', status: 'stopped', detail: '已停止等待；可稍后继续处理。', updatedAt: new Date().toISOString() },
      ],
      result: {
        novelId: 'novel-recovery-e2e',
        chapterId: 'chapter-recovery-e2e',
        scriptId: 'script-recovery-e2e',
        storyboardId: 'storyboard-recovery-e2e',
        workflowId: 'workflow-recovery-e2e',
        shotCount: 2,
      },
      issue: {
        stepId: 'media',
        stepLabel: '批量生成音视频草稿',
        summary: '配音音色不可用，已暂停在音视频草稿阶段',
        rawMessage: '[2054] voice id not exist',
        cause: '当前角色声线或默认 TTS 音色在 MiniMax 账号下不存在。',
        advice: [
          '去模型与密钥中检查当前 TTS 配置。',
          '去 TTS 工作台试听同一个音色。',
          '先跳过配音继续生成无声视频和字幕。',
        ],
        canSkipAudio: true,
        canRetryProduction: true,
      },
    }));
  });
  await page.route('**/api/v1/llm/configs', (route) => route.fulfill({ json: [] }));

  await page.goto('/quick-start');

  const failedStep = page.getByTestId('quick-start-progress-step-media');
  await expect(failedStep.getByText('批量生成音视频草稿')).toBeVisible();
  await expect(failedStep.getByText('快速修复')).toBeVisible();
  await expect(failedStep.getByText('配音音色不可用，已暂停在音视频草稿阶段')).toBeVisible();
  await expect(failedStep.getByText('去 TTS 工作台试听同一个音色。')).toBeVisible();
  await expect(failedStep.getByRole('button', { name: '重试生产阶段' })).toBeVisible();
  await expect(failedStep.getByRole('button', { name: '跳过配音继续' })).toBeVisible();
  await expect(failedStep.getByRole('link', { name: '去模型与密钥' })).toHaveAttribute('href', '/llm-config');
  await expect(failedStep.getByRole('link', { name: '进入工作室' })).toHaveAttribute('href', /workflow_id=workflow-recovery-e2e/);
  await expect(failedStep.getByRole('link', { name: '任务中心' })).toHaveAttribute('href', '/jobs');

  const stoppedStep = page.getByTestId('quick-start-progress-step-render');
  await expect(stoppedStep.getByText('生成本地预览包与字幕')).toBeVisible();
  await expect(stoppedStep.getByText('当前等待已停止，已创建内容会保留')).toBeVisible();
  await expect(stoppedStep.getByRole('button', { name: '重试生产阶段' })).toBeVisible();
  await expect(stoppedStep.getByRole('link', { name: '进入工作室' })).toHaveAttribute('href', /workflow_id=workflow-recovery-e2e/);
  await expect(stoppedStep.getByRole('link', { name: '任务中心' })).toHaveAttribute('href', '/jobs');
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
          workflow_id: 'workflow-existing-e2e',
          chapters: [{ id: 'chapter-series-e2e', chapter_number: 1, title: '第一章' }],
          narrative: { hook: '密信亮起星光。' },
          production_readiness: {
            has_workflow: true,
            has_storyboard: true,
            asset_ready: false,
            missing_asset_count: 2,
            voice_count: 0,
          },
          missing_requirements: [
            { message: '声线锁定' },
            { message: '质量门禁', count: 1 },
          ],
          continuity_summary: {
            style: '旧城雨夜视觉',
            characters: ['阿月'],
            scenes: ['旧城雨夜'],
            props: ['密信'],
            events: ['密信亮起星光'],
            voice_count: 0,
          },
        },
      ],
    },
  }));

  await page.goto('/novels/novel-series-e2e?tab=series-plan');
  await expect(page.getByRole('tab', { name: /整书计划/ })).toHaveAttribute('data-state', 'active', { timeout: 10_000 });
  await expect(page.getByText('连续动漫制作线')).toBeVisible();
  await expect(page.getByText('第一集 星光密信')).toBeVisible();
  await expect(page.getByText('待锁定 2 个资产')).toBeVisible();
  await expect(page.getByText('声线锁定、质量门禁（1）')).toBeVisible();
  await expect(page.getByText(/风格：旧城雨夜视觉/)).toBeVisible();
  await expect(page.getByText(/角色：阿月/)).toBeVisible();
  await page.getByRole('button', { name: '继续本集工程' }).click();
  await expect(page).toHaveURL(/\/studio\?workflow_id=workflow-existing-e2e/);
});
