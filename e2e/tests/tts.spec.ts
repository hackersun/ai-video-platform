import { test, expect } from '@playwright/test';

test.describe('TTS页面后端集成', () => {
  test('从 /tts/jobs 加载并展示历史记录', async ({ page }) => {
    await page.route('**/api/v1/tts/jobs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'job-1',
            text: '后端历史台词A',
            voice: '年轻女声',
            status: 'succeeded',
            created_at: '2026-03-23T10:00:00Z',
            audio_url: '/static/audio/job-1.mp3'
          }
        ]),
      });
    });

    await page.goto('/tts');

    await expect(page.locator('h1')).toContainText('语音合成');
    await expect(page.getByText('后端历史台词A')).toBeVisible();
  });

  test('历史记录中的非安全音频链接不会被激活', async ({ page }) => {
    await page.route('**/api/v1/tts/jobs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'job-xss',
            text: '危险链接样本',
            voice: '年轻女声',
            status: 'succeeded',
            created_at: '2026-03-23T10:00:00Z',
            audio_url: '//evil.example/audio.mp3'
          }
        ]),
      });
    });

    await page.goto('/tts');
    await page.getByText('危险链接样本').click();

    await expect(page.getByText('输入文本后点击生成')).toBeVisible();
    await expect(page.getByRole('button', { name: '下载' })).toBeDisabled();
  });

  test('提交生成请求到 /tts/generate 并展示提交状态', async ({ page }) => {
    await page.route('**/api/v1/tts/jobs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });

    await page.route('**/api/v1/tts/generate', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          task_id: 'tts-task-1',
          job_id: 'job-1',
          status: 'succeeded',
          message: 'TTS 任务已完成'
        }),
      });
    });

    page.on('dialog', async (dialog) => {
      await dialog.dismiss();
    });

    await page.goto('/tts');
    await page.getByPlaceholder('请输入火山引擎 API Key').fill('test-key');
    await page.getByPlaceholder('请输入要转换为语音的文本...').fill('请播放这段台词');

    const generateRequestPromise = page.waitForRequest('**/api/v1/tts/generate');
    await page.getByRole('button', { name: '生成语音' }).click();

    const generateRequest = await generateRequestPromise;
    expect(generateRequest.postDataJSON()).toMatchObject({
      text: '请播放这段台词',
      voice: 'female-young',
      speed: 1,
      api_key: 'test-key',
    });

    await expect(page.getByText('生成任务已提交，等待可播放音频')).toBeVisible();
    await expect(page.getByRole('button', { name: '下载' })).toBeDisabled();
  });
});
