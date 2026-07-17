import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 86400 })).toString('base64url');
  return `dev.${payload}.sig`;
}

test('production graph separates story order from production revisions and links impact', async ({ page }) => {
  const userId = `graph-panel-${Date.now()}`;
  await page.addInitScript(({ token, id }) => {
    localStorage.setItem('auth_token', token);
    localStorage.setItem('user', JSON.stringify({ id, username: id, email: `${id}@example.test` }));
  }, { token: devToken(userId), id: userId });

  const laterStory = {
    id: 'event-later-story', event_type: 'prop_owner_changed', production_version: 1, episode_index: 3,
    story_time: { episode_index: 3, sequence: 1 }, production_time: { stage: 'script' }, affected_episode_indices: [3],
  };
  const earlierStory = {
    id: 'event-earlier-story', event_type: 'prop_owner_changed', production_version: 2, episode_index: 2,
    story_time: { episode_index: 2, sequence: 1 }, production_time: { stage: 'review' }, affected_episode_indices: [2, 3],
    affected_shots: [{ id: 'shot-2', review_url: '/studio/shot-review?workflow_id=wf-graph&shot_id=shot-2' }],
  };

  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace(/\/+$/, '');
    if (path === '/api/v1/workflow') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([{ workflow_id: 'wf-graph', title: '第三集', status: 'active' }]) });
      return;
    }
    if (path === '/api/v1/studio/workflows/wf-graph/snapshot') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          series_studio: { enabled: true, primary_console: 'series_studio', expert_drilldowns: [] },
          workflow: { id: 'wf-graph', title: '第三集', status: 'active', novel_id: 'novel-graph' },
          story_context: { novel: { id: 'novel-graph', title: '雾港铜铃' } },
          production_bible_summary: { readiness_score: 90, counts: {}, missing_requirements: [], asset_readiness: { ready: true } },
          production_graph: {
            version: 2,
            hash: '1234567890abcdef',
            story_order: [earlierStory, laterStory],
            production_revisions: [laterStory, earlierStory],
          },
          production: { shot_count: 1, ready: true }, shots: [], assets: {}, jobs: { summary: {} }, issues: [], actions: [], mode_policy: {},
        }),
      });
      return;
    }
    if (path === '/api/v1/production-cards/novel/novel-graph') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ cards: [], summary: {} }) });
      return;
    }
    if (path === '/api/v1/prompt-skills') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [], count: 0 }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });

  await page.goto('/studio?workflow_id=wf-graph');
  await page.getByRole('tab', { name: '复审' }).click();
  const panel = page.getByTestId('production-graph-panel');
  await expect(panel.getByText('Production Graph')).toBeVisible();
  await expect(panel.getByText('剧情顺序', { exact: true })).toBeVisible();
  await expect(panel.getByText('制作修订顺序', { exact: true })).toBeVisible();
  await expect(panel.getByText('第 2 集').first()).toBeVisible();
  await expect(panel.getByText('修订 v2').first()).toBeVisible();
  const impactLink = panel.getByRole('link', { name: '查看受影响镜头' }).first();
  await expect(impactLink).toHaveAttribute('href', /shot_id=shot-2/);
  await impactLink.click();
  await expect(page).toHaveURL(/\/studio\/shot-review\?workflow_id=wf-graph&shot_id=shot-2/);
});
