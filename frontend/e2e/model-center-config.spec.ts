import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 86400 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `model-center-catalog-${Date.now()}`;
  await page.addInitScript(({ token, id }) => {
    localStorage.setItem('auth_token', token);
    localStorage.setItem('user', JSON.stringify({ id, username: id }));
  }, { token: devToken(userId), id: userId });
});

test('provider selectors hide internal catalog records from stale responses', async ({ page }) => {
  await page.route('**/api/v1/llm/providers', async (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify([
      { id: 'volcano', name: 'volcano', name_cn: '火山引擎', base_url: 'https://ark.example.test' },
      { id: 'deterministic-acceptance', name: 'cached-provider', name_cn: 'Deterministic Internal', base_url: 'https://internal.example.test' },
      { id: 'cached-contract', name: 'contract-text', name_cn: 'Contract Internal', base_url: 'https://internal.example.test' },
      { id: 'cached-preflight', name: 'cached-provider', name_en: 'preflight-provider-en', name_cn: 'Preflight Internal', base_url: 'https://internal.example.test' },
      { id: 'cached-test', name: 'test-provider-text', name_cn: 'Test Internal', base_url: 'https://internal.example.test' },
      { id: 'cached-placeholder', name: 'cached-provider', name_cn: 'Placeholder Internal', base_url: 'https://internal.example.test', description: 'placeholder-provider-description' },
      { id: 'cached-tts', name: 'tts-provider-text', name_cn: 'TTS Internal', base_url: 'https://internal.example.test' },
      { id: 'cached-contract-url', name: 'cached-provider', name_cn: 'Contract URL Internal', base_url: 'contract-provider-base-url' },
      { id: 'cached-cn-preflight', name: 'cached-provider', name_cn: '预检供应商', base_url: 'https://internal.example.test' },
      { id: 'cached-cn-test', name: 'cached-provider', name_cn: '测试供应商', base_url: 'https://internal.example.test' },
      { id: 'cached-cn-placeholder', name: 'cached-provider', name_cn: '占位供应商', base_url: 'https://internal.example.test' },
      { id: 'cached-cn-tts', name: 'cached-provider', name_cn: 'TTS开通供应商', base_url: 'https://internal.example.test' },
    ]),
  }));
  await page.route('**/api/v1/llm/models**', async (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: '[]',
  }));
  await page.route('**/api/v1/llm/configs', async (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: '[]',
  }));

  await page.goto('/llm-config');

  const providerSelect = page.getByLabel('服务商');
  await expect(providerSelect).toBeVisible();
  await expect(providerSelect.locator('option')).toHaveText(['选择服务商', '火山引擎']);
  await expect(page.getByRole('button', { name: '火山引擎' })).toBeVisible();
  await expect(page.getByRole('button', { name: /Internal$/ })).toHaveCount(0);
});
