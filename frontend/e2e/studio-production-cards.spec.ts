import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `cards-user-${Date.now()}`;
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

test('studio production cards show readiness gaps and repair links', async ({ page }) => {
  const cardPayload = {
    novel_id: 'novel-1',
    summary: { ready: 1, incomplete: 1 },
    cards: [
      {
        entity_id: 'char-1',
        entity_type: 'character',
        name: '孙剑',
        novel_id: 'novel-1',
        visual: {
          views: [
            { view_key: 'front', view_label: '正面', asset_id: 'asset-front', url: '/static/front.png', is_locked: true, is_final: true, version: 2 },
            { view_key: 'side', view_label: '侧面', asset_id: 'asset-side', url: '/static/side.png', is_locked: false, is_final: false, version: 1 },
          ],
          required_views: ['front', 'side', 'back'],
          missing_views: ['back'],
          locked_count: 1,
        },
        voice: { voice: 'zh_male_01', voice_speed: 1, story_bible_id: 'bible-1', locked: true },
        profile: { description: '云上列车的年轻修理师' },
        state: {},
        usage: { shot_count: 8, last_used_at: '2026-07-02T12:00:00Z' },
        readiness: {
          score: 62,
          final_ready: false,
          gaps: [
            { code: 'view_missing:back', message: '缺少背面定稿图', fix_url: '/assets?novel_id=novel-1&entity_type=character&entity_id=char-1' },
            { code: 'view_unlocked:side', message: '侧面视图尚未锁定', fix_url: '/assets?novel_id=novel-1&entity_type=character&entity_id=char-1' },
          ],
        },
      },
      {
        entity_id: 'scene-1',
        entity_type: 'scene',
        name: '云端车站',
        novel_id: 'novel-1',
        visual: {
          views: [
            { view_key: 'wide', view_label: '全景', asset_id: 'scene-wide', url: '/static/scene.png', is_locked: true, is_final: true, version: 3 },
          ],
          required_views: ['wide'],
          missing_views: [],
          locked_count: 1,
        },
        voice: null,
        profile: { description: '漂浮在云层间的中转站' },
        state: {},
        usage: { shot_count: 4, last_used_at: null },
        readiness: { score: 100, final_ready: true, gaps: [] },
      },
    ],
  };
  let finalizePayload: any = null;

  await page.route('**/api/v1/production-cards/novel/novel-1/batch-finalize-supporting', async (route) => {
    finalizePayload = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        novel_id: 'novel-1',
        finalized: [{ entity_id: 'char-2', name: '阿月', asset_id: 'asset-ayue-front', voice: 'voice_a' }],
        skipped: [{ entity_id: 'char-1', name: '孙剑', reason: 'protagonist', occurrences: 8 }],
      }),
    });
  });

  await page.route('**/api/v1/production-cards/novel/novel-1', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(cardPayload),
    });
  });

  await page.goto('/studio/cards?novel_id=novel-1');

  await expect(page.getByRole('heading', { name: '定稿卡' })).toBeVisible();
  await expect(page.getByText('就绪 1')).toBeVisible();
  await expect(page.getByText('待补齐 1')).toBeVisible();
  await expect(page.getByText('孙剑')).toBeVisible();
  await expect(page.getByText('完整度 62%')).toBeVisible();
  await expect(page.getByText('缺少背面定稿图')).toBeVisible();
  await expect(page.getByRole('link', { name: '去补齐' }).first()).toHaveAttribute(
    'href',
    '/assets?novel_id=novel-1&entity_type=character&entity_id=char-1'
  );
  await expect(page.getByText('云端车站')).toBeVisible();
  await expect(page.getByText('终稿就绪')).toBeVisible();

  await page.getByRole('button', { name: '一键补齐配角' }).click();
  await expect(page.getByText('已补齐 1 个配角')).toBeVisible();
  await expect(page.getByText('阿月')).toBeVisible();
  await expect(page.getByText('voice_a · asset-ayue-front')).toBeVisible();
  await expect(page.getByText('跳过 1 个角色')).toBeVisible();
  await expect(page.getByText('孙剑 · protagonist')).toBeVisible();
  expect(finalizePayload).toEqual({ min_occurrences: 2 });
});
