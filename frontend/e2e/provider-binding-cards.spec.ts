import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  const payload = Buffer.from(JSON.stringify({ sub: 'binding-cards-user', exp: Math.floor(Date.now() / 1000) + 86400 })).toString('base64url');
  await page.addInitScript((token) => {
    localStorage.setItem('auth_token', token);
    localStorage.setItem('user', JSON.stringify({ id: 'binding-cards-user', username: 'binding-cards-user' }));
  }, `dev.${payload}.sig`);
});

test('selected model binding controls final-quality readiness without changing canonical version', async ({ page }) => {
  let bindingReady = false;
  let createPayload: any = null;

  await page.route('**/api/v1/production-cards/novel/novel-binding', async (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      novel_id: 'novel-binding',
      summary: { ready: 1, incomplete: 0 },
      cards: [{
        entity_id: 'char-mili', entity_type: 'character', name: '米粒', novel_id: 'novel-binding',
        visual: { locked_count: 1, missing_views: [], views: [{ view_key: 'front', asset_id: 'asset-mili-v3', version: 3, url: 'https://cdn.example.com/mili.png', is_locked: true, is_final: true }] },
        usage: { shot_count: 4 }, voice: { locked: true }, readiness: { score: 100, final_ready: true, gaps: [] },
      }],
    }),
  }));
  await page.route('**/api/v1/assets/bindings/health**', async (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      provider_id: 'volcano', model_id: 'seedance-2.0',
      assets: [{ asset_id: 'asset-mili-v3', asset_version: 3, canonical_ready: true, binding_required: true, binding_ready: bindingReady, binding_id: bindingReady ? 'binding-1' : null }],
    }),
  }));
  await page.route('**/api/v1/assets/asset-mili-v3/bindings', async (route) => {
    createPayload = route.request().postDataJSON();
    bindingReady = true;
    await route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify({ id: 'binding-1', upload_status: 'ready', verified: true }) });
  });

  await page.goto('/studio/cards?novel_id=novel-binding&provider_id=volcano&model_id=seedance-2.0');
  const card = page.getByTestId('production-card-char-mili');
  await expect(card.getByText('Canonical v3 已就绪')).toBeVisible();
  await expect(card.getByText('Seedance 2.0 引用未就绪')).toBeVisible();
  await expect(card.getByRole('button', { name: '终稿生成' })).toBeDisabled();
  await card.getByRole('button', { name: '生成模型引用' }).click();
  await expect(card.getByText('Seedance 2.0 引用已验证')).toBeVisible();
  await expect(card.getByRole('button', { name: '终稿生成' })).toBeEnabled();
  expect(createPayload).toMatchObject({ provider_id: 'volcano', model_id: 'seedance-2.0', asset_version: 3, verify: true });
  await expect(card.getByText('Canonical v3 已就绪')).toBeVisible();
  await card.getByRole('button', { name: '终稿生成' }).click();
  await expect(page).toHaveURL(/\/studio\?.*provider_id=volcano.*model_id=seedance-2.0.*production_strategy=final_quality/);
});
