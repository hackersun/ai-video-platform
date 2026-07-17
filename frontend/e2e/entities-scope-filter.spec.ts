import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

const scopedEntity = {
  id: 'entity-lin-lan',
  entity_type: 'character',
  name: '林岚',
  canonical_name: '林岚',
  description: '十二岁的山城邮差少女',
  aliases: [],
  appearance: '银蓝短发，蓝白邮差斗篷，琥珀色眼睛。',
  relations: [],
  state_changes: [],
  attributes: {},
  tags: [],
  version: 1,
  is_approved: true,
  consistency_score: 1,
  confidence: 98,
  source: 'entity_extraction',
  novel_id: 'novel-001',
  created_at: '2026-07-07T00:00:00',
  updated_at: '2026-07-07T00:00:00',
};

test.beforeEach(async ({ page }) => {
  const userId = 'entities-scope-user';
  await page.addInitScript(({ authToken, authUserId }) => {
    localStorage.setItem('auth_token', authToken);
    localStorage.setItem('user', JSON.stringify({
      id: authUserId,
      username: authUserId,
      email: `${authUserId}@example.test`,
    }));
  }, { authToken: devToken(userId), authUserId: userId });
});

test('实体审阅台按 URL novel_id 过滤实体列表和统计请求', async ({ page }) => {
  const entityRequests: URL[] = [];
  const statsRequests: URL[] = [];

  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    let body: unknown = [];

    if (path.endsWith('/story-bibles/entities/stats')) {
      statsRequests.push(url);
      body = { total: 1, counts: { character: 1 } };
    } else if (path.endsWith('/story-bibles/entities')) {
      entityRequests.push(url);
      body = [scopedEntity];
    } else if (path.endsWith('/assets/view-presets')) {
      body = { presets: [] };
    } else if (path.endsWith(`/assets/entity/${scopedEntity.id}`)) {
      body = { assets: [], locked_assets: [], total: 0 };
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(body),
    });
  });

  await page.goto('/entities?novel_id=novel-001');

  await expect(page.getByText('林岚')).toBeVisible();
  expect(entityRequests.some((url) => (
    url.searchParams.get('novel_id') === 'novel-001'
    && url.searchParams.get('scope') === 'novel'
  ))).toBe(true);
  expect(statsRequests.some((url) => (
    url.searchParams.get('novel_id') === 'novel-001'
    && url.searchParams.get('scope') === 'novel'
  ))).toBe(true);
});
