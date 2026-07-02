import { expect, test } from '@playwright/test';

function devToken(userId: string) {
  const payload = Buffer.from(
    JSON.stringify({ sub: userId, exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60 })
  ).toString('base64url');
  return `dev.${payload}.sig`;
}

test.beforeEach(async ({ page }) => {
  const userId = `onboarding-user-${Date.now()}`;
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

test('quick start provides a sample story and beginner-ready checks', async ({ page }) => {
  await page.route('**/api/v1/llm/configs', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });

  await page.goto('/quick-start');
  await expect(page.getByRole('heading', { name: '连续动漫向导' })).toBeVisible();
  await page.getByRole('button', { name: '填入示例故事' }).click();

  await expect(page.getByPlaceholder('例如：星灯邮差')).toHaveValue('星灯邮差');
  await expect(page.getByPlaceholder(/写 2-5 句话即可/)).toHaveValue(/云上列车/);
  await expect(page.getByText('高级模型配置可先不管')).toBeVisible();
  await expect(page.getByText('就绪')).toHaveCount(4);
});

test('model config keeps test and noisy TTS models hidden until advanced mode is opened', async ({ page }) => {
  await page.route('**/api/v1/llm/providers', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 'volcano',
          name: 'volcano',
          name_cn: '火山引擎',
          base_url: 'https://ark.cn-beijing.volces.com/api/v3',
          description: '测试用火山提供商',
        },
      ]),
    });
  });

  await page.route('**/api/v1/llm/models**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          id: 'volcano-seedance-recommended',
          provider_id: 'volcano',
          model_id: 'doubao-seedance-2-0-fast',
          model_name: 'Doubao Seedance 2.0 Fast',
          model_name_cn: '常用视频模型',
          model_type: 'video',
          capabilities: ['text-to-video', 'image-to-video'],
          context_window: 0,
          max_tokens: 0,
          input_cost_per_1k: 0,
          output_cost_per_1k: 0,
          is_recommended: true,
        },
        {
          id: 'test-video-chaos',
          provider_id: 'volcano',
          model_id: 'test-video-chaos',
          model_name: 'test-video-chaos',
          model_name_cn: '测试视频模型',
          model_type: 'video',
          capabilities: ['text-to-video'],
          context_window: 0,
          max_tokens: 0,
          input_cost_per_1k: 0,
          output_cost_per_1k: 0,
        },
        {
          id: 'tts-noisy-voice',
          provider_id: 'volcano',
          model_id: 'speech-voice-preview',
          model_name: 'speech-voice-preview',
          model_name_cn: '普通 TTS 声音模型',
          model_type: 'tts',
          capabilities: ['text-to-speech'],
          context_window: 0,
          max_tokens: 0,
          input_cost_per_1k: 0,
          output_cost_per_1k: 0,
        },
      ]),
    });
  });

  await page.route('**/api/v1/llm/configs', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });

  await page.goto('/llm-config');
  await expect(page.getByText('新手模式：只显示推荐和常用模型')).toBeVisible();
  await expect(page.getByText('常用视频模型').first()).toBeVisible();
  await expect(page.getByText('测试视频模型')).toHaveCount(0);
  await expect(page.getByText('普通 TTS 声音模型')).toHaveCount(0);

  await page.getByRole('button', { name: /显示测试\/高级模型/ }).click();
  await expect(page.getByText('测试视频模型').first()).toBeVisible();
  await expect(page.getByText('普通 TTS 声音模型').first()).toBeVisible();
});

test('top navigation defaults to beginner mode and can reveal expert tools', async ({ page }) => {
  await page.route('**/api/v1/novels**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });
  await page.route('**/api/v1/video/jobs**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });
  await page.route('**/api/v1/tts/jobs**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });
  await page.route('**/api/v1/scripts**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });

  await page.addInitScript(() => localStorage.removeItem('ai-video-platform:expert-nav'));
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('/dashboard');

  await expect(page.getByRole('link', { name: '连续动漫向导' })).toBeVisible();
  await expect(page.getByRole('button', { name: '打开故事创作菜单' })).toHaveCount(0);
  await page.getByRole('button', { name: '专家工具' }).click();
  await expect(page.getByRole('button', { name: '打开故事创作菜单' })).toBeVisible();
  await expect(page.getByRole('button', { name: '收起专家工具' })).toBeVisible();
});
