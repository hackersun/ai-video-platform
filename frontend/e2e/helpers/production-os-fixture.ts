import { expect, test as base, type Page, type Route } from '@playwright/test';

export const REAL_BACKEND = process.env.PRODUCTION_OS_REAL_BACKEND === '1';

export function devToken(userId: string) {
  const payload = Buffer.from(JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 86400 })).toString('base64url');
  return `dev.${payload}.sig`;
}

export const test = base.extend<{ productionOsUserId: string }>({
  productionOsUserId: async ({}, use, testInfo) => {
    await use(`production-os-${testInfo.workerIndex}-${Date.now()}`);
  },
  page: async ({ page, productionOsUserId }, use) => {
    await page.addInitScript(({ token, userId }) => {
      localStorage.setItem('auth_token', token);
      localStorage.setItem('user', JSON.stringify({ id: userId, username: userId, email: `${userId}@example.test` }));
    }, { token: devToken(productionOsUserId), userId: productionOsUserId });
    await use(page);
  },
});

export { expect };

export async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
}

export async function frontendApi<T>(
  page: Page,
  path: string,
  init: { method?: string; body?: string; headers?: Record<string, string> } = {},
): Promise<T> {
  const apiBase = process.env.NEXT_PUBLIC_API_URL || '/api/v1';
  return page.evaluate(async ({ apiBaseUrl, apiPath, requestInit }) => {
    const token = localStorage.getItem('auth_token');
    const response = await fetch(`${apiBaseUrl}${apiPath}`, {
      method: requestInit.method,
      body: requestInit.body,
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(requestInit.headers || {}) },
    });
    const payload = await response.json().catch(() => null);
    if (!response.ok) throw new Error(JSON.stringify(payload));
    return payload;
  }, { apiBaseUrl: apiBase, apiPath: path, requestInit: init }) as Promise<T>;
}

export function observeProductionRequests(page: Page) {
  const requests: Array<{ method: string; path: string; body: unknown }> = [];
  page.on('request', (request) => {
    const url = new URL(request.url());
    if (!url.pathname.startsWith('/api/v1/')) return;
    requests.push({ method: request.method(), path: url.pathname, body: request.postDataJSON() });
  });
  return requests;
}
