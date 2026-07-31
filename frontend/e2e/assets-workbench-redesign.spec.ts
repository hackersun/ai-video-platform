import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 86400 })).toString('base64url');
  return `dev.${payload}.sig`;
}

const assets = [
  {
    id: 'asset-character-front', category: 'character', asset_type: 'image', name: '萧云正面定稿',
    description: '主角正面角色参考', url: '/static/generated/images/asset-character-front-f5568b81-402a7f40eb524fc692ed1f9e4e8c2433.png',
    novel_id: 'novel-workbench', entity_id: 'character-xiao-yun', entity_type: 'character',
    version: 3, is_locked: true, is_final: true, usage_count: 128,
    generation_params: { view_key: 'front', view_label: '正面', visual_consistency: { score: 94 } },
    updated_at: '2026-07-15T09:20:00+08:00',
  },
  {
    id: 'asset-prop-failed', category: 'prop', asset_type: 'image', name: '青铜铃',
    description: '贯穿四章的关键道具', url: '/static/generated/images/asset-pose-2997e222-2e301926a6b04d6fbf14fb7d25b39606.png',
    novel_id: 'novel-workbench', entity_id: 'prop-bell', entity_type: 'prop', version: 2,
    status: 'failed', error_message: '细节视图生成失败：材质描述与参考图不一致', usage_count: 12,
    generation_params: { view_key: 'detail', view_label: '细节' }, updated_at: '2026-07-15T08:45:00+08:00',
  },
  {
    id: 'asset-scene-draft', category: 'scene', asset_type: 'image', name: '雾港外景',
    description: '第一章雾港定场', url: '/static/generated/images/asset-scene-establishing-861978d7-42ef806803844f6799982e171d9573d6.png',
    novel_id: 'novel-workbench', entity_id: 'scene-fog-port', entity_type: 'scene',
    version: 1, is_locked: false, is_final: false, usage_count: 0,
    generation_params: { view_key: 'establishing', view_label: '全景' }, updated_at: '2026-07-15T08:10:00+08:00',
  },
];

function makeAssets(count: number) {
  return Array.from({ length: count }, (_, index) => {
    const sequence = index + 1;
    return {
      ...assets[index % assets.length],
      id: `asset-page-${String(sequence).padStart(2, '0')}`,
      name: `分页资产 ${String(sequence).padStart(2, '0')}`,
      status: undefined,
      error_message: undefined,
      is_final: true,
    };
  });
}

async function installMocks(page: any, assetItems: Record<string, any>[] = assets) {
  const userId = 'asset-workbench-user';
  await page.addInitScript(({ token, user }) => {
    localStorage.setItem('auth_token', token);
    localStorage.setItem('user', JSON.stringify({ id: user, username: user }));
  }, { token: devToken(userId), user: userId });
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace(/\/+$/, '');
    if (path === '/api/v1/assets/categories') return route.fulfill({ json: [
      { id: 'character', name: 'character', name_cn: '角色' },
      { id: 'scene', name: 'scene', name_cn: '场景' },
      { id: 'prop', name: 'prop', name_cn: '道具' },
    ] });
    if (path === '/api/v1/projects') return route.fulfill({ json: [] });
    if (path === '/api/v1/novels') return route.fulfill({ json: [{ id: 'novel-workbench', title: '雾港铜铃' }] });
    if (path === '/api/v1/assets/view-presets') return route.fulfill({ json: { presets: [] } });
    if (path === '/api/v1/assets/style-templates') return route.fulfill({ json: { templates: [] } });
    if (path === '/api/v1/chapters/novel/novel-workbench' || path === '/api/v1/scripts') return route.fulfill({ json: [] });
    if (path === '/api/v1/asset-maintenance/entity-options') return route.fulfill({ json: [
      { id: 'character-xiao-yun', name: '萧云', entity_type: 'character' },
      { id: 'prop-bell', name: '青铜铃', entity_type: 'prop' },
      { id: 'scene-fog-port', name: '雾港', entity_type: 'scene' },
    ] });
    if (path === '/api/v1/story-bibles/entities') return route.fulfill({ json: [
      { id: 'character-xiao-yun', name: '萧云', entity_type: 'character' },
      { id: 'prop-bell', name: '青铜铃', entity_type: 'prop' },
      { id: 'scene-fog-port', name: '雾港', entity_type: 'scene' },
    ] });
    if (path === '/api/v1/assets') return route.fulfill({ json: assetItems });
    return route.fulfill({ json: [] });
  });
}

test('asset workbench prioritizes failure recovery, inspection and batch maintenance', async ({ page }) => {
  await installMocks(page);
  await page.goto('/assets');

  await expect(page.getByRole('heading', { name: '资产工作台' })).toBeVisible();
  const workbench = page.getByTestId('asset-workbench');
  await expect(workbench.getByText('雾港铜铃').last()).toBeVisible();
  await expect(page.getByTestId('asset-table-row')).toHaveCount(3);

  await page.getByTestId('asset-collection-failed').click();
  await expect(page.getByTestId('asset-table-row')).toHaveCount(1);
  await expect(page.getByTestId('asset-table-row')).toContainText('细节视图生成失败');

  await page.getByTestId('asset-table-row').click();
  await expect(page.getByTestId('asset-inspector')).toContainText('青铜铃');
  await expect(page.getByTestId('asset-inspector')).toContainText('生成失败');

  await page.getByLabel('选择青铜铃').check();
  await expect(page.getByTestId('asset-bulk-bar')).toContainText('已选择 1 项');
  await expect(page.getByTestId('asset-bulk-bar').getByRole('button', { name: '锁定' })).toBeVisible();
  await expect(page.getByTestId('asset-bulk-bar').getByRole('button', { name: '解锁' })).toBeVisible();
  await expect(page.getByTestId('asset-bulk-bar').getByRole('button', { name: '改作用域' })).toBeVisible();
  await expect(page.getByTestId('asset-bulk-bar').getByRole('button', { name: '重建资产包' })).toBeVisible();
  await expect(page.getByTestId('asset-inspector').getByRole('button', { name: '版本' })).toBeVisible();
  await expect(page.getByTestId('asset-inspector').getByRole('button', { name: '设为全局' })).toBeVisible();
  await expect(page.getByTestId('asset-inspector').getByRole('button', { name: '归档' })).toBeVisible();
});

test('图像尺寸快照失败显示可理解说明和明确重试入口', async ({ page }) => {
  const failedCharacter = {
    ...assets[0],
    id: 'asset-character-front-failed',
    name: '萧云正面生成失败',
    url: undefined,
    thumbnail_url: undefined,
    is_locked: false,
    is_final: false,
    status: 'failed',
    error_message: 'invalid_snapshot_params: image_size',
    generation_params: { view_key: 'front', view_label: '正面', retryable: true },
  };
  await installMocks(page, [failedCharacter]);
  await page.goto('/assets?novel_id=novel-workbench&entity_type=character&entity_id=character-xiao-yun');

  const wizard = page.getByTestId('asset-wizard');
  await expect(wizard.getByText('图像尺寸参数与当前模型不兼容，可直接重试；如仍失败，请展开“生成设置”后重建资产包。')).toBeVisible();
  await expect(wizard.getByRole('button', { name: '重试生成' })).toHaveText('重试');
});

test('asset workbench remains usable on a mobile viewport', async ({ page }) => {
  await installMocks(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/assets');
  await expect(page.getByRole('heading', { name: '资产工作台' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0);
});

test('asset workbench paginates filtered assets and resets to the first page', async ({ page }) => {
  await installMocks(page, makeAssets(26));
  await page.goto('/assets');

  const pagination = page.getByTestId('asset-pagination');
  await expect(pagination).toContainText('显示 1-12 / 26');
  await expect(page.getByTestId('asset-table-row')).toHaveCount(12);
  await expect(page.getByTestId('asset-table-row').filter({ hasText: '分页资产 01' })).toHaveCount(1);
  await expect(page.getByTestId('asset-table-row').filter({ hasText: '分页资产 13' })).toHaveCount(0);

  await pagination.getByRole('button', { name: '下一页' }).click();

  await expect(pagination).toContainText('显示 13-24 / 26');
  await expect(page.getByTestId('asset-table-row').filter({ hasText: '分页资产 13' })).toHaveCount(1);
  await expect(page.getByTestId('asset-table-row').filter({ hasText: '分页资产 01' })).toHaveCount(0);

  await page.getByLabel('搜索资产').fill('分页资产 26');

  await expect(pagination).toContainText('显示 1-1 / 1');
  await expect(page.getByTestId('asset-table-row')).toHaveCount(1);
  await expect(page.getByTestId('asset-table-row').filter({ hasText: '分页资产 26' })).toHaveCount(1);

  await page.getByLabel('搜索资产').fill('');
  await pagination.getByLabel('每页资产数量').selectOption('24');
  await expect(pagination).toContainText('显示 1-24 / 26');
  await expect(page.getByTestId('asset-table-row')).toHaveCount(24);
});
