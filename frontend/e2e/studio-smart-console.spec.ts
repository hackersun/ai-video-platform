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
  shots: [],
  assets: { total_count: 3, locked_count: 3, final_count: 3, by_category: { character: 1, scene: 1, prop: 1 } },
  jobs: { summary: { video_count: 0, tts_count: 0, synthesis_count: 0, media_count: 0 } },
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
    secondary_actions: [],
  },
};

const smartNovel = {
  id: 'novel-smart-console',
  title: '星港追光',
  description: '一部围绕星港与追光者展开的科幻故事。',
  genre: '科幻',
  status: 'writing',
  word_count: 12000,
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

test('novels production entry opens studio command flow and confirms production actions', async ({ page }) => {
  let actionPayload: any = null;
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/\/+/g, '/').replace(/\/$/, '');
    if (path === '/api/v1/workflow') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ workflow_id: 'wf-smart-console', title: '星港追光 第一集', status: 'active' }]),
      });
      return;
    }
    if (path === '/api/v1/novels') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([smartNovel]) });
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
    throw new Error(`未模拟接口: ${route.request().method()} ${path}`);
  });

  await page.goto('/novels');
  await expect(page.getByRole('heading', { name: '小说管理' })).toBeVisible();
  await expect(page.getByText('星港追光')).toBeVisible();
  await expect(page.getByText('最新工程已准备好，可进入 Studio 指挥台继续处理。')).toBeVisible();
  await page.getByRole('link', { name: /进入 Studio 指挥台/ }).click();
  await expect(page).toHaveURL(/\/studio\?workflow_id=wf-smart-console/);

  const commandBar = page.getByTestId('studio-command-bar');
  await expect(commandBar.getByText('星港追光')).toBeVisible();
  await expect(commandBar.getByText('第一章 星港起飞')).toBeVisible();
  await expect(commandBar.getByText('Readiness 81%')).toBeVisible();
  await expect(commandBar.getByText('阻断 1')).toBeVisible();
  await expect(commandBar.getByText('生产前需要人工确认最终资产锁。')).toBeVisible();

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
});
