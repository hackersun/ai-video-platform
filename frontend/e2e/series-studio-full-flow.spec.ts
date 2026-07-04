import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `series-studio-overview-${Date.now()}`;
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

test('series studio overview shows global control state', async ({ page }) => {
  let actionRequested = false;
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/\/+/g, '/').replace(/\/$/, '');
    if (path === '/api/v1/workflow') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ workflow_id: 'wf-series-overview', title: '雾港铜铃 第一集', status: 'active' }]),
      });
      return;
    }
    if (path === '/api/v1/studio/workflows/wf-series-overview/snapshot') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          series_studio: { enabled: true, primary_console: 'series_studio', expert_drilldowns: [] },
          workflow: {
            id: 'wf-series-overview',
            title: '雾港铜铃 第一集',
            status: 'active',
            novel_id: 'novel-series-overview',
            chapter_id: 'chapter-series-overview',
            latest_production_strategy: 'draft_fast',
            latest_production_strategy_label: '快速草稿',
          },
          story_context: {
            novel: { id: 'novel-series-overview', title: '雾港铜铃', genre: '悬疑' },
            chapter: { id: 'chapter-series-overview', title: '第一章 雾港旧码头', chapter_number: 1 },
          },
          production_bible_summary: {
            readiness_score: 72,
            missing_requirements: [{ code: 'asset_references_missing', message: '缺少角色定稿资产' }],
            counts: { characters: 2, scenes: 1, props: 1, events: 1 },
            characters: [{ entity_id: 'char-001', name: '沈砚' }],
            scenes: [{ entity_id: 'scene-001', name: '旧码头' }],
            props: [{ entity_id: 'prop-001', name: '铜铃' }],
            events: [{ entity_id: 'event-001', name: '追查铜铃' }],
            voices: [{ entity_id: 'char-001', voice: 'calm_male' }],
            asset_readiness: { asset_count: 2, missing_asset_count: 1, ready: false },
          },
          production: { shot_count: 4, asset_lock_coverage: 0.5, entity_ref_coverage: 0.75, ready: false },
          shots: [],
          assets: { total_count: 2, locked_count: 1, final_count: 1, by_category: { character: 1 } },
          jobs: { summary: { video_count: 0, tts_count: 0, synthesis_count: 0, media_count: 0 } },
          issues: [{ code: 'missing_asset_locks', message: '缺少资产锁', severity: 'blocking' }],
          actions: [
            { code: 'open_story_bible', label: '生成 Story Bible', href: '/story-bibles', risk: 'navigation' },
            { code: 'apply_asset_locks', label: '应用资产锁', risk: 'safe' },
          ],
          mode_policy: { mode: 'production', ready: false, blocking_issue_count: 1 },
        }),
      });
      return;
    }
    if (path === '/api/v1/studio/workflows/wf-series-overview/actions' && route.request().method() === 'POST') {
      const payload = route.request().postDataJSON();
      actionRequested = payload.code === 'apply_asset_locks';
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'action-series-overview',
          workflow_id: 'wf-series-overview',
          code: 'apply_asset_locks',
          label: '应用资产锁',
          status: 'succeeded',
          risk: 'safe',
          result: { applied_shot_count: 4 },
        }),
      });
      return;
    }
    if (path === '/api/v1/production-cards/novel/novel-series-overview') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ novel_id: 'novel-series-overview', cards: [], summary: { ready: 0, incomplete: 0 } }) });
      return;
    }
    if (path === '/api/v1/prompt-skills') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [], count: 0 }) });
      return;
    }
    throw new Error(`未模拟接口: ${route.request().method()} ${path}`);
  });

  await page.goto('/studio?workflow_id=wf-series-overview');

  await expect(page.getByText('系列动漫工作室')).toBeVisible();
  await expect(page.getByText('连续性状态')).toBeVisible();
  await expect(page.getByRole('button', { name: '下一步' })).toBeVisible();
  await expect(page.getByText('模型策略：快速草稿')).toBeVisible();

  await page.getByRole('button', { name: '下一步' }).click();
  await expect(page.getByText('最近动作：')).toBeVisible();
  expect(actionRequested).toBe(true);
});
