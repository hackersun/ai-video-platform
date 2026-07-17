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
  const readyMetric = page.locator('header').getByText('终稿就绪', { exact: true }).locator('..');
  await expect(readyMetric).toContainText('1');
  const incompleteMetric = page.locator('header').getByText('待补齐', { exact: true }).locator('..');
  await expect(incompleteMetric).toContainText('1');
  const sunCard = page.getByTestId('production-card-char-1');
  await expect(sunCard.getByText('孙剑', { exact: true })).toBeVisible();
  await expect(sunCard).toContainText('完整度 62%');
  await expect(sunCard.getByText('缺少背面定稿图')).toBeVisible();
  await expect(sunCard.getByRole('link', { name: '去资产库补齐' }).first()).toHaveAttribute(
    'href',
    '/assets?novel_id=novel-1&entity_type=character&entity_id=char-1&view_key=back&action=generate-missing&source=production-card'
  );
  const sceneCard = page.getByTestId('production-card-scene-1');
  await expect(sceneCard.getByText('云端车站', { exact: true })).toBeVisible();
  await expect(sceneCard.getByText('终稿就绪', { exact: true })).toBeVisible();

  await expect(page.getByLabel('最低出镜次数')).toHaveValue('2');
  await page.getByLabel('最低出镜次数').fill('3');
  await page.getByLabel('图像模型配置 ID').fill('img-config-9');
  await page.getByLabel('声线池').fill('voice_alpha, voice_beta');
  await page.getByRole('button', { name: '一键补齐配角' }).click();
  await expect(page.getByText('已补齐 1 个配角')).toBeVisible();
  await expect(page.getByText('阿月')).toBeVisible();
  await expect(page.getByText('voice_a · asset-ayue-front')).toBeVisible();
  await expect(page.getByText('跳过 1 个角色')).toBeVisible();
  await expect(page.getByText('孙剑 · protagonist')).toBeVisible();
  expect(finalizePayload).toEqual({
    min_occurrences: 3,
    image_model_config_id: 'img-config-9',
    voice_pool: ['voice_alpha', 'voice_beta'],
  });
});

test('studio production cards complete missing views directly and carry precise context into assets', async ({ page }) => {
  const cardPayload = {
    novel_id: 'novel-1',
    summary: { ready: 0, incomplete: 3 },
    cards: [
      {
        entity_id: 'char-1',
        entity_type: 'character',
        name: '孙剑',
        novel_id: 'novel-1',
        visual: {
          views: [{ view_key: 'front', view_label: '正面', asset_id: 'asset-front', url: '/static/front.png', is_locked: true, is_final: true }],
          required_views: ['front', 'side', 'back'],
          missing_views: ['back'],
          locked_count: 1,
        },
        voice: { voice: 'zh_male_01', locked: true },
        profile: { description: '云上列车的年轻修理师' },
        usage: { shot_count: 8 },
        readiness: {
          score: 66,
          final_ready: false,
          gaps: [
            { code: 'view_missing:back', message: '缺少背面定稿图', fix_url: '/assets?novel_id=novel-1&entity_type=character&entity_id=char-1' },
          ],
        },
      },
      {
        entity_id: 'scene-1',
        entity_type: 'scene',
        name: '云端车站',
        novel_id: 'novel-1',
        visual: {
          views: [{ view_key: 'establishing', view_label: '全景定场', asset_id: 'scene-wide', url: '/static/scene.png', is_locked: true, is_final: true }],
          required_views: ['establishing', 'layout', 'detail'],
          missing_views: ['layout', 'detail'],
          locked_count: 1,
        },
        voice: null,
        profile: { description: '漂浮在云层间的中转站' },
        usage: { shot_count: 4 },
        readiness: {
          score: 55,
          final_ready: false,
          gaps: [{ code: 'view_missing:layout', message: '缺少空间布局参考图' }],
        },
      },
      {
        entity_id: 'prop-1',
        entity_type: 'prop',
        name: '星轨罗盘',
        novel_id: 'novel-1',
        visual: {
          views: [],
          required_views: ['main', 'detail'],
          missing_views: ['main', 'detail'],
          locked_count: 0,
        },
        voice: null,
        profile: { description: '主角定位云海航线的道具' },
        usage: { shot_count: 3 },
        readiness: {
          score: 30,
          final_ready: false,
          gaps: [{ code: 'view_missing:main', message: '缺少主视图定稿图' }],
        },
      },
    ],
  };
  const generateRequests: any[] = [];

  await page.route('**/api/v1/assets/generate-entity-views', async (route) => {
    const payload = route.request().postDataJSON();
    generateRequests.push(payload);
    if (generateRequests.length === 1) {
      await new Promise((resolve) => setTimeout(resolve, 150));
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ total: payload.view_keys?.length || 0, failures: [] }),
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

  const sunCard = page.getByTestId('production-card-char-1');
  await expect(sunCard.getByRole('link', { name: '去资产库补齐' })).toHaveAttribute(
    'href',
    '/assets?novel_id=novel-1&entity_type=character&entity_id=char-1&view_key=back&action=generate-missing&source=production-card'
  );
  await sunCard.getByRole('button', { name: '补齐背面' }).click();
  await expect(page.getByText('正在补齐 孙剑：背面')).toBeVisible();
  await expect(page.getByText('已补齐 1 项缺失视图')).toBeVisible();
  expect(generateRequests[0]).toEqual({ entity_id: 'char-1', view_keys: ['back'], style: 'anime' });

  const sceneCard = page.getByTestId('production-card-scene-1');
  await sceneCard.getByRole('button', { name: '补齐云端车站缺口' }).click();
  await expect(page.getByText('已补齐 2 项缺失视图')).toBeVisible();
  expect(generateRequests[1]).toEqual({ entity_id: 'scene-1', view_keys: ['layout', 'detail'], style: 'anime' });

  await page.getByRole('button', { name: '一键补齐全部缺口' }).click();
  await expect(page.getByText('已补齐 5 项缺失视图')).toBeVisible();
  expect(generateRequests.slice(2)).toEqual([
    { entity_id: 'char-1', view_keys: ['back'], style: 'anime' },
    { entity_id: 'scene-1', view_keys: ['layout', 'detail'], style: 'anime' },
    { entity_id: 'prop-1', view_keys: ['main', 'detail'], style: 'anime' },
  ]);
});
