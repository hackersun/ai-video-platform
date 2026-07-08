import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 3600 })).toString('base64url');
  return `dev.${payload}.sig`;
}

test('object storage adapter exposes credentials and qiniu upload fields', async ({ page }) => {
  await page.addInitScript(({ token, userId }) => {
    localStorage.setItem('auth_token', token);
    localStorage.setItem('user', JSON.stringify({ id: userId, username: userId, email: `${userId}@example.test` }));
  }, { token: devToken('storage-ui-user'), userId: 'storage-ui-user' });

  await page.route('**/api/v1/external/providers', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        { id: 'openai', name: 'openai', name_cn: 'OpenAI / Sora', api_type: 'audio_video', base_url: 'https://api.openai.com/v1' },
        { id: 'object_storage', name: 'object_storage', name_cn: '对象存储 / CDN', api_type: 'storage', base_url: '' },
      ]),
    });
  });
  await page.route('**/api/v1/external/configs', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });
  await page.route('**/api/v1/external/capability-status', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ readiness: {}, providers: [], configs: [], registry: {} }) });
  });

  await page.goto('/production-adapters');
  await page.locator('select').first().selectOption('object_storage');

  await expect(page.getByLabel('API Key')).toBeVisible();
  await expect(page.getByLabel('API Secret')).toBeVisible();
  const adapterJson = page.locator('textarea').first();
  await expect(adapterJson).toContainText('storage_provider');
  await expect(adapterJson).toContainText('bucket');
  await expect(adapterJson).toContainText('upload_url');
});

test('object storage adapter runs media delivery self-check from the config card', async ({ page }) => {
  const configId = 'storage-config-001';
  await page.addInitScript(({ token, userId }) => {
    localStorage.setItem('auth_token', token);
    localStorage.setItem('user', JSON.stringify({ id: userId, username: userId, email: `${userId}@example.test` }));
  }, { token: devToken('storage-delivery-ui-user'), userId: 'storage-delivery-ui-user' });

  await page.route('**/api/v1/external/providers', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        { id: 'object_storage', name: 'object_storage', name_cn: '对象存储 / CDN', api_type: 'storage', base_url: '' },
      ]),
    });
  });
  await page.route('**/api/v1/external/configs', async (route) => {
    if (route.request().method() !== 'GET') {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: configId,
          provider_id: 'object_storage',
          provider_name: '对象存储 / CDN',
          provider_key: 'object_storage',
          api_type: 'storage',
          name: 'sunqy 七牛 Kodo 私有媒体出口',
          custom_base_url: 'https://cdn.example.com',
          timeout: 60,
          retry_count: 3,
          is_default: true,
          is_active: true,
          test_status: 'success',
          test_message: '七牛对象存储上传出口可用',
          extra_config: { storage_provider: 'qiniu', bucket: 'ai-video-test' },
        },
      ]),
    });
  });
  await page.route('**/api/v1/external/capability-status', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        readiness: { storage: { ready_count: 1, configured_count: 1, provider_count: 1 } },
        providers: [],
        configs: [],
        registry: {},
      }),
    });
  });

  let deliveryCheckRequested = false;
  await page.route(`**/api/v1/external/configs/${configId}/delivery-test`, async (route) => {
    deliveryCheckRequested = true;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        config_id: configId,
        status: 'success',
        success: true,
        message: '真实媒体交付自检通过：本地 /static 探针文件已转换为云端可读 URL，并完成下载验证',
        checked_at: new Date().toISOString(),
        source_url: '/static/generated/adapter-self-check/probe.png',
        delivery_method: 'qiniu_object_upload',
        object_key: 'static/generated/adapter-self-check/probe.png',
        download_status: 200,
        provider_url_preview: 'https://cdn.example.com/static/generated/adapter-self-check/probe.png?e=1700000300&token=***',
      }),
    });
  });

  await page.goto('/production-adapters');
  const card = page.locator('div').filter({ hasText: 'sunqy 七牛 Kodo 私有媒体出口' }).first();
  await expect(card.getByRole('button', { name: '交付自检' })).toBeVisible();
  await card.getByRole('button', { name: '交付自检' }).click();

  await expect(page.getByText('真实媒体交付自检通过').first()).toBeVisible();
  await expect(page.getByText('交付方式：qiniu_object_upload')).toBeVisible();
  await expect(page.getByText('对象 Key：static/generated/adapter-self-check/probe.png')).toBeVisible();
  expect(deliveryCheckRequested).toBe(true);
});
