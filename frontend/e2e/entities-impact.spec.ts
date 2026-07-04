import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

const entity = {
  id: 'entity-hero',
  entity_type: 'character',
  name: '沈砚',
  canonical_name: '沈砚',
  description: '灰蓝长衫调查者',
  aliases: ['主角'],
  appearance: '灰蓝长衫，黑发束起，随身铜铃。',
  relations: [],
  state_changes: [],
  attributes: {},
  tags: [],
  version: 2,
  is_approved: true,
  consistency_score: 1,
  confidence: 96,
  source: 'manual',
  novel_id: 'novel-impact',
  created_at: '2026-07-04T00:00:00',
  updated_at: '2026-07-04T00:00:00',
};

const impact = {
  entity: { id: entity.id, name: entity.name, entity_type: entity.entity_type },
  novel_id: entity.novel_id,
  first_affected_episode_index: 1,
  affected_episode_count: 3,
  affected_shot_count: 2,
  apply_options: [
    {
      episode_index: 1,
      label: '从第 1 集起应用新设定',
      affected_episode_count: 3,
      affected_shot_count: 2,
    },
  ],
  episodes: [
    { episode_index: 1, title: '第一集', affected_shot_count: 1, affected_shots: [{ id: 'shot-1', title: '雨巷初见' }] },
    { episode_index: 2, title: '第二集', affected_shot_count: 0, affected_shots: [] },
    { episode_index: 3, title: '第三集', affected_shot_count: 1, affected_shots: [{ id: 'shot-3', title: '铜铃回声' }] },
  ],
  shots: [
    { id: 'shot-1', title: '雨巷初见', episode_index: 1 },
    { id: 'shot-3', title: '铜铃回声', episode_index: 3 },
  ],
};

test.beforeEach(async ({ page }) => {
  const userId = 'entities-impact-user';
  await page.addInitScript(({ authToken, authUserId }) => {
    localStorage.setItem('auth_token', authToken);
    localStorage.setItem('user', JSON.stringify({
      id: authUserId,
      username: authUserId,
      email: `${authUserId}@example.test`,
    }));
  }, { authToken: devToken(userId), authUserId: userId });

  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    let body: unknown = [];

    if (path.endsWith('/story-bibles/entities/stats')) {
      body = { total: 1, counts: { character: 1 } };
    } else if (path.endsWith(`/story-bibles/entities/${entity.id}/impact`)) {
      body = impact;
    } else if (path.endsWith('/story-bibles/entities')) {
      body = [entity];
    } else if (path.endsWith('/assets/view-presets')) {
      body = { presets: [] };
    } else if (path.endsWith(`/assets/entity/${entity.id}`)) {
      body = { assets: [], locked_assets: [], total: 0 };
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(body),
    });
  });
});

test('实体详情展示跨集变更影响和从指定集数应用建议', async ({ page }) => {
  await page.goto('/entities');

  await page.getByRole('button', { name: '查看沈砚' }).click();

  await expect(page.getByRole('dialog')).toContainText('变更影响');
  await expect(page.getByRole('dialog')).toContainText('影响 3 集 · 2 个镜头');
  await expect(page.getByRole('dialog')).toContainText('从第 1 集起应用新设定');
  await expect(page.getByRole('dialog')).toContainText('第 3 集 · 1 个镜头');
});
