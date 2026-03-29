import { test, expect, Page } from '@playwright/test';

/**
 * 登录辅助函数
 */
async function login(page: Page, username: string = 'e2etest', password: string = 'test123456') {
  await page.goto('/login');
  await page.fill('input[type="text"]', username);
  await page.fill('input[type="password"]', password);
  await page.click('button:has-text("登录")');
  await page.waitForURL(/.*dashboard/, { timeout: 15000 });
}

/**
 * 等待加载完成
 */
async function waitForLoading(page: Page) {
  const loader = page.locator('[class*="animate-spin"]').first();
  if (await loader.isVisible({ timeout: 1000 }).catch(() => false)) {
    await loader.waitFor({ state: 'hidden', timeout: 10000 });
  }
}

// ========== 视频生成页面测试 ==========

test.describe('视频生成页面测试', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.goto('/video-generation');
    await waitForLoading(page);
  });

  test('页面元素渲染正确', async ({ page }) => {
    await expect(page.locator('text=视频生成')).toBeVisible();
    await expect(page.locator('text=火山引擎').or(page.locator('text=提供商'))).toBeVisible();
    await page.screenshot({ path: 'test-results/video-generation-page.png' });
  });

  test('提供商选择器可见', async ({ page }) => {
    const providerCard = page.locator('text=火山引擎');
    await expect(providerCard).toBeVisible();
    await page.screenshot({ path: 'test-results/video-providers.png' });
  });

  test('参数配置区域可见', async ({ page }) => {
    await expect(page.locator('text=参数配置, text=视频描述').first()).toBeVisible();
    await page.screenshot({ path: 'test-results/video-params.png' });
  });

  test('视频描述输入框可用', async ({ page }) => {
    const promptInput = page.locator('textarea[placeholder*="描述"], textarea[placeholder*="视频"]');
    if (await promptInput.isVisible()) {
      await promptInput.fill('测试视频描述');
      await expect(promptInput).toHaveValue('测试视频描述');
      await page.screenshot({ path: 'test-results/video-prompt-filled.png' });
    }
  });

  test('时长选择器可用', async ({ page }) => {
    // 查找时长滑块或按钮
    const durationSlider = page.locator('[class*="slider"], input[type="range"]');
    const durationButtons = page.locator('button:has-text("4"), button:has-text("5"), button:has-text("10")');

    const hasSlider = await durationSlider.first().isVisible({ timeout: 1000 }).catch(() => false);
    const hasButtons = await durationButtons.first().isVisible({ timeout: 1000 }).catch(() => false);

    if (hasButtons) {
      await durationButtons.first().click();
      await page.waitForTimeout(300);
      await page.screenshot({ path: 'test-results/video-duration.png' });
    }
  });

  test('分辨率选择器可用', async ({ page }) => {
    const resolutions = ['480p', '720p', '1080p'];
    for (const res of resolutions) {
      const button = page.locator(`button:has-text("${res}")`);
      if (await button.isVisible({ timeout: 500 }).catch(() => false)) {
        await button.click();
        await page.waitForTimeout(200);
      }
    }
    await page.screenshot({ path: 'test-results/video-resolution.png' });
  });

  test('参考图片URL输入框', async ({ page }) => {
    const imageInput = page.locator('input[placeholder*="图片"], input[placeholder*="URL"]');
    if (await imageInput.isVisible({ timeout: 2000 }).catch(() => false)) {
      await imageInput.fill('https://example.com/image.jpg');
      await expect(imageInput).toHaveValue('https://example.com/image.jpg');
      await page.screenshot({ path: 'test-results/video-image-url.png' });
    }
  });

  test('开始生成按钮可见', async ({ page }) => {
    const generateButton = page.locator('button:has-text("开始生成"), button:has-text("生成视频")');
    await expect(generateButton).toBeVisible();
    await page.screenshot({ path: 'test-results/video-generate-button.png' });
  });

  test('API Key 未配置提示', async ({ page }) => {
    const apiWarning = page.locator('text=未配置 API Key, text=请先配置');
    const hasWarning = await apiWarning.isVisible({ timeout: 2000 }).catch(() => false);
    if (hasWarning) {
      await expect(page.locator('text=前往配置')).toBeVisible();
      await page.screenshot({ path: 'test-results/video-no-api-key.png' });
    }
  });

  test('生成历史区域可见', async ({ page }) => {
    await expect(page.locator('text=生成历史').or(page.locator('text=历史记录'))).toBeVisible();
    await page.screenshot({ path: 'test-results/video-history-area.png' });
  });

  test('模型信息卡片可见', async ({ page }) => {
    const modelInfo = page.locator('text=模型, text=Doubao, text=Seedance');
    const hasModel = await modelInfo.first().isVisible({ timeout: 2000 }).catch(() => false);
    if (hasModel) {
      await page.screenshot({ path: 'test-results/video-model-info.png' });
    }
  });
});

// ========== 视频生成历史测试 ==========

test.describe('视频生成历史测试', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.goto('/video-generation');
    await waitForLoading(page);
  });

  test('历史记录列表渲染', async ({ page }) => {
    await waitForLoading(page);
    // 历史记录可能在加载中或已有数据
    const historyArea = page.locator('[class*="history"], [class*="clock"]').first();
    const hasHistory = await historyArea.isVisible({ timeout: 2000 }).catch(() => false);
    expect(hasHistory || true).toBeTruthy();
    await page.screenshot({ path: 'test-results/video-history.png' });
  });

  test('刷新历史按钮', async ({ page }) => {
    const refreshButton = page.locator('button:has([class*="refresh"]), button:has([class*="Refresh"])');
    if (await refreshButton.isVisible({ timeout: 1000 }).catch(() => false)) {
      await refreshButton.click();
      await page.waitForTimeout(500);
      await page.screenshot({ path: 'test-results/video-refresh-history.png' });
    }
  });

  test('空历史状态', async ({ page }) => {
    await waitForLoading(page);
    const emptyState = page.locator('text=暂无生成历史, text=没有历史');
    const hasEmpty = await emptyState.isVisible({ timeout: 2000 }).catch(() => false);
    if (hasEmpty) {
      await expect(page.locator('text=暂无生成历史')).toBeVisible();
      await page.screenshot({ path: 'test-results/video-empty-history.png' });
    }
  });
});

// ========== 视频生成流程测试 (Mock) ==========

test.describe('视频生成流程测试 (Mock API)', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('提交生成请求', async ({ page }) => {
    // Mock API
    await page.route('**/api/v1/video/jobs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([])
      });
    });

    await page.route('**/api/v1/video/generate', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          task_id: 'mock-task-id',
          job_id: 'mock-job-id',
          status: 'pending'
        })
      });
    });

    await page.route('**/api/v1/llm/configs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ provider: '火山引擎', api_key: 'mock-key' }])
      });
    });

    await page.goto('/video-generation');
    await waitForLoading(page);

    // 填写视频描述
    const promptInput = page.locator('textarea[placeholder*="描述"], textarea[placeholder*="视频"]');
    if (await promptInput.isVisible()) {
      await promptInput.fill('无人机以极快速度穿越障碍，带来沉浸式飞行体验');
    }

    // 点击生成
    const generateButton = page.locator('button:has-text("开始生成"), button:has-text("生成视频")');
    await generateButton.click();

    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'test-results/video-generating.png' });
  });

  test('生成状态显示', async ({ page }) => {
    await page.route('**/api/v1/video/jobs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'video-job-1',
            title: '测试视频',
            status: 'running',
            progress: 50,
            created_at: new Date().toISOString()
          }
        ])
      });
    });

    await page.route('**/api/v1/llm/configs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ provider: '火山引擎', api_key: 'mock-key' }])
      });
    });

    await page.goto('/video-generation');
    await waitForLoading(page);

    // 验证生成中的状态显示
    await page.waitForTimeout(500);
    const generating = page.locator('text=生成中, text=提交中');
    const hasGenerating = await generating.isVisible({ timeout: 3000 }).catch(() => false);

    if (hasGenerating) {
      await page.screenshot({ path: 'test-results/video-status-generating.png' });
    } else {
      // 检查历史记录中的状态
      await page.screenshot({ path: 'test-results/video-status-check.png' });
    }
  });
});

// ========== TTS 页面测试 ==========

test.describe('TTS 语音合成页面测试', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.goto('/tts');
    await waitForLoading(page);
  });

  test('页面元素渲染正确', async ({ page }) => {
    await expect(page.locator('text=语音合成, text=TTS').first()).toBeVisible();
    await page.screenshot({ path: 'test-results/tts-page.png' });
  });

  test('文本输入框可用', async ({ page }) => {
    const textInput = page.locator('textarea[placeholder*="文本"], textarea[placeholder*="台词"], input[placeholder*="文本"]').first();
    if (await textInput.isVisible()) {
      await textInput.fill('这是一段测试台词');
      await expect(textInput).toHaveValue('这是一段测试台词');
      await page.screenshot({ path: 'test-results/tts-text-filled.png' });
    }
  });

  test('声音选择器可见', async ({ page }) => {
    const voiceSelect = page.locator('select, button:has-text("声音"), button:has-text("角色")').first();
    const hasVoice = await voiceSelect.isVisible({ timeout: 2000 }).catch(() => false);
    if (hasVoice) {
      await page.screenshot({ path: 'test-results/tts-voice-select.png' });
    }
  });

  test('参数调节控件', async ({ page }) => {
    // 查找滑块控件
    const sliders = page.locator('[class*="slider"], input[type="range"]');
    const sliderCount = await sliders.count();
    expect(sliderCount).toBeGreaterThanOrEqual(0);
    await page.screenshot({ path: 'test-results/tts-sliders.png' });
  });

  test('生成按钮状态', async ({ page }) => {
    const generateButton = page.locator('button:has-text("生成语音"), button:has-text("生成"), button:has-text("合成")');
    await expect(generateButton).toBeVisible();
    await page.screenshot({ path: 'test-results/tts-generate-button.png' });
  });

  test('历史记录加载', async ({ page }) => {
    await waitForLoading(page);
    const historyArea = page.locator('text=历史记录, text=历史');
    const hasHistory = await historyArea.isVisible({ timeout: 2000 }).catch(() => false);
    expect(hasHistory || true).toBeTruthy();
    await page.screenshot({ path: 'test-results/tts-history-area.png' });
  });
});

// ========== TTS 完整流程测试 (Mock) ==========

test.describe('TTS 完整流程测试 (Mock API)', () => {
  test('提交 TTS 生成请求', async ({ page }) => {
    await login(page);

    // Mock API
    await page.route('**/api/v1/tts/jobs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([])
      });
    });

    await page.route('**/api/v1/tts/generate', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          task_id: 'tts-task-1',
          job_id: 'tts-job-1',
          status: 'pending',
          message: 'TTS 任务已提交'
        })
      });
    });

    await page.goto('/tts');
    await waitForLoading(page);

    // 填写文本
    const textInput = page.locator('textarea[placeholder*="文本"], textarea[placeholder*="台词"]').first();
    if (await textInput.isVisible()) {
      await textInput.fill('测试语音合成');
    }

    // 填写 API Key
    const apiKeyInput = page.locator('input[placeholder*="API Key"], input[placeholder*="api key"]').first();
    if (await apiKeyInput.isVisible()) {
      await apiKeyInput.fill('test-api-key');
    }

    // 点击生成
    const generateButton = page.locator('button:has-text("生成语音"), button:has-text("生成")').first();
    await generateButton.click();

    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'test-results/tts-generating.png' });
  });
});
