import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

const snapshot = {
  series_studio: { enabled: true, primary_console: 'series_studio', expert_drilldowns: [] },
  workflow: {
    id: 'wf-repair',
    title: '修复测试小说 第一集',
    status: 'active',
    novel_id: 'novel-repair',
    chapter_id: 'chapter-repair',
    storyboard_id: null,
  },
  story_context: {
    novel: { id: 'novel-repair', title: '修复测试小说', genre: '3D 修仙' },
    chapter: { id: 'chapter-repair', title: '第一章 山门', chapter_number: 1 },
    storyboard: null,
  },
  story_bible: null,
  production_bible_summary: {
    readiness_score: 0,
    counts: { characters: 0, scenes: 0, props: 0, events: 0 },
    asset_readiness: { asset_count: 0, missing_asset_count: 0, ready: false },
  },
  production: { shot_count: 0, asset_lock_coverage: 0, entity_ref_coverage: 0, ready: false },
  shots: [],
  assets: { total_count: 0, locked_count: 0, final_count: 0, by_category: {} },
  jobs: { summary: { video_count: 0, tts_count: 0, synthesis_count: 0, media_count: 0 }, video_jobs: [], tts_jobs: [], synthesis_jobs: [], media_jobs: [] },
  issues: [],
  actions: [],
  mode_policy: { mode: 'production', ready: false, blocking_issue_count: 3, warning_issue_count: 0 },
  guidance: {
    readiness_score: 0,
    blocker_count: 3,
    current_stage: 'content',
    blockers: [
      {
        code: 'select_storyboard',
        message: '工作流缺少分镜，无法检查镜头生产条件。',
        severity: 'blocking',
        repair_action: { code: 'open_storyboard', label: '选择分镜', href: '/storyboards', risk: 'navigation' },
      },
      {
        code: 'missing_story_bible',
        message: '当前小说缺少 Story Bible，人物、场景、道具和事件一致性无法统一约束。',
        severity: 'blocking',
        repair_action: { code: 'open_story_bible', label: '生成 Story Bible', href: '/story-bibles', risk: 'navigation' },
      },
      {
        code: 'missing_shots',
        message: '当前工作流还没有镜头，无法进入视频生成和合成。',
        severity: 'blocking',
        repair_action: { code: 'open_storyboard', label: '生成或编辑分镜镜头', href: '/storyboards', risk: 'navigation' },
      },
    ],
    stages: [],
    secondary_actions: [],
  },
};

test.beforeEach(async ({ page }) => {
  const userId = `studio-manual-repair-${Date.now()}`;
  await page.addInitScript(({ token, user }) => {
    localStorage.setItem('auth_token', token);
    localStorage.setItem('user', JSON.stringify(user));
  }, {
    token: devToken(userId),
    user: { id: userId, username: userId, email: `${userId}@example.test` },
  });
});

test('manual repair keeps the current novel context and opens an actionable Story Bible flow', async ({ page }) => {
  let storyBibleNovelFilter = '';
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/\/+/g, '/').replace(/\/$/, '');
    if (path === '/api/v1/workflow') {
      await route.fulfill({ json: [{ workflow_id: 'wf-repair', id: 'wf-repair', title: '修复测试小说 第一集', status: 'active', novel_id: 'novel-repair', chapter_id: 'chapter-repair' }] });
      return;
    }
    if (path === '/api/v1/studio/workflows/wf-repair/snapshot') {
      await route.fulfill({ json: snapshot });
      return;
    }
    if (path === '/api/v1/novels') {
      await route.fulfill({ json: [
        { id: 'novel-repair', title: '修复测试小说', genre: '3D 修仙' },
        { id: 'novel-other', title: '不相关小说', genre: '都市' },
      ] });
      return;
    }
    if (path === '/api/v1/story-bibles') {
      storyBibleNovelFilter = url.searchParams.get('novel_id') || '';
      await route.fulfill({ json: storyBibleNovelFilter === 'novel-repair' ? [] : [
        {
          id: 'legacy-bible', user_id: 'test-user', novel_id: 'novel-other', title: 'Production Bible v4',
          character_rules: [], scene_rules: [], prop_rules: [], event_timeline: [], extra_data: {},
          created_at: '2026-08-06T00:00:00Z', updated_at: '2026-08-06T00:00:00Z',
        },
      ] });
      return;
    }
    await route.fulfill({ json: [] });
  });

  await page.goto('/studio?workflow_id=wf-repair');

  const repairPanel = page.getByLabel('本集运行状态');
  await expect(repairPanel.getByRole('heading', { name: '待处理事项' })).toBeVisible();
  await expect(repairPanel.getByText('先关联或创建本集分镜，工作室才能检查镜头。')).toBeVisible();
  await expect(repairPanel.getByText('为当前小说建立角色、场景、道具和事件设定。')).toBeVisible();
  await expect(repairPanel.getByText('分镜建立后生成镜头，才能继续视频和合成。')).toBeVisible();

  const storyBibleAction = repairPanel.getByRole('link', { name: '为当前小说生成设定' });
  const actionHref = new URL(await storyBibleAction.getAttribute('href') || '', 'http://localhost');
  expect(actionHref.pathname).toBe('/story-bibles');
  expect(actionHref.searchParams.get('workflow_id')).toBe('wf-repair');
  expect(actionHref.searchParams.get('novel_id')).toBe('novel-repair');
  expect(actionHref.searchParams.get('chapter_id')).toBe('chapter-repair');
  expect(actionHref.searchParams.get('source_issue_code')).toBe('missing_story_bible');
  expect(actionHref.searchParams.get('action')).toBe('create');
  expect(actionHref.searchParams.get('source')).toBe('studio');
  expect(actionHref.searchParams.get('return_to')).toContain('/studio?workflow_id=wf-repair');

  await storyBibleAction.click();

  await expect(page).toHaveURL(/\/story-bibles\?/);
  await expect.poll(() => storyBibleNovelFilter).toBe('novel-repair');
  await expect(page.getByText('正在处理《修复测试小说》')).toBeVisible();
  await expect(page.getByText('Production Bible v4')).toHaveCount(0);
  const dialog = page.getByRole('dialog', { name: '从小说生成 Story Bible' });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole('combobox')).toHaveValue('novel-repair');
});
