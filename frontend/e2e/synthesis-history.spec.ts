import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `synthesis-history-user-${Date.now()}`;
  const token = devToken(userId);
  await page.addInitScript(({ authToken, authUserId }) => {
    localStorage.setItem('auth_token', authToken);
    localStorage.setItem('user', JSON.stringify({
      id: authUserId,
      username: authUserId,
      email: `${authUserId}@example.test`,
    }));
  }, { authToken: token, authUserId: userId });
});

test('synthesis history can filter and preview render artifacts inline', async ({ page }) => {
  const synthesisRequests: string[] = [];

  await page.route('**/api/v1/video/jobs**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });
  await page.route('**/api/v1/tts/jobs**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });
  await page.route('**/api/v1/synthesis/publications**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });
  await page.route('**/api/v1/synthesis/jobs**', async (route) => {
    const url = new URL(route.request().url());
    synthesisRequests.push(url.search);
    const novelId = url.searchParams.get('novel_id');
    const body = novelId && novelId !== 'novel-001'
      ? []
      : [
          {
            id: 'syn-render-001',
            job_id: 'syn-render-001',
            user_id: 'user-1',
            title: '第一章可播放渲染包',
            status: 'succeeded',
            progress: 100,
            output_url: '/static/exports/render-001-preview.html',
            manifest_url: '/static/exports/sequence-001.json',
            preview_url: '/static/exports/render-001-preview.html',
            srt_url: '/static/exports/render-001.srt',
            timeline_url: '/static/exports/render-001-timeline.json',
            render_manifest_url: '/static/exports/render-001.json',
            render_status: 'rendered',
            segment_count: 2,
            novel_id: 'novel-001',
            chapter_id: 'chapter-001',
            script_id: 'script-001',
            storyboard_id: 'storyboard-001',
            shot_id: 'shot-001',
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ];
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });

  await page.goto('/synthesis');

  await expect(page.getByText('合成历史筛选')).toBeVisible();
  await page.getByLabel('小说ID').fill('novel-001');
  await page.getByLabel('章节ID').fill('chapter-001');
  await page.getByLabel('渲染状态').selectOption('rendered');
  await page.getByRole('button', { name: '筛选历史' }).click();

  await expect.poll(() => synthesisRequests.some((query) => query.includes('novel_id=novel-001'))).toBeTruthy();
  await expect(page.getByText('第一章可播放渲染包')).toBeVisible();

  await page.getByRole('button', { name: '预览 第一章可播放渲染包' }).click();

  await expect(page.getByTestId('synthesis-history-preview')).toBeVisible();
  await expect(page.getByText('历史预览：第一章可播放渲染包')).toBeVisible();
  await expect(page.getByRole('link', { name: '字幕 SRT' })).toBeVisible();
  await expect(page.getByRole('link', { name: '时间线' })).toBeVisible();
  await expect(page.getByRole('link', { name: '渲染清单' })).toBeVisible();
});
