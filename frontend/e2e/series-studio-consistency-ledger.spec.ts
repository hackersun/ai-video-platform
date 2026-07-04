import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `series-studio-ledger-${Date.now()}`;
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

test('consistency ledger shows score and repair actions', async ({ page }) => {
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/\/+/g, '/').replace(/\/$/, '');
    if (path === '/api/v1/workflow') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ workflow_id: 'wf-ledger', title: '雾港铜铃 第一集', status: 'active' }]),
      });
      return;
    }
    if (path === '/api/v1/studio/workflows/wf-ledger/snapshot') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          series_studio: { enabled: true, primary_console: 'series_studio', expert_drilldowns: [] },
          workflow: {
            id: 'wf-ledger',
            title: '雾港铜铃 第一集',
            status: 'active',
            novel_id: 'novel-ledger',
            chapter_id: 'chapter-ledger',
            latest_production_strategy_label: '快速草稿',
          },
          story_context: {
            novel: { id: 'novel-ledger', title: '雾港铜铃', genre: '悬疑' },
            chapter: { id: 'chapter-ledger', title: '第一章 雾港旧码头', chapter_number: 1 },
          },
          production_bible_summary: {
            readiness_score: 70,
            style: { visual_style: '冷色悬疑动漫' },
            characters: [{ entity_id: 'char-1', name: '孙剑', approved: true }],
            scenes: [],
            props: [],
            events: [],
            voices: [],
            missing_requirements: [],
            asset_readiness: { asset_count: 1, missing_asset_count: 0, ready: true },
            counts: { characters: 1, scenes: 0, props: 0, events: 0 },
          },
          series_plan: { novel_id: 'novel-ledger', current_episode: { episode_index: 1, title: '第一集' }, episodes: [] },
          episode_contract: {
            contract_id: 'contract-ledger',
            production_bible_hash: 'hash-ledger',
            locked_at: '2026-07-04T00:00:00+00:00',
            entity_locks: [{ entity_id: 'char-1', entity_type: 'character', name: '孙剑' }],
            required_checks: ['characters'],
          },
          consistency_ledger: {
            overall_score: 70,
            dimensions: {
              style: 100,
              character_visual: 0,
              scene: 100,
              prop_state: 100,
              voice: 100,
              event_continuity: 100,
              subtitle_timing: 100,
            },
            findings: [{
              code: 'shot_character_unbound',
              severity: 'blocking',
              shot_id: 'shot-1',
              message: '镜头没有绑定角色参考，人物一致性不可控',
              repair_action: { code: 'bind_character_reference', label: '绑定角色参考', risk: 'navigation' },
            }],
          },
          production: { shot_count: 1, asset_lock_coverage: 0, entity_ref_coverage: 0, ready: false },
          shots: [],
          assets: { total_count: 1, locked_count: 1, final_count: 1, by_category: { character: 1 } },
          jobs: { summary: { video_count: 0, tts_count: 0, synthesis_count: 0, media_count: 0 } },
          issues: [],
          actions: [],
          mode_policy: { mode: 'production', ready: false, blocking_issue_count: 0 },
        }),
      });
      return;
    }
    if (path === '/api/v1/production-cards/novel/novel-ledger') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ novel_id: 'novel-ledger', cards: [], summary: { ready: 0, incomplete: 0 } }) });
      return;
    }
    if (path === '/api/v1/workflow/wf-ledger/shot-review') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ workflow_id: 'wf-ledger', shots: [] }) });
      return;
    }
    if (path === '/api/v1/prompt-skills') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [], count: 0 }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({}) });
  });

  await page.goto('/studio?workflow_id=wf-ledger');

  const panel = page.getByTestId('consistency-ledger-panel');
  await expect(panel.getByText('一致性评分')).toBeVisible();
  await expect(panel.getByText('人物形象')).toBeVisible();
  await expect(panel.getByText('镜头没有绑定角色参考，人物一致性不可控')).toBeVisible();
  await expect(panel.getByRole('button', { name: '绑定角色参考' })).toBeVisible();

  await panel.getByRole('button', { name: '绑定角色参考' }).click();
  await expect(page).toHaveURL(/\/studio\/shot-review\?workflow_id=wf-ledger/);
});
