import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 86400 })).toString('base64url');
  return `dev.${payload}.sig`;
}

test('任务中心优先显示书名与步骤中文，而不是只靠短 UUID', async ({ page }) => {
  const userId = `jobs-name-${Date.now()}`;
  await page.addInitScript(({ authToken, authUserId }) => {
    localStorage.setItem('auth_token', authToken);
    localStorage.setItem('user', JSON.stringify({ id: authUserId, username: authUserId, email: `${authUserId}@example.test` }));
  }, { authToken: devToken(userId), authUserId: userId });

  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/novels') || path.includes('/novels?')) {
      await route.fulfill({ json: [{ id: 'novel-1', title: '雾港来客' }] });
      return;
    }
    if (path.includes('/video/jobs')) {
      await route.fulfill({ json: [{
        id: 'job-uuid-aaaa-bbbb-cccc-dddddddddddd',
        title: 'unused raw title',
        status: 'running',
        progress_percent: 40,
        novel_id: 'novel-1',
        novel_title: '雾港来客',
        stage: 'run_media_quality',
        created_at: new Date().toISOString(),
      }] });
      return;
    }
    if (path.includes('/jobs')) {
      await route.fulfill({ json: [] });
      return;
    }
    await route.fulfill({ json: [] });
  });

  await page.goto('/jobs');
  await expect(page.getByRole('heading', { name: '《雾港来客》· 生成画面和配音' })).toBeVisible();
  await expect(page.getByText('生成画面和配音').first()).toBeVisible();
});
