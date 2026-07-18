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
    if (path === '/api/v1/model-center/catalog') body = catalogPage(Number(url.searchParams.get('page') || 1));
    if (path === '/api/v1/model-center/connections') body = {
      items: [{
        id: 'connection-1', provider_id: 'volcengine', provider_name: '火山引擎', provider_code: 'volcengine',
        name: '主视频连接', status: 'verified', base_url: null, has_secret: true, secret_hint: '****',
        secret_updated_at: null, enabled: true, revision: 1,
      }],
      meta: { page: Number(url.searchParams.get('page') || 1), page_size: 20, total: 21 },
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
