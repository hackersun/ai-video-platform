import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 86400 })).toString('base64url');
  return `dev.${payload}.sig`;
}

const novel = { id: 'novel-asset-maintenance', title: '雨巷铜铃' };
const activeEntity = {
  id: 'entity-lin-che',
  name: '林澈',
  entity_type: 'character',
  description: '黑发青年侦探',
  lifecycle_status: 'approved',
  active_asset_count: 1,
};
const archivedEntity = {
  id: 'entity-old-character',
  name: '已停用旧角色',
  entity_type: 'character',
  lifecycle_status: 'archived',
  active_asset_count: 0,
};
const initialAsset = {
  id: 'asset-lin-che-front',
  category: 'character',
  asset_type: 'image',
  name: '林澈正面',
  novel_id: novel.id,
  entity_id: activeEntity.id,
  entity_type: 'character',
  url: '/static/dev/lin-che-front.png',
  is_final: true,
  is_locked: true,
  generation_params: { view_key: 'front', view_label: '正面' },
};

async function installMocks(page: any) {
  let assetActive = true;
  let entityActive = true;
  let optionRequests = 0;
  await page.addInitScript(({ token }) => {
    localStorage.setItem('auth_token', token);
    localStorage.setItem('user', JSON.stringify({ id: 'asset-maintenance-user', username: 'asset-maintenance-user' }));
  }, { token: devToken('asset-maintenance-user') });

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace(/\/+$/, '');
    if (path === '/api/v1/assets/categories') return route.fulfill({ json: [{ id: 'character', name: 'character', name_cn: '角色' }] });
    if (path === '/api/v1/projects') return route.fulfill({ json: [] });
    if (path === '/api/v1/novels') return route.fulfill({ json: [novel] });
    if (path === `/api/v1/chapters/novel/${novel.id}` || path === '/api/v1/scripts') return route.fulfill({ json: [] });
    if (path === '/api/v1/assets/view-presets') return route.fulfill({ json: { presets: [] } });
    if (path === '/api/v1/assets/style-templates') return route.fulfill({ json: { templates: [] } });
    if (path === '/api/v1/asset-maintenance/entity-options') {
      optionRequests += 1;
      return route.fulfill({ json: entityActive ? [activeEntity] : [] });
    }
    if (path === `/api/v1/asset-maintenance/entities/${activeEntity.id}/deactivate` && request.method() === 'POST') {
      entityActive = false;
      assetActive = false;
      return route.fulfill({ json: {
        entity_id: activeEntity.id,
        entity_name: activeEntity.name,
        lifecycle_status: 'archived',
        archived_asset_count: 1,
        already_inactive: false,
      } });
    }
    if (path === '/api/v1/story-bibles/entities') {
      return route.fulfill({ json: [activeEntity, archivedEntity] });
    }
    if (path === `/api/v1/assets/${initialAsset.id}` && request.method() === 'DELETE') {
      assetActive = false;
      return route.fulfill({ status: 204, body: '' });
    }
    if (path === '/api/v1/assets') return route.fulfill({ json: assetActive ? [initialAsset] : [] });
    return route.fulfill({ json: [] });
  });

  return { getOptionRequests: () => optionRequests };
}

test('asset wizard uses production-visible options and asset archive keeps the object selectable', async ({ page }) => {
  const state = await installMocks(page);
  await page.goto(`/assets?novel_id=${novel.id}`);

  const entitySelect = page.getByLabel('小说对象');
  await expect(page.getByTestId('asset-wizard').getByRole('heading', { name: '补齐资产' })).toBeVisible();
  await expect(entitySelect.locator('option', { hasText: '林澈' })).toHaveCount(1);
  await expect(entitySelect.locator('option', { hasText: '1 项资产' })).toHaveCount(1);
  await expect(entitySelect.locator('option', { hasText: '已停用旧角色' })).toHaveCount(0);
  expect(state.getOptionRequests()).toBeGreaterThan(0);

  await entitySelect.selectOption(activeEntity.id);
  await expect(page.getByRole('button', { name: '生成 2 个缺失视图' })).toBeVisible();
  await expect(page.getByLabel('画面风格')).toBeHidden();
  await page.getByRole('button', { name: '生成设置' }).click();
  await expect(page.getByLabel('画面风格')).toBeVisible();
  await page.getByTestId('asset-table-row').click();
  await page.getByTestId('asset-inspector').getByRole('button', { name: '归档' }).click();

  await expect(page.getByText('资产已归档')).toBeVisible();
  await expect(entitySelect.locator('option', { hasText: '林澈' })).toHaveCount(1);
});

test('asset editor is a focused drawer and production-object deactivation refreshes the workbench', async ({ page }) => {
  await installMocks(page);
  await page.goto(`/assets?novel_id=${novel.id}`);

  await page.getByTestId('asset-table-row').click();
  const inspector = page.getByTestId('asset-inspector');
  await inspector.getByRole('button', { name: '编辑' }).click();

  const editor = page.getByRole('dialog', { name: '编辑资产' });
  await expect(editor).toBeVisible();
  await expect(editor.getByText('技术信息')).toBeVisible();
  await expect(editor.getByPlaceholder('生成参数 JSON，可选，例如：{ "source": "starter", "editable": true }')).toBeHidden();
  await editor.getByRole('button', { name: '取消' }).click();
  await expect(editor).toBeHidden();
  await expect(page.getByRole('heading', { name: '资产工作台' })).toBeVisible();

  await inspector.getByRole('button', { name: '停用制片对象' }).click();
  const confirm = page.getByRole('dialog', { name: '停用制片对象' });
  await expect(confirm).toContainText('林澈');
  await expect(confirm).toContainText('1 项活动资产');
  await confirm.getByRole('button', { name: '确认停用' }).click();

  await expect(page.getByText('已停用制片对象「林澈」，并归档 1 项资产')).toBeVisible();
  await expect(page.getByTestId('asset-table-row')).toHaveCount(0);
  await expect(page.getByLabel('小说对象').locator('option', { hasText: '林澈' })).toHaveCount(0);
});
