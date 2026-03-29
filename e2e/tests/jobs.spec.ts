import { test, expect } from '@playwright/test';

test.describe('任务队列页面后端集成', () => {
  test('从后端加载并展示视频/TTS/合成任务', async ({ page }) => {
    await page.route('**/api/v1/video/jobs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'video-job-1',
            title: '后端视频任务A',
            status: 'succeeded',
            progress: 100,
            created_at: '2026-03-24T10:00:00Z',
            duration: 12,
            video_url: '/static/video/video-job-1.mp4',
          },
        ]),
      });
    });

    await page.route('**/api/v1/tts/jobs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'tts-job-1',
            text: '后端语音任务B',
            status: 'running',
            progress: 40,
            created_at: '2026-03-24T10:01:00Z',
            duration_seconds: 8,
          },
        ]),
      });
    });

    await page.route('**/api/v1/synthesis/jobs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'syn-job-1',
            title: '后端合成任务C',
            status: 'pending',
            progress: 0,
            created_at: '2026-03-24T10:02:00Z',
          },
        ]),
      });
    });

    await page.goto('/jobs');

    await expect(page.locator('h1')).toContainText('任务队列');
    await expect(page.getByText('后端视频任务A')).toBeVisible();
    await expect(page.getByText('后端语音任务B')).toBeVisible();
    await expect(page.getByText('后端合成任务C')).toBeVisible();
    await expect(page.getByText('第一章视频生成')).toHaveCount(0);
  });

  test('单个端点失败时仍展示其它任务', async ({ page }) => {
    await page.route('**/api/v1/video/jobs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'video-job-2',
            title: '可用视频任务',
            status: 'succeeded',
            progress: 100,
            created_at: '2026-03-24T11:00:00Z',
            video_url: '/static/video/video-job-2.mp4',
          },
        ]),
      });
    });

    await page.route('**/api/v1/tts/jobs', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'tts endpoint failed' }),
      });
    });

    await page.route('**/api/v1/synthesis/jobs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'syn-job-2',
            title: '可用合成任务',
            status: 'running',
            progress: 35,
            created_at: '2026-03-24T11:02:00Z',
          },
        ]),
      });
    });

    await page.goto('/jobs');

    await expect(page.getByText('可用视频任务')).toBeVisible();
    await expect(page.getByText('可用合成任务')).toBeVisible();
    await expect(page.getByText('暂无任务')).toHaveCount(0);
  });
});
