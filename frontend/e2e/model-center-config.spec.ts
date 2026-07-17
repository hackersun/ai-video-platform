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
      { id: 'contract-text', name: 'contract-text', name_cn: 'Contract Text Internal', base_url: 'https://internal.example.test' },
      { id: 'deterministic-acceptance', name: 'deterministic-acceptance', name_cn: 'Deterministic Acceptance Internal', base_url: 'https://internal.example.test' },
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

  await expect(page.getByRole('button', { name: '火山引擎' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Contract Text Internal' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Deterministic Acceptance Internal' })).toHaveCount(0);
});
