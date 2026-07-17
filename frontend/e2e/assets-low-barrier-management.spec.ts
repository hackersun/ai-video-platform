import { expect, test } from '@playwright/test';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

const novel = { id: 'novel-low-barrier', title: '低门槛资产小说' };
const entities = [
  { id: 'entity-character', name: '沈砚', entity_type: 'character', description: '黑衣少年剑修' },
  { id: 'entity-scene', name: '旧城雨巷', entity_type: 'scene', description: '冷蓝雨夜街巷' },
  { id: 'entity-prop', name: '铜铃', entity_type: 'prop', description: '裂纹青铜铃' },
];

const baseAsset = {
  id: 'asset-current-front',
  category: 'character',
  asset_type: 'image',
  name: '沈砚正面当前定稿',
  url: '/static/dev/current-front.png',
  thumbnail_url: '/static/dev/current-front-thumb.png',
  novel_id: novel.id,
  entity_id: 'entity-character',
  entity_type: 'character',
  version: 2,
  is_locked: true,
  is_final: true,
  generation_params: {
    source: 'entity_multiview',
    view_key: 'front',
    view_label: '正面',
    visual_contract: { id: 'contract-current-front' },
    reference_view_key: 'side',
  },
};

const historyAssets = [
  {
    ...baseAsset,
    id: 'asset-history-front-v1',
    name: '沈砚正面历史版本',
    url: '/static/dev/history-front.png',
    thumbnail_url: '/static/dev/history-front-thumb.png',
    version: 1,
    is_locked: false,
    is_final: false,
  },
  {
    id: 'asset-history-side-v1',
    category: 'character',
    asset_type: 'image',
    name: '沈砚侧面历史版本',
    url: '/static/dev/history-side.png',
    thumbnail_url: '/static/dev/history-side-thumb.png',
    novel_id: novel.id,
    entity_id: 'entity-character',
    entity_type: 'character',
    version: 1,
    generation_params: { source: 'entity_multiview', view_key: 'side', view_label: '侧面' },
  },
];

async function installAssetMocks(page: any) {
  await page.addInitScript(({ authToken, authUserId }) => {
    localStorage.setItem('auth_token', authToken);
    localStorage.setItem('user', JSON.stringify({
      id: authUserId,
      username: authUserId,
      email: `${authUserId}@example.test`,
    }));
  }, { authToken: devToken('asset-low-barrier-user'), authUserId: 'asset-low-barrier-user' });

  await page.route('**/api/v1/assets/categories', async (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify([
      { id: 'character', name: 'character', name_cn: '角色' },
      { id: 'scene', name: 'scene', name_cn: '场景' },
      { id: 'prop', name: 'prop', name_cn: '道具' },
    ]),
  }));
  await page.route('**/api/v1/projects**', async (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify([]),
  }));
  await page.route('**/api/v1/novels**', async (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify([novel]),
  }));
  await page.route('**/api/v1/chapters/**', async (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify([]),
  }));
  await page.route('**/api/v1/scripts**', async (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify([]),
  }));
  await page.route('**/api/v1/story-bibles/entities**', async (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(entities),
  }));
  await page.route('**/api/v1/asset-maintenance/entity-options**', async (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(entities.map((entity) => ({
      ...entity,
      lifecycle_status: 'approved',
      active_asset_count: entity.id === 'entity-character' ? 1 : 0,
    }))),
  }));
  await page.route('**/api/v1/assets/view-presets', async (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      presets: [
        {
          entity_type: 'character',
          category: 'character',
          title: '角色三视图',
          description: '锁定角色正面、侧面、背面外观。',
          recommended_aspect_ratios: ['9:16'],
          views: [
            { key: 'front', label: '正面', aspect_ratio: '9:16' },
            { key: 'side', label: '侧面', aspect_ratio: '9:16' },
            { key: 'back', label: '背面', aspect_ratio: '9:16' },
          ],
        },
        {
          entity_type: 'scene',
          category: 'scene',
          title: '场景四视图',
          description: '固定场景全景、空间布局、关键细节和光影氛围。',
          recommended_aspect_ratios: ['16:9'],
          views: [
            { key: 'establishing', label: '全景定场', aspect_ratio: '16:9' },
            { key: 'layout', label: '空间布局', aspect_ratio: '16:9' },
            { key: 'detail', label: '关键细节', aspect_ratio: '16:9' },
            { key: 'lighting', label: '光影氛围', aspect_ratio: '16:9' },
          ],
        },
        {
          entity_type: 'prop',
          category: 'prop',
          title: '道具多视图',
          description: '固定道具主视图、细节、比例和使用状态。',
          recommended_aspect_ratios: ['1:1'],
          views: [
            { key: 'main', label: '主视图', aspect_ratio: '1:1' },
            { key: 'detail', label: '细节', aspect_ratio: '1:1' },
            { key: 'scale', label: '比例参考', aspect_ratio: '1:1' },
          ],
        },
      ],
    }),
  }));
  await page.route('**/api/v1/assets/style-templates', async (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ templates: [{ style: 'anime', label: '动漫' }] }),
  }));
  await page.route('**/api/v1/assets/entity/entity-character/versions?**', async (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(historyAssets),
  }));
  await page.route('**/api/v1/assets?**', async (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify([baseAsset]),
  }));
}

test('asset edit supports URL previews, history backfill, entity-specific guidance, and locked-context regeneration', async ({ page }) => {
  await installAssetMocks(page);

  let updatePayload: any = null;
  let regeneratePayload: any = null;
  await page.route('**/api/v1/assets/asset-current-front**', async (route) => {
    if (route.request().method() === 'PUT') {
      updatePayload = route.request().postDataJSON();
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ...baseAsset, ...updatePayload }),
      });
    }
    if (route.request().method() === 'POST' && route.request().url().endsWith('/regenerate')) {
      regeneratePayload = route.request().postDataJSON();
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ...baseAsset,
          id: 'asset-current-front-v3',
          name: '沈砚正面重新生成',
          url: '/static/dev/current-front-v3.png',
          thumbnail_url: '/static/dev/current-front-v3-thumb.png',
          version: 3,
          is_locked: false,
          is_final: false,
        }),
      });
    }
    return route.continue();
  });

  await page.goto('/assets');
  await expect(page.getByRole('heading', { name: '资产库' })).toBeVisible();

  const wizard = page.getByTestId('asset-wizard');
  await page.getByLabel('向导小说').selectOption(novel.id);
  await expect(wizard.getByRole('heading', { name: '角色三视图' })).toBeVisible();
  await expect(wizard.getByRole('button', { name: /生成 \d+ 个缺失视图/ })).toBeVisible();

  await page.getByLabel('资产对象类型').selectOption('scene');
  await expect(wizard.getByRole('heading', { name: '场景四视图' })).toBeVisible();
  await expect(wizard.getByText('固定场景全景、空间布局、关键细节和光影氛围。')).toBeVisible();
  await expect(wizard.getByRole('button', { name: /生成 \d+ 个缺失视图/ })).toBeVisible();

  await page.getByLabel('资产对象类型').selectOption('prop');
  await expect(wizard.getByRole('heading', { name: '道具多视图' })).toBeVisible();
  await expect(wizard.getByText('固定道具主视图、细节、比例和使用状态。')).toBeVisible();
  await expect(wizard.getByRole('button', { name: /生成 \d+ 个缺失视图/ })).toBeVisible();

  await page.getByLabel('资产对象类型').selectOption('character');
  await page.getByLabel('小说对象').selectOption('entity-character');

  const card = page.getByTestId('asset-card').filter({ hasText: baseAsset.name });
  await card.getByRole('button', { name: '编辑' }).click();

  await expect(page.getByRole('img', { name: '资源文件' })).toBeVisible();
  await page.getByPlaceholder('资源 URL 或 /static/... 路径').fill('/static/dev/manual-resource.png');
  await expect(page.getByRole('img', { name: '资源文件' })).toHaveAttribute('src', `${API_BASE.replace(/\/api\/v1$/, '')}/static/dev/manual-resource.png`);
  await page.getByPlaceholder('缩略图 URL，可选').fill('/static/dev/manual-thumb.png');
  await expect(page.getByRole('img', { name: '缩略图' })).toHaveAttribute('src', `${API_BASE.replace(/\/api\/v1$/, '')}/static/dev/manual-thumb.png`);

  const resourceField = page.getByPlaceholder('资源 URL 或 /static/... 路径').locator('xpath=ancestor::div[contains(@class, "space-y-2")][1]');
  await resourceField.getByRole('button', { name: '打开', exact: true }).click();
  const previewDialog = page.getByRole('dialog', { name: '资产预览' });
  await expect(previewDialog).toBeVisible();
  await expect(previewDialog.getByRole('img', { name: baseAsset.name })).toHaveAttribute('src', `${API_BASE.replace(/\/api\/v1$/, '')}/static/dev/manual-resource.png`);
  await previewDialog.getByRole('button', { name: '关闭' }).click();

  await page.getByRole('button', { name: '从生成历史选择' }).click();
  const historyDialog = page.getByRole('dialog', { name: '生成历史' });
  await expect(historyDialog).toBeVisible();
  await expect(historyDialog.getByText('沈砚正面历史版本')).toBeVisible();
  await historyDialog.getByRole('button', { name: '使用此版本' }).first().click();
  await expect(page.getByPlaceholder('资源 URL 或 /static/... 路径')).toHaveValue('/static/dev/history-front.png');
  await expect(page.getByPlaceholder('缩略图 URL，可选')).toHaveValue('/static/dev/history-front-thumb.png');

  await page.getByRole('button', { name: '保存资产' }).click();
  await expect(page.getByText('资产已更新')).toBeVisible();
  expect(updatePayload).toMatchObject({
    url: '/static/dev/history-front.png',
    thumbnail_url: '/static/dev/history-front-thumb.png',
  });

  await card.getByRole('button', { name: '重生成' }).click();
  await expect(page.getByText(/已按/)).toBeVisible();
  expect(regeneratePayload).toMatchObject({
    style: 'anime',
    entity_id: 'entity-character',
    entity_type: 'character',
    view_key: 'front',
    source_asset_id: 'asset-current-front',
    inherit_locked_settings: true,
    was_locked: true,
    was_final: true,
  });
});

test('asset library guides production-card missing view completion from contextual URL', async ({ page }) => {
  await installAssetMocks(page);

  let generatePayload: any = null;
  await page.route('**/api/v1/assets/generate-entity-views', async (route) => {
    generatePayload = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ total: 1, failures: [] }),
    });
  });

  await page.goto(`/assets?novel_id=${novel.id}&entity_type=character&entity_id=entity-character&view_key=back&action=generate-missing&source=production-card`);

  const wizard = page.getByTestId('asset-wizard');
  await expect(wizard.getByText('来自定稿卡的补齐任务')).toBeVisible();
  await expect(wizard.getByText('沈砚 · 背面')).toBeVisible();
  await expect(page.getByLabel('向导小说')).toHaveValue(novel.id);
  await expect(page.getByLabel('资产对象类型')).toHaveValue('character');
  await expect(page.getByLabel('小说对象')).toHaveValue('entity-character');
  await expect(page.getByTestId('asset-wizard-view-back').getByText('定稿卡指定补齐项')).toBeVisible();

  await wizard.getByRole('button', { name: '生成背面缺失视图' }).click();

  await expect(page.getByText('已生成 1 张背面参考图')).toBeVisible();
  expect(generatePayload).toMatchObject({
    entity_id: 'entity-character',
    novel_id: novel.id,
    view_keys: ['back'],
    style: 'anime',
    consistency_mode: 'standard',
  });
});
