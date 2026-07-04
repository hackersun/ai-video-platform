import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 86400 })).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `asset-contract-user-${Date.now()}`;
  await page.addInitScript(({ token, id }) => {
    localStorage.setItem('auth_token', token);
    localStorage.setItem('user', JSON.stringify({ id, username: id, email: `${id}@example.test` }));
  }, { token: devToken(userId), id: userId });
});

test('asset wizard shows story contract controls and strict-mode review results', async ({ page }) => {
  const novel = { id: 'novel-1', title: '雨巷旧邮局' };
  const entity = { id: 'scene-1', name: '旧邮局', entity_type: 'scene', description: '1980年代雨夜旧邮局' };
  const generatedAsset = {
    id: 'asset-layout',
    category: 'scene',
    asset_type: 'image',
    name: '旧邮局 · 空间布局',
    url: '/static/dev/old-post-office-layout.png',
    thumbnail_url: '/static/dev/old-post-office-layout.png',
    novel_id: novel.id,
    entity_id: entity.id,
    entity_type: 'scene',
    generation_params: {
      source: 'entity_multiview',
      view_key: 'layout',
      view_label: '空间布局',
      consistency_mode: 'strict',
      visual_contract: {
        id: 'contract-old-post-office',
        entity_type: 'scene',
        name: '旧邮局',
        continuity_axes: {
          era: '1980年代小城',
          weather: '雨夜',
          lighting_direction: '门外冷蓝雨光，室内右上方暖黄灯',
          color_palette: '灰蓝冷雨色 + 暖黄室内灯',
        },
        spatial_layout: { fixed_elements: '左侧正门' },
      },
      visual_consistency: { score: 88.4, status: 'needs_review', issues: ['lighting_direction'] },
      retry_prompt_advice: '必须保持光源方向：门外冷蓝雨光，室内右上方暖黄灯',
    },
  };

  await page.route('**/api/v1/novels**', async (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([novel]) }));
  await page.route('**/api/v1/story-bibles/entities**', async (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([entity]) }));
  await page.route('**/api/v1/assets/categories', async (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([{ id: 'scene', name: 'scene', name_cn: '场景' }]) }));
  await page.route('**/api/v1/projects**', async (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) }));
  await page.route('**/api/v1/chapters/**', async (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) }));
  await page.route('**/api/v1/scripts**', async (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) }));
  await page.route('**/api/v1/assets/view-presets', async (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      presets: [{
        entity_type: 'scene',
        category: 'scene',
        title: '场景四视图',
        views: [
          { key: 'establishing', label: '全景定场', aspect_ratio: '16:9' },
          { key: 'layout', label: '空间布局', aspect_ratio: '16:9' },
          { key: 'detail', label: '关键细节', aspect_ratio: '16:9' },
          { key: 'lighting', label: '光影氛围', aspect_ratio: '16:9' },
        ],
      }],
    }),
  }));
  await page.route('**/api/v1/assets/style-templates', async (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ templates: [{ style: 'cinematic-2d', label: '2D电影' }] }) }));
  await page.route('**/api/v1/assets?**', async (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([generatedAsset]) }));
  await page.route('**/api/v1/assets/generate-entity-views', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ entity_type: 'scene', entity_id: entity.id, assets: { layout: generatedAsset }, total: 1, failures: [] }) });
  });
  let regenerateCalled = false;
  await page.route('**/api/v1/assets/asset-layout/regenerate', async (route) => {
    regenerateCalled = true;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ...generatedAsset, id: 'asset-layout-regenerated', version: 2 }),
    });
  });

  await page.goto('/assets?novel_id=novel-1&entity_type=scene&entity_id=scene-1&view_key=layout&action=generate-missing&source=production-card');
  const contractPanel = page.getByTestId('asset-visual-contract-panel');
  await expect(contractPanel.getByText('视觉契约')).toBeVisible();
  await expect(contractPanel.getByText('1980年代小城')).toBeVisible();
  await expect(contractPanel.getByText('门外冷蓝雨光，室内右上方暖黄灯')).toBeVisible();
  await expect(page.getByText('一致性 88')).toBeVisible();
  await expect(page.getByText('必须保持光源方向：门外冷蓝雨光，室内右上方暖黄灯')).toBeVisible();
  await expect(page.getByRole('button', { name: '按问题重生成' })).toBeVisible();
  await page.getByRole('button', { name: '按问题重生成' }).click();
  expect(regenerateCalled).toBe(true);

  await page.getByLabel('一致性模式').selectOption('strict');
  const [generateRequest] = await Promise.all([
    page.waitForRequest((request) => request.url().includes('/api/v1/assets/generate-entity-views') && request.method() === 'POST'),
    page.getByRole('button', { name: '生成空间布局缺失视图' }).click(),
  ]);

  expect(generateRequest.postDataJSON()).toMatchObject({
    entity_id: 'scene-1',
    novel_id: 'novel-1',
    view_keys: ['layout'],
    style: 'cinematic-2d',
    consistency_mode: 'strict',
  });
});
