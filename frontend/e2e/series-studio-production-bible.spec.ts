import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

function studioSnapshot({ approved = false } = {}) {
  return {
    series_studio: { enabled: true, primary_console: 'series_studio', expert_drilldowns: [] },
    workflow: {
      id: 'wf-production-bible',
      title: '雾港铜铃 第一集',
      status: 'active',
      novel_id: 'novel-production-bible',
      latest_production_strategy_label: '快速草稿',
    },
    story_context: {
      novel: { id: 'novel-production-bible', title: '雾港铜铃', genre: '悬疑' },
      chapter: { id: 'chapter-production-bible', title: '第一章 雾港旧码头', chapter_number: 1 },
    },
    story_bible: { id: 'bible-production', title: '雾港 Story Bible', character_rule_count: 1, scene_rule_count: 1, prop_rule_count: 1, event_count: 1 },
    production_bible_summary: {
      readiness_score: approved ? 92 : 78,
      style: {
        visual_style: '冷色悬疑动漫',
        worldview: '潮湿雾港与旧工业区',
        negative_prompt: '避免现代喜剧画风',
      },
      characters: [{ entity_id: 'char-shenyan', name: '沈砚', description: '灰蓝长衫的调查者', approved }],
      scenes: [{ entity_id: 'scene-dock', name: '旧码头', description: '冷雾与锈蚀吊机', approved: true }],
      props: [{ entity_id: 'prop-bell', name: '铜铃', description: '旧铜关键线索', approved: true }],
      events: [{ entity_id: 'event-trace', name: '追查铜铃', description: '主线事件', approved: true }],
      voices: [{ entity_id: 'char-shenyan', character_name: '沈砚', voice: 'calm_male', source: 'entity_attributes' }],
      asset_readiness: { asset_count: 3, missing_asset_count: 0, ready: true },
      missing_requirements: [],
      counts: { characters: 1, scenes: 1, props: 1, events: 1, voices: 1 },
    },
    production: { shot_count: 4, asset_lock_coverage: 1, entity_ref_coverage: 1, ready: true },
    shots: [],
    assets: { total_count: 3, locked_count: 3, final_count: 3, by_category: { character: 1, scene: 1, prop: 1 } },
    jobs: { summary: { video_count: 0, tts_count: 0, synthesis_count: 0, media_count: 0 } },
    issues: [],
    actions: [],
    mode_policy: { mode: 'production', ready: true, blocking_issue_count: 0 },
  };
}

test.beforeEach(async ({ page }) => {
  const userId = `series-studio-bible-${Date.now()}`;
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

test('production bible panel exposes required continuity sections', async ({ page }) => {
  let approved = false;
  let approvePayload: any = null;

  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/\/+/g, '/').replace(/\/$/, '');
    if (path === '/api/v1/workflow') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ workflow_id: 'wf-production-bible', title: '雾港铜铃 第一集', status: 'active' }]),
      });
      return;
    }
    if (path === '/api/v1/studio/workflows/wf-production-bible/snapshot') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(studioSnapshot({ approved })),
      });
      return;
    }
    if (path === '/api/v1/story-bibles/entities/char-shenyan/approve' && route.request().method() === 'POST') {
      approvePayload = route.request().postDataJSON();
      approved = true;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ entity_id: 'char-shenyan', approved: true, attributes: {} }),
      });
      return;
    }
    if (path === '/api/v1/production-cards/novel/novel-production-bible') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ novel_id: 'novel-production-bible', cards: [], summary: { ready: 0, incomplete: 0 } }) });
      return;
    }
    if (path === '/api/v1/prompt-skills') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [], count: 0 }) });
      return;
    }
    throw new Error(`未模拟接口: ${route.request().method()} ${path}`);
  });

  await page.goto('/studio?workflow_id=wf-production-bible');

  const panel = page.getByTestId('production-bible-panel');
  await expect(panel.getByText('Production Bible')).toBeVisible();
  await expect(panel.getByText('风格', { exact: true })).toBeVisible();
  await expect(panel.getByText('角色', { exact: true })).toBeVisible();
  await expect(panel.getByText('场景', { exact: true })).toBeVisible();
  await expect(panel.getByText('道具', { exact: true })).toBeVisible();
  await expect(panel.getByText('事件', { exact: true })).toBeVisible();
  await expect(panel.getByText('声线', { exact: true })).toBeVisible();

  await panel.getByRole('button', { name: '确认' }).first().click();
  await expect(panel.getByText('已确认').first()).toBeVisible();
  expect(approvePayload).toMatchObject({ approved: true, approval_note: 'Series Studio 确认' });
});
