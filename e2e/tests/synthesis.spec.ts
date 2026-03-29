import { test, expect } from '@playwright/test';

test.describe('音视频合成页面后端集成', () => {
  test('从 /synthesis/jobs 加载并展示历史记录', async ({ page }) => {
    await page.route('**/api/v1/synthesis/jobs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'syn-job-1',
            title: '后端合成任务A',
            status: 'succeeded',
            progress: 100,
            created_at: '2026-03-24T10:02:00Z',
            output_url: '/static/output/syn-job-1.mp4'
          }
        ]),
      });
    });

    await page.goto('/synthesis');

    await expect(page.locator('h1')).toContainText('音视频合成');
    await expect(page.getByText('后端合成任务A')).toBeVisible();
  });

  test('提交合成请求到 /synthesis/generate', async ({ page }) => {
    await page.route('**/api/v1/synthesis/jobs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });

    await page.route('**/api/v1/synthesis/generate', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          task_id: 'syn-task-1',
          job_id: 'syn-job-1',
          status: 'succeeded',
          message: '合成任务已完成'
        }),
      });
    });

    page.on('dialog', async (dialog) => {
      await dialog.dismiss();
    });

    await page.goto('/synthesis');
    await page.getByPlaceholder('请输入视频URL').fill('https://example.com/video.mp4');
    await page.getByPlaceholder('请输入音频URL').fill('https://example.com/audio.mp3');
    await page.getByPlaceholder('请输入火山引擎 API Key').fill('test-key');

    const generateRequestPromise = page.waitForRequest('**/api/v1/synthesis/generate');
    await page.getByRole('button', { name: '开始合成' }).click();

    const generateRequest = await generateRequestPromise;
    expect(generateRequest.postDataJSON()).toMatchObject({
      video_url: 'https://example.com/video.mp4',
      audio_url: 'https://example.com/audio.mp3',
      api_key: 'test-key',
    });

    await expect(page.getByText('合成任务已提交')).toBeVisible();
  });
});
