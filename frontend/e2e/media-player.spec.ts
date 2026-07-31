import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

async function installAuth(page: import('@playwright/test').Page, userId: string) {
  await page.addInitScript(({ authToken, authUserId }) => {
    localStorage.setItem('auth_token', authToken);
    localStorage.setItem('user', JSON.stringify({
      id: authUserId,
      username: authUserId,
      email: `${authUserId}@example.test`,
    }));
  }, { authToken: devToken(userId), authUserId: userId });
}

test('交付成片通过站内播放器获取最新签名地址', async ({ page }) => {
  const userId = 'media-player-user';
  await installAuth(page, userId);

  await page.route('**/api/v1/media/jobs/job-1/playback-url', async (route) => {
    await route.fulfill({
      json: {
        job_id: 'job-1',
        url: 'https://media.example.test/final.mp4?token=fresh',
        delivery_method: 'qiniu_signed_refresh',
      },
    });
  });
  await page.goto('/media-player?job_id=job-1');

  await expect(page.getByRole('heading', { name: '成片播放' })).toBeVisible();
  const video = page.getByTestId('delivery-video');
  await expect(video).toBeVisible();
  await expect(video).toHaveAttribute('src', 'https://media.example.test/final.mp4?token=fresh');
  await expect(page.getByText('播放地址已刷新')).toBeVisible();
});

test('播放签名失效时自动刷新一次并继续使用新地址', async ({ page }) => {
  await installAuth(page, 'media-player-auto-refresh-user');
  let playbackCalls = 0;
  await page.route('**/api/v1/media/jobs/job-auto/playback-url', async (route) => {
    playbackCalls += 1;
    await route.fulfill({
      json: {
        job_id: 'job-auto',
        url: `https://media.example.test/auto.mp4?token=fresh-${playbackCalls}`,
        delivery_method: 'qiniu_signed_refresh',
      },
    });
  });
  await page.goto('/media-player?job_id=job-auto');

  const video = page.getByTestId('delivery-video');
  await expect(video).toHaveAttribute('src', /token=fresh-\d+/);
  await page.waitForTimeout(100);
  const callsBeforeError = playbackCalls;
  await video.evaluate((element) => element.dispatchEvent(new Event('error')));

  await expect.poll(() => playbackCalls).toBe(callsBeforeError + 1);
  await expect(video).toHaveAttribute(
    'src',
    `https://media.example.test/auto.mp4?token=fresh-${callsBeforeError + 1}`,
  );
  await expect(page.getByText('播放地址已自动刷新')).toBeVisible();
});

test('点击下载时重新获取签名地址后再下载', async ({ page }) => {
  await installAuth(page, 'media-player-download-user');
  let playbackCalls = 0;
  let mediaRequestUrl = '';
  await page.route('**/api/v1/media/jobs/job-download/playback-url', async (route) => {
    playbackCalls += 1;
    await route.fulfill({
      json: {
        job_id: 'job-download',
        url: `https://media.example.test/download.mp4?token=fresh-${playbackCalls}`,
        delivery_method: 'local_static',
      },
    });
  });
  await page.route('https://media.example.test/download.mp4**', async (route) => {
    mediaRequestUrl = route.request().url();
    await route.fulfill({
      body: 'video-bytes',
      contentType: 'video/mp4',
      headers: { 'Content-Disposition': 'attachment; filename="final.mp4"' },
    });
  });
  await page.goto('/media-player?job_id=job-download');

  await expect(page.getByRole('link', { name: '下载成片' })).toBeVisible();
  await page.waitForTimeout(100);
  const callsBeforeDownload = playbackCalls;
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('link', { name: '下载成片' }).click();
  await downloadPromise;

  expect(playbackCalls).toBe(callsBeforeDownload + 1);
  expect(mediaRequestUrl).toContain('_download=');
});
