import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

function studioSnapshot({ locked = false, workflowId = 'wf-multi-episode', chapterId = 'chapter-1' } = {}) {
  const currentEpisodeIndex = chapterId === 'chapter-2' ? 2 : 1;
  return {
    series_studio: { enabled: true, primary_console: 'series_studio', expert_drilldowns: [] },
    workflow: {
      id: workflowId,
      title: currentEpisodeIndex === 2 ? '雾港铜铃 第二集' : '雾港铜铃 第一集',
      status: 'active',
      novel_id: 'novel-multi-episode',
      chapter_id: chapterId,
      latest_production_strategy_label: '快速草稿',
    },
    story_context: {
      novel: { id: 'novel-multi-episode', title: '雾港铜铃', genre: '悬疑' },
      chapter: {
        id: chapterId,
        title: currentEpisodeIndex === 2 ? '第二章 旧码头' : '第一章 雾港旧码头',
        chapter_number: currentEpisodeIndex,
      },
    },
    production_bible_summary: {
      readiness_score: 88,
      style: { visual_style: '冷色悬疑动漫' },
      characters: [],
      scenes: [],
      props: [],
      events: [],
      voices: [],
      missing_requirements: [],
      asset_readiness: { asset_count: 0, missing_asset_count: 0, ready: true },
      counts: { characters: 0, scenes: 0, props: 0, events: 0 },
    },
    series_plan: {
      novel_id: 'novel-multi-episode',
      current_episode: { episode_index: currentEpisodeIndex, title: currentEpisodeIndex === 2 ? '第二集' : '第一集', chapter_ids: [chapterId] },
      episodes: [
        {
          episode_index: 1,
          title: '第一集',
          chapter_ids: ['chapter-1'],
          chapter_range: { start_number: 1, end_number: 1, label: '1' },
          status: 'planned',
          summary: '沈砚抵达雾港。',
          carry_over_state: { characters: ['沈砚'], props: ['铜铃'], events: [] },
          workflow_id: 'wf-multi-episode',
        },
        {
          episode_index: 2,
          title: '第二集',
          chapter_ids: ['chapter-2'],
          chapter_range: { start_number: 2, end_number: 2, label: '2' },
          status: 'planned',
          summary: '旧码头线索升级。',
          carry_over_state: { characters: ['沈砚'], props: ['铜铃'], events: ['追查铜铃'] },
          workflow_id: 'wf-episode-2',
        },
      ],
    },
    episode_contract: locked ? {
      contract_id: 'contract-locked',
      workflow_id: workflowId,
      novel_id: 'novel-multi-episode',
      chapter_id: chapterId,
      locked_at: '2026-07-04T00:00:00+00:00',
      production_bible_hash: 'abcdef1234567890abcdef1234567890',
      entity_locks: [{ entity_id: 'char-1', name: '沈砚' }],
      required_checks: ['style', 'characters', 'reference_package'],
    } : null,
    production: { shot_count: 4, asset_lock_coverage: 1, entity_ref_coverage: 1, ready: true },
    shots: [],
    assets: { total_count: 0, locked_count: 0, final_count: 0, by_category: {} },
    jobs: { summary: { video_count: 0, tts_count: 0, synthesis_count: 0, media_count: 0 } },
    issues: [],
    actions: [],
    mode_policy: { mode: 'production', ready: true, blocking_issue_count: 0 },
  };
}

test.beforeEach(async ({ page }) => {
  const userId = `series-studio-episodes-${Date.now()}`;
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

test('multi episode plan and contract are visible', async ({ page }) => {
  let locked = false;

  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/\/+/g, '/').replace(/\/$/, '');
    if (path === '/api/v1/workflow') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { workflow_id: 'wf-multi-episode', title: '雾港铜铃 第一集', status: 'active' },
          { workflow_id: 'wf-episode-2', title: '雾港铜铃 第二集', status: 'active' },
        ]),
      });
      return;
    }
    if (path === '/api/v1/studio/workflows/wf-multi-episode/snapshot') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(studioSnapshot({ locked })),
      });
      return;
    }
    if (path === '/api/v1/studio/workflows/wf-episode-2/snapshot') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(studioSnapshot({ locked, workflowId: 'wf-episode-2', chapterId: 'chapter-2' })),
      });
      return;
    }
    if (
      (path === '/api/v1/workflow/wf-multi-episode/episode-contract/lock' ||
        path === '/api/v1/workflow/wf-episode-2/episode-contract/lock') &&
      route.request().method() === 'POST'
    ) {
      const workflowId = path.includes('wf-episode-2') ? 'wf-episode-2' : 'wf-multi-episode';
      const chapterId = workflowId === 'wf-episode-2' ? 'chapter-2' : 'chapter-1';
      locked = true;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(studioSnapshot({ locked: true, workflowId, chapterId }).episode_contract),
      });
      return;
    }
    if (path === '/api/v1/production-cards/novel/novel-multi-episode') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ novel_id: 'novel-multi-episode', cards: [], summary: { ready: 0, incomplete: 0 } }) });
      return;
    }
    if (path === '/api/v1/prompt-skills') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [], count: 0 }) });
      return;
    }
    throw new Error(`未模拟接口: ${route.request().method()} ${path}`);
  });

  await page.goto('/studio?workflow_id=wf-multi-episode');

  await expect(page.getByTestId('episode-plan-panel').getByRole('heading', { name: '多集计划' })).toBeVisible();
  await expect(page.getByText('第 1 集 · 第一集')).toBeVisible();
  await expect(page.getByTestId('episode-plan-panel')).toContainText('承接明细：沈砚、铜铃');
  await expect(page.getByTestId('episode-plan-panel')).toContainText('承接明细：沈砚、铜铃、追查铜铃');
  await expect(page.getByTestId('episode-contract-panel').getByRole('heading', { name: '剧集合约' })).toBeVisible();
  await expect(page.getByRole('button', { name: /锁定剧集合约|重新锁定剧集合约/ })).toBeVisible();

  await page.getByTestId('episode-plan-panel').getByRole('link', { name: '打开本集' }).nth(1).click();
  await expect(page).toHaveURL(/workflow_id=wf-episode-2/);
  await expect(page.getByText('第二集 · 连续性状态 88%')).toBeVisible();

  await page.getByRole('button', { name: '锁定剧集合约' }).click();
  await expect(page.getByText('abcdef123456...567890')).toBeVisible();
  expect(locked).toBe(true);
});
