import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 86400 })).toString('base64url');
  return `dev.${payload}.sig`;
}

const makeEntity = (index: number) => ({
  id: `entity-${index}`, novel_id: 'novel-review', entity_type: 'character',
  name: `角色 ${index}`, canonical_name: `角色 ${index}`, aliases: [],
  description: `角色描述 ${index}`, evidence: `原文证据 ${index}`, confidence: 90,
  source: 'provider_model', review_status: 'candidate', is_approved: false,
  attributes: {}, relations: [], extra_data: { quality: { score: 80 } },
});

test.beforeEach(async ({ page }) => {
  const userId = 'entity-review-user';
  await page.addInitScript(({ token, id }) => {
    localStorage.setItem('auth_token', token);
    localStorage.setItem('user', JSON.stringify({ id, username: id, email: `${id}@example.test` }));
  }, { token: devToken(userId), id: userId });
});

test('实体工作台分页、跨页选择，并在定稿后保持当前位置', async ({ page }) => {
  const all = Array.from({ length: 76 }, (_, index) => makeEntity(index + 1));
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.pathname.endsWith('/novels/novel-review')) {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ id: 'novel-review', title: '玄玉道途' }) });
    }
    if (url.pathname.includes('/entity-review/novels/novel-review/entities')) {
      const currentPage = Number(url.searchParams.get('page') || 1);
      const size = Number(url.searchParams.get('page_size') || 50);
      const items = all.slice((currentPage - 1) * size, currentPage * size);
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
        items, page: currentPage, page_size: size, total: all.length, total_pages: Math.ceil(all.length / size),
        summary: { total: all.length, candidate_count: all.length, approved_count: 0, rejected_count: 0, counts: { candidate: all.length }, by_type: { character: all.length } },
      }) });
    }
    if (url.pathname.endsWith('/entity-review/bulk-review')) {
      const payload = request.postDataJSON();
      const updated = all.filter((item) => payload.entity_ids.includes(item.id)).map((item) => ({ ...item, review_status: payload.action === 'approve' ? 'approved' : 'rejected' }));
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ updated, skipped: [], summary: { total: 76, candidate_count: 75, approved_count: 1, rejected_count: 0 } }) });
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });

  await page.goto('/novels/novel-review/asset-analysis');
  await expect(page.getByRole('heading', { name: '玄玉道途' })).toBeVisible();
  await expect(page.getByText('第 1 / 2 页')).toBeVisible();
  await page.getByRole('checkbox', { name: '选择角色 1', exact: true }).check();
  await page.getByRole('button', { name: '下一页' }).click();
  await expect(page).toHaveURL(/page=2/);
  await page.getByRole('checkbox', { name: '选择角色 51' }).check();
  await expect(page.getByText('已选择 2 项')).toBeVisible();

  await page.getByRole('button', { name: '定稿角色 51' }).click();
  await expect(page).toHaveURL(/page=2/);
  await expect(page.getByText('第 2 / 2 页')).toBeVisible();
  await expect(page.getByRole('table').getByText('角色 51')).toBeVisible();
  await expect(page.locator('[data-testid="entity-review-initial-loading"]')).toHaveCount(0);
});
