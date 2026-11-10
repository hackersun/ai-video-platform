import type { Route } from '@playwright/test';

/**
 * Read-only endpoints that newer Studio panels fetch opportunistically.
 * Specs that throw on unmocked routes call this first so they keep focusing
 * on the behaviour under test instead of every incidental GET.
 */
export async function fulfillStudioFallback(route: Route, path: string): Promise<boolean> {
  if (route.request().method() !== 'GET') return false;
  const json = (body: unknown) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });

  const cards = path.match(/^\/api\/v1\/production-cards\/novel\/([^/]+)$/);
  if (cards) {
    // No production cards unless a spec mocks them explicitly.
    await route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'not found' }) });
    return true;
  }
  if (path === '/api/v1/video/models') {
    await json({ models: [] });
    return true;
  }
  if (path === '/api/v1/publication-pipeline-statuses') {
    await json({ statuses: {} });
    return true;
  }
  if (/^\/api\/v1\/novels\/[^/]+\/publication-pipelines$/.test(path)) {
    await json([]);
    return true;
  }
  if (/^\/api\/v1\/chapters\/novel\/[^/]+$/.test(path)) {
    await json([]);
    return true;
  }
  const novel = path.match(/^\/api\/v1\/novels\/([^/]+)$/);
  if (novel) {
    await json({
      id: novel[1],
      title: '测试小说',
      description: '',
      genre: '',
      status: 'draft',
      chapter_count: 0,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    });
    return true;
  }
  return false;
}
