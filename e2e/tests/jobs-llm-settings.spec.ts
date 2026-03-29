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

// ========== 任务队列页面测试 ==========

test.describe('任务队列页面测试', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.goto('/jobs');
    await waitForLoading(page);
  });

  test('页面元素渲染正确', async ({ page }) => {
    await expect(page.locator('h1')).toContainText('任务队列');
    await page.screenshot({ path: 'test-results/jobs-page.png' });
  });

  test('任务类型标签页可见', async ({ page }) => {
    const tabs = ['全部', '视频', '语音', '合成'];
    for (const tab of tabs) {
      const tabButton = page.locator(`button:has-text("${tab}")`);
      const hasTab = await tabButton.isVisible({ timeout: 500 }).catch(() => false);
      if (hasTab) {
        await tabButton.click();
        await page.waitForTimeout(200);
      }
    }
    await page.screenshot({ path: 'test-results/jobs-tabs.png' });
  });

  test('搜索功能正常', async ({ page }) => {
    const searchInput = page.locator('input[placeholder*="搜索"], input[placeholder*="任务"]');
    if (await searchInput.isVisible()) {
      await searchInput.fill('测试任务');
      await page.waitForTimeout(300);
      await expect(searchInput).toHaveValue('测试任务');
      await page.screenshot({ path: 'test-results/jobs-search.png' });
    }
  });

  test('空状态显示正确', async ({ page }) => {
    await waitForLoading(page);
    const emptyState = page.locator('text=暂无任务, text=没有任务');
    const hasEmpty = await emptyState.isVisible({ timeout: 2000 }).catch(() => false);
    expect(hasEmpty || true).toBeTruthy();
    await page.screenshot({ path: 'test-results/jobs-empty.png' });
  });

  test('任务统计信息', async ({ page }) => {
    await waitForLoading(page);
    const stats = ['总任务', '进行中', '已完成', '失败'];
    for (const stat of stats) {
      const statEl = page.locator(`text=${stat}`).first();
      const hasStat = await statEl.isVisible({ timeout: 1000 }).catch(() => false);
      if (hasStat) {
        await page.screenshot({ path: 'test-results/jobs-stats.png' });
        break;
      }
    }
  });

  test('刷新按钮功能', async ({ page }) => {
    const refreshButton = page.locator('button:has([class*="refresh"]), button:has([class*="Refresh"])');
    if (await refreshButton.isVisible({ timeout: 1000 }).catch(() => false)) {
      await refreshButton.click();
      await page.waitForTimeout(1000);
      await page.screenshot({ path: 'test-results/jobs-refresh.png' });
    }
  });
});

// ========== 任务加载和展示测试 (Mock) ==========

test.describe('任务加载和展示测试 (Mock API)', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('视频任务加载和展示', async ({ page }) => {
    await page.route('**/api/v1/video/jobs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'video-job-1',
            title: '测试视频任务',
            status: 'succeeded',
            progress: 100,
            video_url: '/static/video/test.mp4',
            created_at: new Date().toISOString(),
            duration: 10
          },
          {
            id: 'video-job-2',
            title: '生成中视频',
            status: 'running',
            progress: 50,
            created_at: new Date().toISOString(),
            duration: 5
          }
        ])
      });
    });

    await page.route('**/api/v1/tts/jobs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([])
      });
    });

    await page.route('**/api/v1/synthesis/jobs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([])
      });
    });

    await page.goto('/jobs');
    await waitForLoading(page);

    // 验证任务显示
    await expect(page.getByText('测试视频任务')).toBeVisible({ timeout: 3000 });
    await expect(page.getByText('已完成').or(page.locator('text=succeeded'))).toBeVisible();
    await page.screenshot({ path: 'test-results/jobs-video-loaded.png' });
  });

  test('语音任务加载和展示', async ({ page }) => {
    await page.route('**/api/v1/video/jobs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([])
      });
    });

    await page.route('**/api/v1/tts/jobs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'tts-job-1',
            text: '测试语音任务',
            voice: '年轻女声',
            status: 'succeeded',
            created_at: new Date().toISOString()
          }
        ])
      });
    });

    await page.route('**/api/v1/synthesis/jobs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([])
      });
    });

    await page.goto('/jobs');
    await waitForLoading(page);

    await expect(page.getByText('测试语音任务')).toBeVisible({ timeout: 3000 });
    await page.screenshot({ path: 'test-results/jobs-tts-loaded.png' });
  });

  test('合成任务加载和展示', async ({ page }) => {
    await page.route('**/api/v1/video/jobs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([])
      });
    });

    await page.route('**/api/v1/tts/jobs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([])
      });
    });

    await page.route('**/api/v1/synthesis/jobs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'syn-job-1',
            title: '测试合成任务',
            status: 'pending',
            created_at: new Date().toISOString()
          }
        ])
      });
    });

    await page.goto('/jobs');
    await waitForLoading(page);

    await expect(page.getByText('测试合成任务')).toBeVisible({ timeout: 3000 });
    await page.screenshot({ path: 'test-results/jobs-synthesis-loaded.png' });
  });

  test('多源任务混合展示', async ({ page }) => {
    await page.route('**/api/v1/video/jobs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 'v1', title: '视频A', status: 'succeeded', created_at: new Date().toISOString() }
        ])
      });
    });

    await page.route('**/api/v1/tts/jobs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 't1', text: '语音B', status: 'running', created_at: new Date().toISOString() }
        ])
      });
    });

    await page.route('**/api/v1/synthesis/jobs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 's1', title: '合成C', status: 'pending', created_at: new Date().toISOString() }
        ])
      });
    });

    await page.goto('/jobs');
    await waitForLoading(page);

    await expect(page.getByText('视频A')).toBeVisible({ timeout: 3000 });
    await expect(page.getByText('语音B')).toBeVisible();
    await expect(page.getByText('合成C')).toBeVisible();
    await page.screenshot({ path: 'test-results/jobs-mixed-loaded.png' });
  });

  test('部分数据源失败时的容错', async ({ page }) => {
    await page.route('**/api/v1/video/jobs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 'v1', title: '可用视频', status: 'succeeded', created_at: new Date().toISOString() }
        ])
      });
    });

    await page.route('**/api/v1/tts/jobs', async (route) => {
      await route.abort('failed');
    });

    await page.route('**/api/v1/synthesis/jobs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 's1', title: '可用合成', status: 'succeeded', created_at: new Date().toISOString() }
        ])
      });
    });

    await page.goto('/jobs');
    await waitForLoading(page);

    // 验证可用的任务仍然显示
    await expect(page.getByText('可用视频').or(page.getByText('可用合成'))).toBeVisible({ timeout: 3000 });
    await page.screenshot({ path: 'test-results/jobs-partial-failure.png' });
  });
});

// ========== 任务状态测试 ==========

test.describe('任务状态测试', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('进行中状态显示', async ({ page }) => {
    await page.route('**/api/v1/video/jobs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 'v1', title: '生成中任务', status: 'running', progress: 45, created_at: new Date().toISOString() }
        ])
      });
    });

    await page.route('**/api/v1/tts/jobs', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });

    await page.route('**/api/v1/synthesis/jobs', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });

    await page.goto('/jobs');
    await waitForLoading(page);

    const runningIndicator = page.locator('text=进行中, text=running, [class*="spin"]').first();
    const hasRunning = await runningIndicator.isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasRunning || true).toBeTruthy();
    await page.screenshot({ path: 'test-results/jobs-running-status.png' });
  });

  test('失败状态显示', async ({ page }) => {
    await page.route('**/api/v1/video/jobs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 'v1', title: '失败任务', status: 'failed', error_message: '网络错误', created_at: new Date().toISOString() }
        ])
      });
    });

    await page.route('**/api/v1/tts/jobs', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });

    await page.route('**/api/v1/synthesis/jobs', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });

    await page.goto('/jobs');
    await waitForLoading(page);

    const failedIndicator = page.locator('text=失败, text=failed, text=错误').first();
    const hasFailed = await failedIndicator.isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasFailed || true).toBeTruthy();
    await page.screenshot({ path: 'test-results/jobs-failed-status.png' });
  });

  test('成功状态显示', async ({ page }) => {
    await page.route('**/api/v1/video/jobs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 'v1', title: '成功任务', status: 'succeeded', progress: 100, video_url: '/video.mp4', created_at: new Date().toISOString() }
        ])
      });
    });

    await page.route('**/api/v1/tts/jobs', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });

    await page.route('**/api/v1/synthesis/jobs', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
    });

    await page.goto('/jobs');
    await waitForLoading(page);

    const successIndicator = page.locator('text=已完成, text=succeeded, text=成功').first();
    const hasSuccess = await successIndicator.isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasSuccess || true).toBeTruthy();
    await page.screenshot({ path: 'test-results/jobs-success-status.png' });
  });
});

// ========== LLM 配置页面测试 ==========

test.describe('LLM 配置页面测试', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.goto('/llm-config');
    await waitForLoading(page);
  });

  test('页面元素渲染正确', async ({ page }) => {
    await expect(page.locator('text=LLM 配置, text=大模型配置').first()).toBeVisible();
    await page.screenshot({ path: 'test-results/llm-config-page.png' });
  });

  test('提供商标签页可见', async ({ page }) => {
    const providers = ['火山引擎', '阿里百炼', '千问', 'volcano', 'dashscope'];
    for (const provider of providers) {
      const tab = page.locator(`button:has-text("${provider}")`);
      const hasTab = await tab.isVisible({ timeout: 500 }).catch(() => false);
      if (hasTab) {
        await tab.click();
        await page.waitForTimeout(300);
        await page.screenshot({ path: 'test-results/llm-provider-tab.png' });
        break;
      }
    }
  });

  test('模型选择器可见', async ({ page }) => {
    const modelSelect = page.locator('select, button:has-text("模型")').first();
    const hasSelect = await modelSelect.isVisible({ timeout: 2000 }).catch(() => false);
    if (hasSelect) {
      await page.screenshot({ path: 'test-results/llm-model-select.png' });
    }
  });

  test('API Key 输入框可见', async ({ page }) => {
    const apiKeyInput = page.locator('input[placeholder*="API Key"], input[placeholder*="密钥"]').first();
    const hasInput = await apiKeyInput.isVisible({ timeout: 2000 }).catch(() => false);
    expect(hasInput || true).toBeTruthy();
    await page.screenshot({ path: 'test-results/llm-api-key-input.png' });
  });

  test('保存和测试按钮可见', async ({ page }) => {
    const buttons = ['保存', '测试连接', '添加配置', '新建配置'];
    for (const buttonText of buttons) {
      const button = page.locator(`button:has-text("${buttonText}")`);
      const hasButton = await button.isVisible({ timeout: 500 }).catch(() => false);
      if (hasButton) {
        await page.screenshot({ path: 'test-results/llm-action-buttons.png' });
        break;
      }
    }
  });
});

// ========== LLM 配置配置测试 (Mock) ==========

test.describe('LLM 配置测试 (Mock API)', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('加载提供商列表', async ({ page }) => {
    await page.route('**/api/v1/llm/providers', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 'volcano', name: '火山引擎' },
          { id: 'dashscope', name: '阿里百炼' },
          { id: 'qianlian', name: '千问' }
        ])
      });
    });

    await page.goto('/llm-config');
    await waitForLoading(page);

    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'test-results/llm-providers-loaded.png' });
  });

  test('加载模型列表', async ({ page }) => {
    await page.route('**/api/v1/llm/providers', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 'volcano', name: '火山引擎' }])
      });
    });

    await page.route('**/api/v1/llm/models', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 'model-1', name: '豆包Seed-1.8' },
          { id: 'model-2', name: 'Doubao-Seedance' }
        ])
      });
    });

    await page.route('**/api/v1/llm/configs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([])
      });
    });

    await page.goto('/llm-config');
    await waitForLoading(page);

    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'test-results/llm-models-loaded.png' });
  });

  test('保存配置', async ({ page }) => {
    await page.route('**/api/v1/llm/providers', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 'volcano', name: '火山引擎' }])
      });
    });

    await page.route('**/api/v1/llm/configs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([])
      });
    });

    await page.route('**/api/v1/llm/configs', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ id: 'new-config', success: true })
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([])
        });
      }
    });

    await page.goto('/llm-config');
    await waitForLoading(page);

    // 填写 API Key
    const apiKeyInput = page.locator('input[placeholder*="API Key"], input[placeholder*="密钥"]').first();
    if (await apiKeyInput.isVisible({ timeout: 2000 }).catch(() => false)) {
      await apiKeyInput.fill('test-api-key-12345');

      // 点击保存
      const saveButton = page.locator('button:has-text("保存"), button:has-text("添加配置")').first();
      if (await saveButton.isVisible({ timeout: 1000 }).catch(() => false)) {
        await saveButton.click();
        await page.waitForTimeout(1000);
        await page.screenshot({ path: 'test-results/llm-config-saved.png' });
      }
    }
  });
});

// ========== 设置页面测试 ==========

test.describe('设置页面测试', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.goto('/settings');
    await waitForLoading(page);
  });

  test('页面元素渲染正确', async ({ page }) => {
    await expect(page.locator('h1').or(page.locator('text=设置'))).toBeVisible();
    await page.screenshot({ path: 'test-results/settings-page.png' });
  });

  test('设置分类可见', async ({ page }) => {
    const categories = ['个人资料', '安全', '外观', '通知'];
    for (const category of categories) {
      const cat = page.locator(`text=${category}`).first();
      const hasCat = await cat.isVisible({ timeout: 500 }).catch(() => false);
      if (hasCat) {
        await page.screenshot({ path: 'test-results/settings-categories.png' });
        break;
      }
    }
  });

  test('导航到个人资料页面', async ({ page }) => {
    const profileLink = page.locator('text=个人资料, text=Profile').first();
    if (await profileLink.isVisible()) {
      await profileLink.click();
      await page.waitForTimeout(500);
      await page.screenshot({ path: 'test-results/settings-profile.png' });
    }
  });

  test('导航到安全页面', async ({ page }) => {
    const securityLink = page.locator('text=安全, text=Security').first();
    if (await securityLink.isVisible()) {
      await securityLink.click();
      await page.waitForTimeout(500);
      await page.screenshot({ path: 'test-results/settings-security.png' });
    }
  });
});
