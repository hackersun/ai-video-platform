import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

const smartSnapshot = {
  workflow: {
    id: 'wf-smart-console',
    title: '星港追光 第一集',
    status: 'active',
    novel_id: 'novel-smart-console',
    chapter_id: 'chapter-smart-console',
    script_id: 'script-smart-console',
    storyboard_id: 'storyboard-smart-console',
    latest_production_strategy_label: '质量优先',
    latest_recommended_model_hint: 'PixelWave v2.1',
    updated_at: '2026-07-05T00:00:00Z',
    metadata: { subtitle_track_ids: ['subtitle-1', 'subtitle-2'] },
  },
  series_studio: {
    enabled: true,
    primary_console: 'series_studio',
    expert_drilldowns: [],
  },
  story_context: {
    novel: { id: 'novel-smart-console', title: '星港追光', genre: '科幻' },
    chapter: { id: 'chapter-smart-console', title: '第一章 星港起飞', chapter_number: 1 },
    storyboard: { id: 'storyboard-smart-console', title: '星港起飞分镜', shot_count: 5 },
  },
  production_bible_summary: {
    readiness_score: 81,
    missing_requirements: [],
    counts: { characters: 1, scenes: 1, props: 1, events: 1 },
    asset_readiness: { asset_count: 3, missing_asset_count: 0, ready: true },
  },
  production: { shot_count: 5, asset_lock_coverage: 1, entity_ref_coverage: 1, ready: true },
  shots: [
    { id: 'shot-1', shot_number: 1, duration: 4, video_status: 'succeeded', audio_status: 'succeeded', quality_report: { status: 'ready', score: 100, warnings: [] } },
    { id: 'shot-2', shot_number: 2, duration: 4, video_status: 'pending', audio_status: 'pending', quality_report: { status: 'warning', score: 92, warnings: ['角色参考图缺失'] } },
    { id: 'shot-3', shot_number: 3, duration: 5, video_status: 'pending', audio_status: 'pending', quality_report: { status: 'warning', score: 95, warnings: ['场景光线待复核'] } },
    { id: 'shot-4', shot_number: 4, duration: 4, video_status: 'pending', audio_status: 'pending', quality_report: { status: 'warning', score: 96, warnings: ['字幕时间待校对'] } },
    { id: 'shot-5', shot_number: 5, duration: 5, video_status: 'pending', audio_status: 'pending', quality_report: { status: 'warning', score: 94, warnings: ['道具状态待复核'] } },
  ],
  assets: { total_count: 3, locked_count: 3, final_count: 3, by_category: { character: 1, scene: 1, prop: 1 } },
  jobs: {
    summary: { video_count: 2, tts_count: 1, synthesis_count: 0, media_count: 0 },
    video_jobs: [{ id: 'video-1', status: 'succeeded' }, { id: 'video-2', status: 'running' }],
    tts_jobs: [{ id: 'tts-1', status: 'succeeded' }],
    synthesis_jobs: [],
  },
  issues: [{ code: 'final_render_requires_confirm', message: '最终成片会使用生产资产锁。', severity: 'warning' }],
  actions: [],
  mode_policy: { mode: 'production', ready: true, blocking_issue_count: 1, warning_issue_count: 0 },
  guidance: {
    readiness_score: 81,
    blocker_count: 1,
    current_stage: 'draft',
    stages: [
      { id: 'content', label: '内容准备', status: 'ready', description: '小说与章节已选定。' },
      { id: 'bible', label: '设定锁定', status: 'ready', description: '角色、场景、道具已锁定。' },
      { id: 'episode', label: '本集工程', status: 'ready', description: '剧本与分镜已同步。' },
      { id: 'draft', label: '草片生产', status: 'working', description: '等待确认生产动作。' },
      { id: 'review', label: '复审出片', status: 'blocked', description: '确认后进入复审。' },
    ],
    next_action: {
      code: 'finalize_production_pack',
      label: '生产锁定',
      risk: 'production',
      reason: '生产前需要人工确认最终资产锁。',
      expected_outputs: ['提交最终资产锁', '刷新工作台快照'],
      scope: ['当前工作流'],
      confirmation: {
        required: true,
        title: '确认生产锁定',
        description: '该操作会提交当前工作流的最终生产资产锁。',
        confirm_label: '确认锁定',
      },
    },
    secondary_actions: [{ code: 'open_story_bible', label: '生成 Story Bible', href: '/story-bibles', risk: 'navigation' }],
  },
};

const smartNovel = {
  id: 'novel-smart-console',
  title: '星港追光',
  description: '一部围绕星港与追光者展开的科幻故事。',
  genre: '科幻',
  status: 'writing',
  word_count: 12000,
  cover_url: null,
  chapter_count: 2,
  total_chapters: 2,
  created_at: '2026-07-01T00:00:00Z',
  updated_at: '2026-07-05T00:00:00Z',
};

const smartProductionEntry = {
  novel_id: 'novel-smart-console',
  stage: 'studio_ready',
  label: '可继续生产',
  description: '最新工程已准备好，可进入 Studio 指挥台继续处理。',
  workflow_id: 'wf-smart-console',
  chapter_id: 'chapter-smart-console',
  metrics: { chapter_count: 1, episode_count: 1, workflow_count: 1 },
  primary_action: {
    code: 'open_studio',
    label: '进入 Studio 指挥台',
    href: '/studio?workflow_id=wf-smart-console&novel_id=novel-smart-console&chapter_id=chapter-smart-console',
    risk: 'safe',
  },
};

test.beforeEach(async ({ page }) => {
  const userId = `studio-smart-console-${Date.now()}`;
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

test('studio resolves a generated relative novel cover through the backend media origin', async ({ page }) => {
  let requestedCoverUrl = '';
  await page.route('**/static/generated/images/novel-cover-test.jpg', async (route) => {
    requestedCoverUrl = route.request().url();
    await route.fulfill({
      status: 200,
      contentType: 'image/png',
      body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64'),
    });
  });
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace(/\/+/g, '/').replace(/\/$/, '');
    if (path === '/api/v1/workflow') {
      await route.fulfill({ json: [{
        workflow_id: 'wf-smart-console',
        id: 'wf-smart-console',
        novel_id: 'novel-smart-console',
        chapter_id: 'chapter-smart-console',
        title: '星港追光 第一集',
        status: 'active',
      }] });
      return;
    }
    if (path === '/api/v1/studio/workflows/wf-smart-console/snapshot') {
      await route.fulfill({ json: smartSnapshot });
      return;
    }
    if (path === '/api/v1/novels/novel-smart-console') {
      await route.fulfill({ json: { ...smartNovel, cover_url: '/static/generated/images/novel-cover-test.jpg' } });
      return;
    }
    if (path === '/api/v1/chapters/novel/novel-smart-console') {
      await route.fulfill({ json: [{
        id: 'chapter-smart-console',
        title: '第一章 星港起飞',
        chapter_number: 1,
      }] });
      return;
    }
    await route.fulfill({ json: [] });
  });

  await page.goto('/studio?workflow_id=wf-smart-console');

  const cover = page.getByRole('img', { name: '星港追光 系列封面' });
  await expect(cover).toBeVisible();
  await expect.poll(() => requestedCoverUrl).toMatch(
    /^http:\/\/(?:localhost|127\.0\.0\.1):8000\/static\/generated\/images\/novel-cover-test\.jpg$/,
  );
  await expect.poll(() => cover.evaluate((image: HTMLImageElement) => image.naturalWidth)).toBeGreaterThan(0);
});

test('novels production entry opens studio command flow and confirms production actions', async ({ page }) => {
  await page.setViewportSize({ width: 1487, height: 1058 });
  let actionPayload: any = null;
  let subtitleQuery = '';
  let createdEpisodeWorkflow = false;
  let createdEpisodePayload: any = null;
  let resolveChapterRequest!: () => void;
  const chapterRequestReady = new Promise<void>((resolve) => { resolveChapterRequest = resolve; });
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/\/+/g, '/').replace(/\/$/, '');
    if (path === '/api/v1/workflow') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            workflow_id: 'wf-smart-console',
            title: '星港追光 第一集（旧兼容记录）',
            status: 'active',
            novel_id: 'novel-smart-console',
            chapter_id: null,
            current_step: 10,
          },
          {
            workflow_id: 'wf-smart-console',
            title: '星港追光 第一集',
            status: 'active',
            novel_id: 'novel-smart-console',
            chapter_id: 'chapter-smart-console',
            current_step: 10,
            completed_steps: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            video_job_ids: ['video-1', 'video-2'],
            synthesis_job_ids: ['synthesis-1'],
            metadata: { production_quality_report: { shot_count: 8 } },
            updated_at: '2026-07-05T00:00:00Z',
          },
          ...(createdEpisodeWorkflow ? [{
            workflow_id: 'wf-smart-console-2', title: '星港追光 · 第二章 追光航线', status: 'active',
            novel_id: 'novel-smart-console', chapter_id: 'chapter-smart-console-2', current_step: 1,
            completed_steps: [], video_job_ids: [], synthesis_job_ids: [],
          }] : []),
          {
            workflow_id: 'wf-other-novel',
            title: '其他小说工作流',
            status: 'active',
            novel_id: 'novel-other',
            chapter_id: 'chapter-other',
          },
        ]),
      });
      return;
    }
    if (path === '/api/v1/novels') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([smartNovel]) });
      return;
    }
    if (path === '/api/v1/novels/novel-smart-console') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(smartNovel) });
      return;
    }
    if (path === '/api/v1/chapters/novel/novel-smart-console') {
      await chapterRequestReady;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 'chapter-smart-console', title: '第一章 星港起飞', chapter_number: 1 },
          { id: 'chapter-smart-console-2', title: '第二章 追光航线', chapter_number: 2 },
        ]),
      });
      return;
    }
    if (path === '/api/v1/novels/production-entries') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ entries: { 'novel-smart-console': smartProductionEntry }, count: 1 }),
      });
      return;
    }
    if (path === '/api/v1/studio/workflows/wf-smart-console/snapshot') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(smartSnapshot) });
      return;
    }
    if (path === '/api/v1/workflow/start' && route.request().method() === 'POST') {
      createdEpisodePayload = route.request().postDataJSON();
      createdEpisodeWorkflow = true;
      await route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify({ workflow_id: 'wf-smart-console-2', title: '星港追光 · 第二章 追光航线', message: '工作流创建成功' }) });
      return;
    }
    if (path === '/api/v1/studio/workflows/wf-smart-console-2/snapshot') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
        ...smartSnapshot,
        workflow: { ...smartSnapshot.workflow, id: 'wf-smart-console-2', title: '星港追光 · 第二章 追光航线', chapter_id: 'chapter-smart-console-2', current_step: 1 },
        story_context: { ...smartSnapshot.story_context, chapter: { id: 'chapter-smart-console-2', title: '第二章 追光航线', chapter_number: 2 } },
      }) });
      return;
    }
    if (path === '/api/v1/studio/workflows/wf-smart-console/actions' && route.request().method() === 'POST') {
      actionPayload = route.request().postDataJSON();
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'action-smart-console',
          workflow_id: 'wf-smart-console',
          code: 'finalize_production_pack',
          label: '生产锁定',
          status: 'succeeded',
          risk: 'production',
        }),
      });
      return;
    }
    if (path === '/api/v1/production-cards/novel/novel-smart-console') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ novel_id: 'novel-smart-console', cards: [], summary: { ready: 0, incomplete: 0 } }),
      });
      return;
    }
    if (path === '/api/v1/prompt-skills') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [], count: 0 }) });
      return;
    }
    if (path === '/api/v1/video/models') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          models: [{
            id: 'test.video.ready',
            name: '测试视频模型',
            adapter_status: 'available',
            is_configured: true,
            test_status: 'success',
          }],
        }),
      });
      return;
    }
    if (path === '/api/v1/subtitles/tracks') {
      subtitleQuery = url.search;
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
      return;
    }
    throw new Error(`未模拟接口: ${route.request().method()} ${path}`);
  });

  await page.goto('/novels');
  await expect(page.getByRole('heading', { name: '小说管理' })).toBeVisible();
  await expect(page.getByRole('button', { name: '预览《星港追光》' })).toBeVisible();
  await expect(page.getByText('最新工程已准备好，可进入 Studio 指挥台继续处理。')).toBeVisible();
  await page.getByRole('link', { name: /进入 Studio 指挥台/ }).click();
  await expect(page).toHaveURL(/\/studio\?workflow_id=wf-smart-console/);

  const commandBar = page.getByTestId('studio-command-bar');
  const episodeWorkspace = page.getByTestId('studio-episode-workspace');
  await expect(episodeWorkspace).toBeVisible();
  await expect(episodeWorkspace.getByLabel('剧集工程')).toContainText('正在加载剧集…');
  await expect(episodeWorkspace.getByLabel('剧集工程').getByRole('button')).toHaveCount(0);
  resolveChapterRequest();
  const workspaceBox = await episodeWorkspace.boundingBox();
  expect(workspaceBox?.width).toBeGreaterThanOrEqual(1400);
  const seriesSummary = episodeWorkspace.getByTestId('studio-series-summary');
  await expect(seriesSummary).toContainText('尚未设置系列封面');
  await expect(seriesSummary).toContainText('已完成 1 集');
  await expect(seriesSummary).toContainText('总集数 2 集');
  await expect(seriesSummary).toContainText('2026-07-05');
  await expect(episodeWorkspace.getByLabel('剧集工程').getByRole('button')).toHaveCount(2);
  await expect(episodeWorkspace.getByLabel('剧集工程').locator('[aria-current="page"]')).toHaveCount(1);
  await expect(episodeWorkspace.getByLabel('剧集工程').getByText('其他小说工作流')).toHaveCount(0);
  await expect(episodeWorkspace.getByLabel('剧集工程')).toContainText('2/8 · 当前制作');
  await expect(episodeWorkspace.getByLabel('剧集工程')).toContainText('未创建工程 · 点击创建');
  const boardHeader = episodeWorkspace.getByTestId('studio-episode-board-header');
  await expect(boardHeader).toContainText('第一章 星港起飞 制作看板');
  await expect(boardHeader).toContainText('总镜头 5');
  await expect(boardHeader).toContainText('完成 1');
  await expect(boardHeader).toContainText('待处理 4');
  await expect(boardHeader).toContainText('预计时长 00:22');
  await expect(episodeWorkspace.getByRole('heading', { name: '设定与资产' })).toBeVisible();
  await expect(episodeWorkspace.getByRole('heading', { name: '分镜与配音' })).toBeVisible();
  await expect(episodeWorkspace.getByRole('heading', { name: '镜头生成' })).toBeVisible();
  await expect(episodeWorkspace.getByRole('heading', { name: '复审与成片' })).toBeVisible();
  await expect(episodeWorkspace.getByRole('heading', { name: '本集概览' })).toBeVisible();
  await expect(episodeWorkspace.getByRole('heading', { name: '模型就绪度' })).toBeVisible();
  await expect(episodeWorkspace.getByText('1/1 模型就绪')).toBeVisible();
  await expect(episodeWorkspace.getByRole('heading', { name: '失败任务' })).toBeVisible();
  await expect(episodeWorkspace.getByTestId('studio-shot-generation-summary')).toContainText('镜头生成（已完成 1/5）');
  await expect(episodeWorkspace.getByTestId('studio-shot-generation-summary')).toContainText('PixelWave v2.1');
  await expect(episodeWorkspace.locator('[data-testid^="studio-quick-action-"]')).toHaveCount(12);
  const quickActionPaths = {
    entities: '/studio/cards', 'scene-assets': '/assets', 'reference-locks': '/studio/cards',
    storyboard: '/storyboards', voices: '/studio/cards', subtitles: '/subtitles',
    'video-generation': '/video-generation', 'shot-references': '/studio/shot-review',
    'shot-quality': '/studio/shot-review', 'continuity-review': '/studio/continuity-review',
    timeline: '/workflow', output: '/workflow',
  };
  for (const [actionId, pathname] of Object.entries(quickActionPaths)) {
    const href = await episodeWorkspace.getByTestId(`studio-quick-action-${actionId}`).getAttribute('href');
    const target = new URL(href || '', 'http://localhost');
    expect(target.pathname).toBe(pathname);
    expect(target.searchParams.get('workflow_id')).toBe('wf-smart-console');
    expect(target.searchParams.get('novel_id')).toBe('novel-smart-console');
    expect(target.searchParams.get('chapter_id')).toBe('chapter-smart-console');
    expect(target.searchParams.get('source')).toBe('studio');
    expect(target.searchParams.get('return_to')).toContain('/studio?workflow_id=wf-smart-console');
  }
  await expect(episodeWorkspace.getByTestId('studio-quick-action-subtitles')).toHaveAttribute('href', /\/subtitles\?/);
  await episodeWorkspace.getByTestId('studio-quick-action-subtitles').click();
  await expect(page).toHaveURL(/\/subtitles\?.*workflow_id=wf-smart-console/);
  await expect(page.getByTestId('studio-task-context')).toContainText('字幕与文本校对');
  await expect(page).toHaveURL(/novel_id=novel-smart-console/);
  await expect(page).toHaveURL(/chapter_id=chapter-smart-console/);
  await expect(page.getByTestId('studio-return-dock')).toBeVisible();
  await expect.poll(() => subtitleQuery).toContain('workflow_id=wf-smart-console');
  await expect.poll(() => subtitleQuery).toContain('chapter_id=chapter-smart-console');
  await page.getByTestId('studio-return-dock').click();
  await expect(page).toHaveURL(/\/studio\?.*workflow_id=wf-smart-console/);
  await expect(episodeWorkspace.getByTestId('studio-cost-summary')).toContainText('暂无费用记录');
  await expect(commandBar.getByRole('button', { name: '测试验证' })).toBeVisible();
  await expect(commandBar.getByRole('button', { name: '生产出片' })).toBeVisible();
  await expect(commandBar.getByRole('button', { name: '生成 Story Bible' })).toBeVisible();
  await expect(commandBar.getByText('下一步：生产锁定')).toBeVisible();
  await expect(commandBar.getByText('星港追光')).toBeVisible();
  await expect(commandBar.getByText('第一章 星港起飞')).toBeVisible();
  await expect(commandBar.getByText('Readiness 81%')).toBeVisible();
  await expect(commandBar.getByText('阻断 1')).toBeVisible();
  await expect(commandBar.getByText('生产前需要人工确认最终资产锁。')).toBeVisible();
  const commandBarBox = await commandBar.boundingBox();
  expect((commandBarBox?.y || 0) + (commandBarBox?.height || 0)).toBeLessThanOrEqual(1058);

  const stageFlow = page.getByTestId('studio-stage-flow');
  await expect(stageFlow.getByText('制作主线')).toBeVisible();
  await expect(stageFlow.getByText('5阶段')).toBeVisible();
  await expect(stageFlow.getByText('内容准备')).toBeVisible();
  await expect(stageFlow.getByText('设定锁定')).toBeVisible();
  await expect(stageFlow.getByText('本集工程')).toBeVisible();
  await expect(stageFlow.getByText('草片生产')).toBeVisible();
  await expect(stageFlow.getByText('复审出片')).toBeVisible();
  await expect(page.getByText('高级工作区')).toBeVisible();
  await expect(page.getByRole('tab', { name: '生产' })).toHaveAttribute('data-state', 'active');

  await commandBar.getByRole('button', { name: '生产锁定' }).click();
  await expect(page.getByRole('dialog', { name: '确认生产锁定' })).toBeVisible();
  await expect(page.getByText('提交最终资产锁')).toBeVisible();
  await page.getByRole('button', { name: '确认锁定' }).click();

  await expect(page.getByText('执行完成')).toBeVisible();
  expect(actionPayload).toMatchObject({ code: 'finalize_production_pack', mode: 'production' });

  const plannedEpisode = episodeWorkspace.getByLabel('剧集工程').getByRole('button').filter({ hasText: '第二章 追光航线' });
  await expect(plannedEpisode).toBeEnabled();
  await plannedEpisode.click();
  await expect(page).toHaveURL(/\/studio\?workflow_id=wf-smart-console-2/);
  await expect(episodeWorkspace.getByLabel('剧集工程').getByRole('button')).toHaveCount(2);
  await expect(episodeWorkspace.getByLabel('剧集工程').locator('[aria-current="page"]')).toHaveCount(1);
  await expect(page.getByTestId('studio-episode-board-header')).toContainText('第二章 追光航线 制作看板');
  expect(createdEpisodePayload).toMatchObject({ novel_id: 'novel-smart-console', chapter_id: 'chapter-smart-console-2' });
});
