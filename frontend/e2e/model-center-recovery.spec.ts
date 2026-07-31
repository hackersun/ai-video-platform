import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 86400 })).toString('base64url');
  return `dev.${payload}.sig`;
}

const providerPage = {
  items: [{ id: 'volcengine', code: 'volcengine', display_name: '火山引擎', provider_family: 'volcano', is_builtin: true, enabled: true, revision: 1 }],
  meta: { page: 1, page_size: 100, total: 1 },
};

function catalogPage(page: number) {
  return {
    items: [{
      provider_id: 'volcengine', provider_name: '火山引擎', provider_code: 'volcengine',
      model_name: page === 1 ? 'Seedance 1.5 Pro' : 'Seedance 1.5 Lite',
      api_model_id: page === 1 ? 'doubao-seedance-1-5-pro' : 'doubao-seedance-1-5-lite',
      profile_version_id: `profile-${page}`, profile_version: page, driver_key: 'volcano_ark_video',
      legacy_model_id: null, legacy_config_id: null, certification_status: 'unverified',
      capabilities: ['video_generation'],
    }],
    meta: { page, page_size: 20, total: 23 },
  };
}

test.beforeEach(async ({ page }) => {
  const id = `model-center-recovery-${Date.now()}`;
  await page.addInitScript(({ token, userId }) => {
    localStorage.setItem('auth_token', token);
    localStorage.setItem('user', JSON.stringify({ id: userId, username: userId }));
  }, { token: devToken(id), userId: id });
  await page.route('**/api/v1/model-center/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/\/+$/g, '');
    let body: unknown = { blocking_issues: [], connections: [], recipes: [] };
    if (path === '/api/v1/model-center/providers') body = providerPage;
    if (path === '/api/v1/model-center/drivers') body = {
      items: [{ key: 'volcano_ark_video_v3', capabilities: ['video_generation'], parameter_schema: {}, contract_version: 'driver-v1' }],
      meta: { page: 1, page_size: 100, total: 1 },
    };
    if (path === '/api/v1/model-center/catalog') body = catalogPage(Number(url.searchParams.get('page') || 1));
    if (path === '/api/v1/model-center/connections') body = {
      items: [{
        id: 'connection-1', provider_id: 'volcengine', provider_name: '火山引擎', provider_code: 'volcengine',
        name: '主视频连接', status: 'verified', base_url: null, has_secret: true, secret_hint: '****',
        secret_updated_at: null, enabled: true, revision: 1,
      }],
      meta: { page: Number(url.searchParams.get('page') || 1), page_size: 20, total: 21 },
    };
    if (path === '/api/v1/model-center/bindings') body = {
      items: [{
        id: 'binding-video', scope_type: 'user', scope_id: 'user-1', task: 'shot_video', capability: 'video_generation',
        profile_version_id: 'profile-1', profile_name: 'Seedance 1.5 Pro', api_model_id: 'doubao-seedance-1-5-pro',
        connection_id: 'connection-1', connection_name: '主视频连接', provider_name: '火山引擎', priority: 100,
        route_policy: 'single', fallback_profile_version_ids: [], certification_status: 'unverified', affected_recipes: 2,
        version: 1, revision: 1, is_active: true,
      }],
      meta: { page: 1, page_size: 20, total: 1 },
    };
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
  });
});

test('catalog searches and paginates on the server with readable labels', async ({ page }) => {
  const catalogRequests: string[] = [];
  page.on('request', (request) => {
    if (request.url().includes('/model-center/catalog?')) catalogRequests.push(request.url());
  });
  await page.goto('/llm-config?section=catalog&capability=video_generation');
  await expect(page.getByText('Seedance 1.5 Pro')).toBeVisible();
  await expect(page.getByRole('table').getByText('火山引擎')).toBeVisible();
  await page.getByLabel('搜索模型').fill('seedance');
  await expect.poll(() => catalogRequests.some((url) => url.includes('q=seedance') && url.includes('capability=video_generation'))).toBe(true);
  await page.getByRole('button', { name: '下一页' }).click();
  await expect(page.getByText('Seedance 1.5 Lite')).toBeVisible();
  await expect.poll(() => catalogRequests.some((url) => url.includes('page=2'))).toBe(true);
  await expect(page.getByText('第 2 / 2 页')).toBeVisible();
});

test('connection form uses provider picker and readable paged rows', async ({ page }) => {
  await page.goto('/llm-config?section=connections');
  await expect(page.getByLabel('提供方')).toHaveValue('volcengine');
  await expect(page.getByRole('option', { name: '火山引擎（volcengine）' })).toHaveCount(1);
  await expect(page.getByRole('cell', { name: '火山引擎' })).toBeVisible();
  await expect(page.getByText('第 1 / 2 页')).toBeVisible();
  await expect(page.getByRole('button', { name: '下一页' })).toBeEnabled();
});

test('model profile wizard saves validates and publishes an installed driver', async ({ page }) => {
  const requests: Array<{ path: string; body: unknown }> = [];
  await page.route('**/api/v1/model-center/**', async (route) => {
    if (route.request().method() === 'GET') return route.fallback();
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/\/+$/g, '');
    requests.push({ path, body: route.request().postDataJSON() });
    let body: unknown = {};
    if (path === '/api/v1/model-center/profiles') body = { id: 'profile-new', provider_id: 'volcengine', profile_key: 'seedance-new', display_name: 'Seedance 新模型', enabled: true, revision: 1 };
    if (path === '/api/v1/model-center/profiles/profile-new/versions') body = { id: 'version-new', model_id: 'profile-new', version: 1, api_model_id: 'doubao-seedance-new', driver_key: 'volcano_ark_video_v3', capabilities: ['video_generation'], contract_version: 'driver-v1', status: 'draft', revision: 1 };
    if (path === '/api/v1/model-center/profile-versions/version-new/validate') body = { valid: true, errors: [], audit_event_id: 'audit-validate' };
    if (path === '/api/v1/model-center/profile-versions/version-new/publish') body = { published_version_id: 'version-new', previous_version_id: null, impact: { affected_bindings: 0, affected_profiles: 1, affected_recipes: 0, affected_prompts: 0 }, audit_event_id: 'audit-publish' };
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
  });

  await page.goto('/llm-config?section=catalog');
  await page.getByRole('button', { name: '新增模型' }).click();
  await page.getByLabel('模型用途').selectOption('video_generation');
  await page.getByLabel('模型显示名称').fill('Seedance 新模型');
  await page.getByLabel('供应商 Model ID').fill('doubao-seedance-new');
  await page.getByLabel('兼容适配器').selectOption('volcano_ark_video_v3');
  await page.getByRole('button', { name: '保存模型草稿' }).click();
  await expect(page.getByText('草稿 v1 已保存')).toBeVisible();
  await page.getByRole('button', { name: '运行免费配置校验' }).click();
  await expect(page.getByText('配置校验通过，可以发布。')).toBeVisible();
  await page.getByLabel('发布说明').fill('契约验证通过');
  await page.getByRole('button', { name: '发布模型' }).click();
  await expect(page.getByText('模型已发布。下一步请配置供应商账号并设为默认模型。')).toBeVisible();

  expect(requests.map((item) => item.path)).toEqual([
    '/api/v1/model-center/profiles',
    '/api/v1/model-center/profiles/profile-new/versions',
    '/api/v1/model-center/profile-versions/version-new/validate',
    '/api/v1/model-center/profile-versions/version-new/publish',
  ]);
  expect(requests[1]?.body).toMatchObject({
    expected_revision: 1, driver_key: 'volcano_ark_video_v3',
    capabilities: ['video_generation'], contract_version: 'driver-v1',
  });
});

test('binding editor only combines matching readable model and connection choices', async ({ page }) => {
  let createBody: Record<string, unknown> | null = null;
  await page.route('**/api/v1/model-center/bindings', async (route) => {
    if (route.request().method() === 'GET') return route.fallback();
    createBody = route.request().postDataJSON();
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({
      id: 'binding-new', ...createBody, profile_name: 'Seedance 1.5 Pro', api_model_id: 'doubao-seedance-1-5-pro',
      connection_name: '主视频连接', provider_name: '火山引擎', fallback_profile_version_ids: [],
      certification_status: 'unverified', affected_recipes: 0, version: 2, revision: 1, is_active: true,
    }) });
  });

  await page.goto('/llm-config?section=bindings');
  await expect(page.getByText('高级路由：single · P100')).toBeVisible();
  await expect(page.getByText('Seedance 1.5 Pro')).toBeVisible();
  await page.getByRole('button', { name: '设置默认模型' }).click();
  await page.getByLabel('使用场景').selectOption('shot_video');
  await expect(page.getByText('视频生成', { exact: true })).toBeVisible();
  await expect(page.getByLabel('默认模型', { exact: true })).toHaveValue('profile-1');
  await expect(page.getByLabel('供应商账号', { exact: true })).toHaveValue('connection-1');
  await page.getByLabel('变更说明').fill('建立视频默认路由');
  await page.getByRole('button', { name: '保存默认模型' }).click();
  await expect.poll(() => createBody).not.toBeNull();
  expect(createBody).toMatchObject({
    task: 'shot_video', capability: 'video_generation', profile_version_id: 'profile-1',
    connection_id: 'connection-1', route_policy: 'single', reason: '建立视频默认路由',
  });
});

test('binding editor previews impact and persists an update', async ({ page }) => {
  let updateBody: Record<string, unknown> | null = null;
  await page.route('**/api/v1/model-center/bindings/binding-video', async (route) => {
    updateBody = route.request().postDataJSON();
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({
      id: 'binding-video', ...updateBody, scope_id: 'user-1', profile_name: 'Seedance 1.5 Pro',
      api_model_id: 'doubao-seedance-1-5-pro', connection_name: '主视频连接', provider_name: '火山引擎',
      certification_status: 'unverified', affected_recipes: 2, version: 2, revision: 2,
    }) });
  });

  await page.goto('/llm-config?section=bindings');
  await page.getByRole('button', { name: '更换镜头视频生成默认模型' }).click();
  await expect(page.getByText('更换后将影响 2 个生产组合')).toBeVisible();
  await page.getByText('高级路由设置（可选）').click();
  await page.getByLabel('优先级').fill('40');
  await page.getByLabel('在生产中启用').uncheck();
  await page.getByLabel('变更说明').fill('临时停用问题路由');
  await page.getByRole('button', { name: '确认更换默认模型' }).click();

  await expect.poll(() => updateBody).not.toBeNull();
  expect(updateBody).toMatchObject({
    priority: 40, is_active: false, expected_revision: 1, reason: '临时停用问题路由',
  });
});
